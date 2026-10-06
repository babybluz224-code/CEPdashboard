"""Tests for tools/xer/xer_tool.py using synthetic XER files built on the fly."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "xer"))
import xer_tool  # noqa: E402

TASK_FIELDS = ["task_id", "proj_id", "task_code", "task_name", "task_type", "status_code",
               "target_drtn_hr_cnt", "remain_drtn_hr_cnt", "act_start_date", "act_end_date",
               "early_end_date", "late_end_date", "target_end_date", "total_float_hr_cnt",
               "cstr_type", "cstr_date", "clndr_id"]


def task(i, code, name, status="TK_NotStart", dur=80, rem=None, a_s="", a_f="", ee="", tf=80,
         cstr="", cdate="", typ="TT_Task", cal="1"):
    rem = dur if rem is None else rem
    return {"task_id": str(i), "proj_id": "1", "task_code": code, "task_name": name, "task_type": typ,
            "status_code": status, "target_drtn_hr_cnt": str(dur), "remain_drtn_hr_cnt": str(rem),
            "act_start_date": a_s, "act_end_date": a_f, "early_end_date": ee, "late_end_date": ee,
            "target_end_date": ee, "total_float_hr_cnt": str(tf), "cstr_type": cstr, "cstr_date": cdate,
            "clndr_id": cal}


def write_xer(path, tasks, rels, data_date):
    L = ["ERMHDR\t20.12\t2026-03-01\tProject\tadmin\tadmin\tdbname\tProject Management\tUSD"]
    L += ["%T\tPROJECT", "%F\tproj_id\tproj_short_name\tlast_recalc_date",
          f"%R\t1\tSOLAR1\t{data_date} 08:00"]
    L += ["%T\tCALENDAR", "%F\tclndr_id\tclndr_name\tday_hr_cnt", "%R\t1\tStd\t8", "%R\t2\tSeven\t10"]
    L += ["%T\tTASK", "%F\t" + "\t".join(TASK_FIELDS)]
    L += ["%R\t" + "\t".join(t[f] for f in TASK_FIELDS) for t in tasks]
    L += ["%T\tTASKPRED", "%F\ttask_pred_id\ttask_id\tpred_task_id\tpred_type\tlag_hr_cnt"]
    ids = {t["task_code"]: t["task_id"] for t in tasks}
    for n, (p, q, typ, lag) in enumerate(rels, 1):
        L.append(f"%R\t{n}\t{ids[q]}\t{ids[p]}\t{typ}\t{lag}")
    L.append("%E")
    with open(path, "w", encoding="cp1252", newline="\n") as f:
        f.write("\n".join(L) + "\n")


def base():
    tasks = [
        task(1, "A100", "Mobilize", "TK_Complete", 40, 0, "2026-01-05 08:00", "2026-01-09 17:00", tf=0),
        task(2, "A110", "Grading", "TK_Active", 160, 80, "2026-01-12 08:00", ee="2026-02-20 17:00", tf=0),
        task(3, "A120", "Pile install", "TK_NotStart", 80, ee="2026-03-06 17:00", tf=0),
        task(4, "A130", "Tracker install", "TK_NotStart", 80, ee="2026-03-20 17:00", tf=0),
        task(5, "A140", "Module install", "TK_NotStart", 120, ee="2026-04-10 17:00", tf=0),
        task(6, "M900", "Mechanical Completion", "TK_NotStart", 0, ee="2026-04-30 17:00", tf=0, typ="TT_FinMile"),
    ]
    rels = [("A100", "A110", "PR_FS", 0), ("A110", "A120", "PR_FS", 0), ("A120", "A130", "PR_FS", 0),
            ("A130", "A140", "PR_FS", 0), ("A140", "M900", "PR_FS", 0)]
    return tasks, rels


def update():
    tasks, rels = base()
    by = {t["task_code"]: t for t in tasks}
    by["A100"]["act_start_date"] = "2026-01-12 08:00"          # retroactive actual start edit
    by["A120"]["target_drtn_hr_cnt"] = "40"                    # original duration halved
    by["A120"]["remain_drtn_hr_cnt"] = "40"                    # remaining cut, no progress
    by["A130"]["status_code"] = "TK_Active"                    # started while A120 unfinished
    by["A130"]["act_start_date"] = "2026-02-25 08:00"          # out of sequence
    by["A130"]["cstr_type"], by["A130"]["cstr_date"] = "CS_MSO", "2026-03-23 08:00"
    by["A140"]["total_float_hr_cnt"] = "160"                   # float created
    by["M900"]["early_end_date"] = "2026-05-29 17:00"          # milestone slipped 29 days
    by["M900"]["target_end_date"] = "2026-05-29 17:00"
    by["A110"]["status_code"] = "TK_Complete"                  # completed...
    by["A110"]["act_end_date"] = "2026-03-30 17:00"            # ...with an actual after the data date
    new = [t for t in tasks if t["task_code"] != "A140"]       # activity deleted
    new.append(task(7, "A160", "Commissioning", dur=60, ee="2026-05-20 17:00"))  # new activity
    rels = [r for r in rels if r[:2] != ("A120", "A130") and "A140" not in r[:2]]
    rels += [("A110", "A130", "PR_FS", 24)]                    # new relationship with 3-day lag
    rels += [("A130", "A160", "PR_FS", -16)]                   # lead
    rels += [("A160", "M900", "PR_FS", 0)]
    return new, rels


class XerToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.old_p = os.path.join(cls.tmp.name, "old.xer")
        cls.new_p = os.path.join(cls.tmp.name, "new.xer")
        t, r = base()
        write_xer(cls.old_p, t, r, "2026-02-27")
        t, r = update()
        write_xer(cls.new_p, t, r, "2026-03-27")
        cls.old, cls.new = xer_tool.Schedule(cls.old_p), xer_tool.Schedule(cls.new_p)
        cls.diff = xer_tool.diff(cls.old, cls.new)
        cls.chk = xer_tool.check(cls.new)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def rows(self, res, section):
        key = next(k for k in res if k.startswith(section))
        return res[key][1]

    def codes(self, res, section):
        return {r[0] for r in self.rows(res, section)}

    def test_parse(self):
        self.assertEqual(len(self.old.tasks), 6)
        self.assertEqual(len(self.old.rels), 5)
        self.assertEqual(self.old.data_date, "2026-02-27")

    def test_retroactive_actual(self):
        rows = self.rows(self.diff, "Retroactive")
        self.assertIn(("A100", "Mobilize", "actual start", "2026-01-05 08:00", "2026-01-12 08:00", "+7"), rows)

    def test_removed_and_added_activities(self):
        self.assertEqual(self.codes(self.diff, "Activities removed"), {"A140"})
        self.assertEqual(self.codes(self.diff, "Activities added"), {"A160"})

    def test_duration_and_noprogress(self):
        self.assertIn("A120", self.codes(self.diff, "Duration (original)"))
        self.assertEqual(self.codes(self.diff, "Remaining duration cut"), {"A120"})

    def test_constraint_added(self):
        self.assertIn("A130", self.codes(self.diff, "Constraint changes"))

    def test_milestone_shift(self):
        rows = self.rows(self.diff, "Milestone date shifts")
        self.assertTrue(any(r[0] == "M900" and r[5] == "+29" for r in rows), rows)

    def test_relationships(self):
        removed = {(r[0], r[1]) for r in self.rows(self.diff, "Relationships removed")}
        self.assertIn(("A120", "A130"), removed)
        added = {(r[0], r[1]): r[3] for r in self.rows(self.diff, "Relationships added")}
        self.assertEqual(added[("A110", "A130")], 3.0)

    def test_status_regression_none(self):
        self.assertEqual(self.rows(self.diff, "Status regressions"), [])

    def test_out_of_sequence(self):
        self.assertIn("A130", self.codes(self.chk, "Out-of-sequence"))

    def test_future_actual_and_lead_and_mandatory(self):
        self.assertIn("A110", self.codes(self.chk, "Actual dates after"))
        self.assertTrue(any(r[3] == -2.0 for r in self.rows(self.chk, "Leads")))
        self.assertTrue(any(r[0] == "A130" and r[4] == "MANDATORY" for r in self.rows(self.chk, "Constraints")))

    def test_regression_detected(self):
        t, r = base()
        t[0]["status_code"] = "TK_NotStart"          # A100 complete -> not started
        p = os.path.join(self.tmp.name, "reg.xer")
        write_xer(p, t, r, "2026-03-27")
        res = xer_tool.diff(self.old, xer_tool.Schedule(p))
        self.assertIn("A100", self.codes(res, "Status regressions"))

    def test_status_inconsistencies(self):
        issues = {(r[0], r[2]) for r in self.rows(self.chk, "Status inconsistencies")}
        self.assertTrue(any(c == "A100" and "after actual finish" in i for c, i in issues), issues)
        self.assertTrue(any(c == "A110" and "remaining duration" in i for c, i in issues), issues)

    def test_no_false_positives_on_identical_files(self):
        res = xer_tool.diff(self.old, xer_tool.Schedule(self.old_p))
        self.assertEqual({k: v for k, (h, v) in res.items() if v}, {})

    def test_multiproject_selection(self):
        with self.assertRaises(SystemExit):
            xer_tool.Schedule(self.old_p, project="NOPE")


if __name__ == "__main__":
    unittest.main()
