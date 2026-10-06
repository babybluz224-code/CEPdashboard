#!/usr/bin/env python3
"""Read native Primavera P6 .xer files and compare schedule updates.

Standard library only, no network, no AI: it runs entirely on your machine.

  xer_tool.py summary FILE [--project P]
  xer_tool.py check   FILE [--project P]           single-file integrity checks
  xer_tool.py export  FILE OUTDIR [--project P]    tasks.csv and relations.csv
  xer_tool.py diff    OLD NEW [--out report.md] [--float-days N] [--project P]

Activities are matched by Activity ID (task_code), because internal task_ids
change between exports. Write outputs to a gitignored folder (findings/).
"""
import argparse
import csv
import os
import sys
from datetime import datetime

HARD = {"CS_MSO", "CS_MEO"}  # mandatory start / mandatory finish
MILESTONES = {"TT_Mile", "TT_FinMile"}
SKIP_TYPES = {"TT_WBS", "TT_LOE"}


def read_xer(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    text = None
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    tables, cur, fields = {}, None, None
    for line in text.splitlines():
        if not line:
            continue
        p = line.split("\t")
        tag = p[0]
        if tag == "%T":
            cur, fields = p[1], None
            tables[cur] = []
        elif tag == "%F":
            fields = p[1:]
        elif tag == "%R" and cur and fields:
            vals = p[1:] + [""] * (len(fields) - len(p) + 1)
            tables[cur].append(dict(zip(fields, vals[: len(fields)])))
        elif tag == "%E":
            break
    return tables


class Schedule:
    def __init__(self, path, project=None):
        self.path = path
        t = read_xer(path)
        projects = t.get("PROJECT", [])
        if not projects:
            sys.exit(f"{path}: no PROJECT table; is this an XER file?")
        self.projects = projects
        proj = None
        if project:
            proj = next((x for x in projects if project in (x.get("proj_id"), x.get("proj_short_name"))), None)
            if proj is None:
                sys.exit(f"{path}: project {project!r} not found. Available: "
                         + ", ".join(x.get("proj_short_name", x.get("proj_id", "?")) for x in projects))
        else:
            proj = projects[0]
        self.proj = proj
        pid = proj.get("proj_id")
        self.data_date = (proj.get("last_recalc_date") or "")[:10]
        cal_hours = {c.get("clndr_id"): float(c.get("day_hr_cnt") or 8) for c in t.get("CALENDAR", [])}
        self.cal_hours = cal_hours
        tasks = [x for x in t.get("TASK", []) if x.get("proj_id") == pid]
        self.by_id = {x["task_id"]: x for x in tasks}
        self.tasks = {}
        for x in tasks:
            code = x.get("task_code")
            if code:
                self.tasks[code] = x
        self.rels = {}
        for r in t.get("TASKPRED", []):
            s, p_ = self.by_id.get(r.get("task_id")), self.by_id.get(r.get("pred_task_id"))
            if s and p_:
                key = (p_["task_code"], s["task_code"], r.get("pred_type", ""))
                self.rels[key] = float(r.get("lag_hr_cnt") or 0)

    def days(self, code, hours):
        x = self.tasks.get(code, {})
        hpd = self.cal_hours.get(x.get("clndr_id"), 8) or 8
        try:
            return round(float(hours) / hpd, 1)
        except (TypeError, ValueError):
            return None

    def name(self, code):
        return self.tasks.get(code, {}).get("task_name", "")

    def is_real(self, code):
        return self.tasks[code].get("task_type") not in SKIP_TYPES


def d(s):
    s = (s or "")[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def shift_days(a, b):
    da, db = d(a), d(b)
    return (db - da).days if da and db else None


def md_table(headers, rows):
    if not rows:
        return "_none_\n"
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "/") for c in r) + " |")
    return "\n".join(out) + "\n"


def check(s):
    """Single-file integrity checks. Returns {section: (headers, rows)}."""
    res = {}
    dd = s.data_date
    preds, succs = {}, {}
    for (p, q, typ), lag in s.rels.items():
        succs.setdefault(p, []).append((q, typ, lag))
        preds.setdefault(q, []).append((p, typ, lag))

    oos, future, status, opens, consts, leads, flt = [], [], [], [], [], [], []
    for code, x in s.tasks.items():
        if not s.is_real(code):
            continue
        st = x.get("status_code", "")
        a_s, a_f = x.get("act_start_date", ""), x.get("act_end_date", "")
        for (p, typ, lag) in preds.get(code, []):
            px = s.tasks.get(p, {})
            if typ == "PR_FS" and a_s and not px.get("act_end_date"):
                oos.append((code, s.name(code), f"{p} not finished", a_s[:10]))
            elif typ == "PR_FS" and a_s and px.get("act_end_date") and d(a_s) and d(px["act_end_date"]) and d(a_s) < d(px["act_end_date"]):
                oos.append((code, s.name(code), f"{p} finished {px['act_end_date'][:10]}", a_s[:10]))
        if dd:
            for lab, v in (("act_start", a_s), ("act_end", a_f)):
                if v and v[:10] > dd:
                    future.append((code, s.name(code), lab, v[:10], dd))
        if st == "TK_Complete" and not a_f:
            status.append((code, s.name(code), "Complete with no actual finish"))
        if a_s and a_f and d(a_s) and d(a_f) and d(a_s) > d(a_f):
            status.append((code, s.name(code), f"Actual start {a_s[:10]} is after actual finish {a_f[:10]}"))
        if st == "TK_Complete" and x.get("remain_drtn_hr_cnt") not in ("", "0", "0.0", None):
            status.append((code, s.name(code), f"Complete but remaining duration {x['remain_drtn_hr_cnt']} hr"))
        if st == "TK_NotStart" and a_s:
            status.append((code, s.name(code), "Not started but has actual start"))
        if st == "TK_Active" and not a_s:
            status.append((code, s.name(code), "In progress with no actual start"))
        if st == "TK_Active" and x.get("remain_drtn_hr_cnt") in ("0", "0.0"):
            status.append((code, s.name(code), "In progress with 0 remaining duration"))
        if st != "TK_Complete":
            if code not in preds and x.get("task_type") != "TT_Mile":
                opens.append((code, s.name(code), "no predecessor"))
            if code not in succs and x.get("task_type") != "TT_FinMile":
                opens.append((code, s.name(code), "no successor"))
        if x.get("cstr_type"):
            consts.append((code, s.name(code), x["cstr_type"], (x.get("cstr_date") or "")[:10],
                           "MANDATORY" if x["cstr_type"] in HARD else ""))
        tf = x.get("total_float_hr_cnt")
        if st != "TK_Complete" and tf not in (None, ""):
            tfd = s.days(code, tf)
            if tfd is not None and tfd < 0:
                flt.append((code, s.name(code), tfd))
    for (p, q, typ), lag in s.rels.items():
        if lag < 0:
            leads.append((p, q, typ, s.days(p, lag), "lead (negative lag)"))
        elif (s.days(p, lag) or 0) > 20:
            leads.append((p, q, typ, s.days(p, lag), "lag over 20 days"))
    res["Out-of-sequence progress"] = (["Activity", "Name", "Predecessor", "Actual start"], oos)
    res["Actual dates after the data date"] = (["Activity", "Name", "Field", "Date", "Data date"], future)
    res["Status inconsistencies"] = (["Activity", "Name", "Issue"], status)
    res["Open ends (incomplete work)"] = (["Activity", "Name", "Issue"], opens)
    res["Constraints"] = (["Activity", "Name", "Type", "Date", "Flag"], consts)
    res["Leads and long lags"] = (["Pred", "Succ", "Type", "Lag (days)", "Issue"], leads)
    res["Negative float"] = (["Activity", "Name", "Total float (days)"], flt)
    return res


def diff(old, new, float_days=5):
    res = {}
    oc, nc = set(old.tasks), set(new.tasks)
    real = lambda sch, c: sch.is_real(c)
    res["Activities removed"] = (["Activity", "Name", "Old status", "Old actual finish"],
        [(c, old.name(c), old.tasks[c].get("status_code", ""), old.tasks[c].get("act_end_date", "")[:10])
         for c in sorted(oc - nc) if real(old, c)])
    res["Activities added"] = (["Activity", "Name", "Target duration (days)"],
        [(c, new.name(c), new.days(c, new.tasks[c].get("target_drtn_hr_cnt"))) for c in sorted(nc - oc) if real(new, c)])

    retro, regress, dur, noprog, cons, cal, ms, flt = [], [], [], [], [], [], [], []
    for c in sorted(oc & nc):
        o, n = old.tasks[c], new.tasks[c]
        if not real(new, c):
            continue
        nm = new.name(c)
        for fld, lab in (("act_start_date", "actual start"), ("act_end_date", "actual finish")):
            ov, nv = o.get(fld, "")[:16], n.get(fld, "")[:16]
            if ov and ov != nv:
                sh = shift_days(ov, nv)
                retro.append((c, nm, lab, ov, nv or "(removed)", "" if sh is None else f"{sh:+d}"))
        if o.get("status_code") == "TK_Complete" and n.get("status_code") != "TK_Complete":
            regress.append((c, nm, "Complete", n.get("status_code", "")))
        if o.get("status_code") == "TK_Active" and n.get("status_code") == "TK_NotStart":
            regress.append((c, nm, "In progress", "Not started"))
        if o.get("status_code") != "TK_Complete":
            od, nd = old.days(c, o.get("target_drtn_hr_cnt")), new.days(c, n.get("target_drtn_hr_cnt"))
            if od != nd:
                dur.append((c, nm, od, nd, None if od is None or nd is None else round(nd - od, 1)))
            orm, nrm = old.days(c, o.get("remain_drtn_hr_cnt")), new.days(c, n.get("remain_drtn_hr_cnt"))
            if (o.get("status_code") == n.get("status_code") == "TK_NotStart" and orm is not None
                    and nrm is not None and nrm < orm):
                noprog.append((c, nm, orm, nrm))
        for k in ("cstr_type", "cstr_date", "cstr_type2", "cstr_date2"):
            if o.get(k, "")[:10] != n.get(k, "")[:10]:
                cons.append((c, nm, k, o.get(k, "")[:10] or "(none)", n.get(k, "")[:10] or "(none)"))
        if o.get("clndr_id") != n.get("clndr_id"):
            cal.append((c, nm, o.get("clndr_id"), n.get("clndr_id")))
        if n.get("task_type") in MILESTONES:
            for fld in ("early_end_date", "early_start_date", "late_end_date", "target_end_date"):
                sh = shift_days(o.get(fld), n.get(fld))
                if sh:
                    ms.append((c, nm, fld, o.get(fld, "")[:10], n.get(fld, "")[:10], f"{sh:+d}"))
        if n.get("status_code") != "TK_Complete":
            of, nf = old.days(c, o.get("total_float_hr_cnt")), new.days(c, n.get("total_float_hr_cnt"))
            if of is not None and nf is not None and abs(nf - of) >= float_days:
                flt.append((c, nm, of, nf, round(nf - of, 1)))
    res["Retroactive actual-date edits"] = (["Activity", "Name", "Field", "Old", "New", "Shift (days)"], retro)
    res["Status regressions"] = (["Activity", "Name", "Old", "New"], regress)
    res["Duration (original) changes on incomplete work"] = (["Activity", "Name", "Old (days)", "New (days)", "Change"], dur)
    res["Remaining duration cut with no progress"] = (["Activity", "Name", "Old remaining", "New remaining"], noprog)
    res["Constraint changes"] = (["Activity", "Name", "Field", "Old", "New"], cons)
    res["Calendar changes"] = (["Activity", "Name", "Old calendar", "New calendar"], cal)
    res["Milestone date shifts"] = (["Activity", "Name", "Field", "Old", "New", "Shift (days)"], ms)
    res[f"Total float changes of {float_days}+ days"] = (["Activity", "Name", "Old (days)", "New (days)", "Change"], flt)

    rem, add, chg = [], [], []
    for k in sorted(set(old.rels) | set(new.rels)):
        p, q, typ = k
        if p not in new.tasks and p not in old.tasks:
            continue
        if k in old.rels and k not in new.rels:
            both = p in new.tasks and q in new.tasks
            rem.append((p, q, typ, old.days(p, old.rels[k]),
                        "" if both else "(an activity was removed)"))
        elif k not in old.rels:
            add.append((p, q, typ, new.days(p, new.rels[k])))
        elif old.rels[k] != new.rels[k]:
            chg.append((p, q, typ, old.days(p, old.rels[k]), new.days(p, new.rels[k])))
    res["Relationships removed"] = (["Pred", "Succ", "Type", "Lag (days)", "Note"], rem)
    res["Relationships added"] = (["Pred", "Succ", "Type", "Lag (days)"], add)
    res["Lag changes"] = (["Pred", "Succ", "Type", "Old lag", "New lag"], chg)
    return res


def report(title, sections, preamble=""):
    out = [f"# {title}\n", preamble]
    for name, (h, rows) in sections.items():
        out.append(f"\n## {name} ({len(rows)})\n")
        out.append(md_table(h, rows))
    return "\n".join(out)


def cmd_summary(a):
    s = Schedule(a.file, a.project)
    print(f"File: {a.file}\nProjects: " + ", ".join(
        f"{p.get('proj_short_name','?')} (id {p.get('proj_id')})" for p in s.projects))
    print(f"Using: {s.proj.get('proj_short_name')}  data date: {s.data_date or '?'}")
    st = {}
    for c, x in s.tasks.items():
        if s.is_real(c):
            st[x.get("status_code", "?")] = st.get(x.get("status_code", "?"), 0) + 1
    print(f"Activities: {sum(st.values())}  by status: {st}")
    print(f"Relationships: {len(s.rels)}")


def cmd_check(a):
    s = Schedule(a.file, a.project)
    print(report(f"Integrity checks: {os.path.basename(a.file)}", check(s), f"Data date: {s.data_date}\n"))


def cmd_export(a):
    s = Schedule(a.file, a.project)
    os.makedirs(a.outdir, exist_ok=True)
    cols = ["task_code", "task_name", "task_type", "status_code", "target_drtn_hr_cnt", "remain_drtn_hr_cnt",
            "act_start_date", "act_end_date", "early_start_date", "early_end_date", "late_start_date",
            "late_end_date", "total_float_hr_cnt", "free_float_hr_cnt", "cstr_type", "cstr_date",
            "phys_complete_pct", "clndr_id", "wbs_id"]
    with open(os.path.join(a.outdir, "tasks.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for x in s.tasks.values():
            w.writerow([x.get(c, "") for c in cols])
    with open(os.path.join(a.outdir, "relations.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pred", "succ", "type", "lag_hr"])
        for (p, q, t), lag in s.rels.items():
            w.writerow([p, q, t, lag])
    print(f"Wrote {len(s.tasks)} activities and {len(s.rels)} relationships to {a.outdir}")


def cmd_diff(a):
    old, new = Schedule(a.old, a.project), Schedule(a.new, a.project)
    pre = (f"Old: {os.path.basename(a.old)} (data date {old.data_date})  \n"
           f"New: {os.path.basename(a.new)} (data date {new.data_date})  \n"
           "Activities matched by Activity ID. A finding is an inconsistency to investigate, "
           "not proof of intent.\n")
    text = report("Schedule update comparison", diff(old, new, a.float_days), pre)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        open(a.out, "w", encoding="utf-8").write(text)
        print(f"Wrote {a.out}")
    else:
        print(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("summary", cmd_summary), ("check", cmd_check)):
        p = sub.add_parser(name); p.add_argument("file"); p.add_argument("--project"); p.set_defaults(fn=fn)
    p = sub.add_parser("export"); p.add_argument("file"); p.add_argument("outdir"); p.add_argument("--project"); p.set_defaults(fn=cmd_export)
    p = sub.add_parser("diff"); p.add_argument("old"); p.add_argument("new"); p.add_argument("--out")
    p.add_argument("--float-days", type=float, default=5); p.add_argument("--project"); p.set_defaults(fn=cmd_diff)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
