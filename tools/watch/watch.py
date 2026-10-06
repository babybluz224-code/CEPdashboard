#!/usr/bin/env python3
"""Watchdog helpers: compare document versions and check document metadata.

  watch.py diff OLD NEW [--out report.md] [--max 200]   what changed between two versions
  watch.py meta FILE[=CLAIMED_DATE] ... [--out report.md]   authorship/date details and flags

Reads .docx, .pptx, .xlsx, .csv, .txt and text-layer .pdf (via the kb reader). Standard
library only (plus `pdftotext`/`pdfinfo` for PDFs). Local, no network, no AI.
A difference or an odd date is a question to ask, not proof of intent: metadata can be
changed, wiped or reset by copying, converting or exporting a file.
"""
import argparse
import difflib
import os
import re
import shutil
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kb"))
import kb  # noqa: E402


def lines_of(path):
    ext = os.path.splitext(path)[1].lower()
    if ext not in kb.KINDS:
        raise SystemExit(f"{path}: unsupported type (use docx, pptx, xlsx, csv, txt, pdf)")
    out = []
    for loc, text in kb.EXTRACT[kb.KINDS[ext]](path):
        for ln in text.splitlines():
            if ln.strip():
                out.append((loc, ln.strip()))
    return out


def inline(a, b):
    ta, tb = a.split(), b.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ta, tb, autojunk=False).get_opcodes():
        if op == "equal":
            out.append(" ".join(ta[i1:i2]))
        else:
            if i2 > i1:
                out.append("[-" + " ".join(ta[i1:i2]) + "-]")
            if j2 > j1:
                out.append("[+" + " ".join(tb[j1:j2]) + "+]")
    return " ".join(out)


def nums(s):
    return re.findall(r"\d[\d,\.]*", s)


LABEL = re.compile(r"^\s*(\d+(?:\.\d+)*\.?|\([a-zA-Z0-9]+\))\s+")


def unlabelled(s):
    return LABEL.sub("", s, count=1)


def diff(old, new):
    a, b = lines_of(old), lines_of(new)
    ta, tb = [t for _, t in a], [t for _, t in b]
    changed, removed, added = [], [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ta, tb, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        olds, news = list(range(i1, i2)), list(range(j1, j2))
        used = set()
        for i in olds:                                  # pair similar lines inside a replaced block
            best, score = None, 0.6
            for j in news:
                if j in used:
                    continue
                r = difflib.SequenceMatcher(None, ta[i], tb[j]).ratio()
                if r > score:
                    best, score = j, r
            if best is None:
                removed.append((a[i][0], ta[i]))
            else:
                used.add(best)
                if unlabelled(ta[i]) == unlabelled(tb[best]):
                    flag = " (clause renumbered only: check cross-references)"
                else:
                    flag = " (numbers differ)" if nums(ta[i]) != nums(tb[best]) else ""
                changed.append((b[best][0], inline(ta[i], tb[best]) + flag))
        for j in news:
            if j not in used:
                added.append((b[j][0], tb[j]))
    return changed, removed, added


def cmd_diff(args):
    changed, removed, added = diff(args.old, args.new)
    out = [f"# Version comparison\n\nOld: {args.old}  \nNew: {args.new}\n",
           "A change is a question to ask the author, not proof of intent. Inserted or deleted rows can shift "
           "cell references in spreadsheets and show as many changes.\n",
           f"Changed lines: {len(changed)}; removed: {len(removed)}; added: {len(added)}\n"]
    for title, rows in (("Changed", changed), ("Removed", removed), ("Added", added)):
        out.append(f"\n## {title} ({len(rows)})\n")
        for loc, text in rows[:args.max]:
            out.append(f"- **{loc}**: {text}")
        if len(rows) > args.max:
            out.append(f"- ... {len(rows) - args.max} more (use --max)")
    text = "\n".join(out) + "\n"
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"Wrote {args.out}: {len(changed)} changed, {len(removed)} removed, {len(added)} added")
    else:
        print(text)


# ---------------------------------------------------------------- metadata
def local(tag):
    return tag.rsplit("}", 1)[-1]


def props(z, name):
    if name not in z.namelist():
        return None
    return {local(c.tag): (c.text or "").strip() for c in ET.fromstring(z.read(name))}


def pdate(s):
    m = re.match(r"\s*(\d{4})-(\d{2})-(\d{2})", s or "")
    return date(int(m[1]), int(m[2]), int(m[3])) if m else None


def meta_ooxml(path, kind):
    info, notes = {}, []
    with zipfile.ZipFile(path) as z:
        core, app = props(z, "docProps/core.xml"), props(z, "docProps/app.xml")
        if core is None:
            notes.append(("NO METADATA", "docProps/core.xml is missing (stripped, or produced by a conversion tool)"))
        else:
            for k in ("creator", "lastModifiedBy", "revision", "created", "modified", "title"):
                info[k] = core.get(k, "")
        for k in ("Application", "Company", "TotalTime"):
            if app and app.get(k):
                info[k] = app[k]
        if kind == "docx":
            root = ET.fromstring(z.read("word/document.xml"))
            ins, dele = len(list(root.iter(kb.q(kb.W, "ins")))), len(list(root.iter(kb.q(kb.W, "del"))))
            if ins or dele:
                notes.append(("TRACKED CHANGES", f"{ins} insertions and {dele} deletions are still unaccepted in the file"))
            if "word/comments.xml" in z.namelist():
                n = len(list(ET.fromstring(z.read("word/comments.xml")).iter(kb.q(kb.W, "comment"))))
                notes.append(("COMMENTS", f"{n} comment(s) in the file"))
        if kind == "xlsx":
            hidden = [s.get("name") for s in ET.fromstring(z.read("xl/workbook.xml")).find(kb.q(kb.S, "sheets"))
                      if s.get("state", "visible") != "visible"]
            if hidden:
                notes.append(("HIDDEN SHEETS", ", ".join(hidden)))
    return info, notes


def meta_pdf(path):
    info, notes = {}, []
    if not shutil.which("pdfinfo"):
        return info, [("SKIPPED", "pdfinfo not installed (poppler-utils)")]
    txt = subprocess.run(["pdfinfo", "-isodates", path], capture_output=True, text=True, errors="replace").stdout
    for ln in txt.splitlines():
        k, _, v = ln.partition(":")
        if k in ("Title", "Author", "Creator", "Producer", "CreationDate", "ModDate"):
            info[{"CreationDate": "created", "ModDate": "modified", "Author": "creator"}.get(k, k)] = v.strip()
    if not info:
        notes.append(("NO METADATA", "no PDF metadata found"))
    notes.append(("NOTE", "exporting or printing to PDF resets dates, so PDF dates often show only when it was exported"))
    return info, notes


def check_file(spec):
    path, _, claimed = spec.partition("=")
    ext = os.path.splitext(path)[1].lower()
    kind = kb.KINDS.get(ext)
    if kind in ("docx", "pptx", "xlsx"):
        info, notes = meta_ooxml(path, kind)
    elif kind == "pdf":
        info, notes = meta_pdf(path)
    else:
        return path, {}, [("SKIPPED", "no embedded metadata for this file type")], claimed
    cr, mo, cl = pdate(info.get("created")), pdate(info.get("modified")), pdate(claimed)
    if cr and mo and mo < cr:
        notes.append(("MODIFIED BEFORE CREATED", f"modified {mo} is earlier than created {cr} (can happen when a file is copied or converted)"))
    if cl and cr and cr > cl:
        notes.append(("CREATED AFTER CLAIMED DATE", f"file created {cr}, {(cr - cl).days} day(s) after the date it claims ({cl})"))
    if cl and mo and mo > cl:
        notes.append(("EDITED AFTER CLAIMED DATE", f"last modified {mo}, {(mo - cl).days} day(s) after the date it claims ({cl}); ask whether it was reissued"))
    if info.get("creator") and info.get("lastModifiedBy") and info["creator"] != info["lastModifiedBy"]:
        notes.append(("DIFFERENT LAST EDITOR", f"created by {info['creator']}, last saved by {info['lastModifiedBy']}"))
    return path, info, notes, claimed


def cmd_meta(args):
    out = ["# Document metadata check\n",
           "Metadata can be changed, wiped or reset by copying, converting or exporting a file. Treat each flag as a "
           "question to ask, not evidence of intent. Add `=YYYY-MM-DD` to a file name to test it against the date it claims.\n"]
    for spec in args.files:
        path, info, notes, claimed = check_file(spec)
        out.append(f"\n## {path}" + (f" (claims {claimed})" if claimed else "") + "\n")
        for k, v in info.items():
            if v:
                out.append(f"- {k}: {v}")
        out.append("")
        for flag, why in notes:
            out.append(f"- **{flag}**: {why}")
    text = "\n".join(out) + "\n"
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"Wrote {args.out}")
    else:
        print(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("diff")
    p.add_argument("old")
    p.add_argument("new")
    p.add_argument("--out")
    p.add_argument("--max", type=int, default=200)
    p.set_defaults(fn=cmd_diff)
    p = sub.add_parser("meta")
    p.add_argument("files", nargs="+")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_meta)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
