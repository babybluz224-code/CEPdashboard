#!/usr/bin/env python3
"""Local document knowledge base: index contract and project files, then search them.

Reads .docx, .pptx, .xlsx/.xlsm, .csv, .pdf (needs `pdftotext`), .txt and .md into a
SQLite full-text index (default case/kb.sqlite, gitignored). Every piece of text keeps
its document and location (clause, slide, sheet rows, page), so answers can quote exactly.
Standard library only (plus the `pdftotext` command for PDFs). No network, no AI.

  kb.py ingest PATH [PATH...]        add or refresh files/folders (unchanged files are skipped;
                                     files deleted from a folder are removed from the index)
  kb.py stale   PATH [PATH...]       list new, changed and missing files without changing the index
  kb.py search  "words" [--phrase|--any] [--doc NAME] [--limit N] [--full]
  kb.py show    DOC LOCATION         print the full text at a location (e.g. 'Contract.docx' '4.1')
  kb.py list                         documents, status and chunk counts

Word notes: automatic clause numbering is reconstructed (verify against Word); tracked
changes appear inline as [+inserted+] and [-deleted-]; comments are indexed separately.
Excel notes: cached values are indexed, formulas shown as [formula: ...], hidden sheets and
rows are flagged, dates appear as Excel serial numbers. Legacy .doc/.ppt/.xls are not read:
open in Office and Save As .docx/.pptx/.xlsx.
"""
import argparse
import csv
import hashlib
import io
import os
import posixpath
import re
import shutil
import sqlite3
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
SEP = " · "
CAP = 2500
ARTICLE_RE = re.compile(r"^\s*(ARTICLE|Article|SECTION|Section|EXHIBIT|Exhibit|APPENDIX|Appendix|SCHEDULE|Schedule)\s+[A-Z0-9IVX][A-Z0-9IVX\-\.]*")
NUM_RE = re.compile(r"^\s*(\d+(?:\.\d+)+|\d+\.)\s+\S")
KINDS = {".docx": "docx", ".docm": "docx", ".pptx": "pptx", ".pptm": "pptx", ".xlsx": "xlsx",
         ".xlsm": "xlsx", ".csv": "csv", ".tsv": "csv", ".pdf": "pdf", ".txt": "text", ".md": "text"}
LEGACY = {".doc", ".ppt", ".xls"}


def q(ns, tag):
    return f"{{{ns}}}{tag}"


def clause_key(text):
    """'4.1 Retainage...' -> '4.1'; 'ARTICLE 4 PAYMENT' -> 'ARTICLE 4'; else ''."""
    m = NUM_RE.match(text)
    if m:
        return m.group(1)
    m = ARTICLE_RE.match(text)
    return m.group(0).strip() if m else ""


def rels(z, part):
    d, f = posixpath.split(part)
    rp = posixpath.join(d, "_rels", f + ".rels")
    if rp not in z.namelist():
        return {}
    out = {}
    for r in ET.fromstring(z.read(rp)):
        out[r.get("Id")] = (r.get("Type", ""), r.get("Target", ""))
    return out


def resolve(base_part, target):
    if target.startswith("/"):
        return target[1:]
    return posixpath.normpath(posixpath.join(posixpath.dirname(base_part), target))


def assemble(items, cap=CAP):
    """items: (is_start, location, text) -> [(location, text)], split at paragraph bounds."""
    out, loc, buf = [], None, []

    def flush(more=False):
        nonlocal buf
        if buf:
            out.append((loc, "\n".join(buf)))
        buf = []

    for is_start, location, text in items:
        if not text.strip():
            continue
        if is_start or loc is None:
            flush()
            loc = location
        elif sum(len(b) for b in buf) + len(text) > cap:
            flush()
            if not loc.endswith("(cont.)"):
                loc = loc + " (cont.)"
        buf.append(text)
    flush()
    return out


# ---------------------------------------------------------------- Word
def _alpha(n):
    return chr(65 + (n - 1) % 26) * ((n - 1) // 26 + 1)


def _roman(n):
    vals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"),
            (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    s = ""
    for v, r in vals:
        while n >= v:
            s, n = s + r, n - v
    return s


def fmt_num(n, fmt):
    return {"decimal": str(n), "decimalZero": "%02d" % n, "lowerLetter": _alpha(n).lower(),
            "upperLetter": _alpha(n), "lowerRoman": _roman(n).lower(), "upperRoman": _roman(n)}.get(fmt, "")


class Numberer:
    def __init__(self, z):
        self.abstract, self.nums, self.counters, self.style_num = {}, {}, {}, {}
        names = z.namelist()
        if "word/numbering.xml" in names:
            root = ET.fromstring(z.read("word/numbering.xml"))
            for a in root.findall(q(W, "abstractNum")):
                lv = {}
                for l in a.findall(q(W, "lvl")):
                    f, t, st = l.find(q(W, "numFmt")), l.find(q(W, "lvlText")), l.find(q(W, "start"))
                    lv[int(l.get(q(W, "ilvl")))] = (f.get(q(W, "val")) if f is not None else "decimal",
                                                    t.get(q(W, "val")) if t is not None else "",
                                                    int(st.get(q(W, "val"))) if st is not None else 1)
                self.abstract[a.get(q(W, "abstractNumId"))] = lv
            for n in root.findall(q(W, "num")):
                self.nums[n.get(q(W, "numId"))] = n.find(q(W, "abstractNumId")).get(q(W, "val"))
        if "word/styles.xml" in names:
            for st in ET.fromstring(z.read("word/styles.xml")).findall(q(W, "style")):
                np_ = st.find(f"{q(W, 'pPr')}/{q(W, 'numPr')}")
                if np_ is not None:
                    nid, il = np_.find(q(W, "numId")), np_.find(q(W, "ilvl"))
                    if nid is not None:
                        self.style_num[st.get(q(W, "styleId"))] = (
                            nid.get(q(W, "val")), int(il.get(q(W, "val"))) if il is not None else 0)

    def label(self, p):
        ppr = p.find(q(W, "pPr"))
        if ppr is None:
            return "", None
        np_, nid, il = ppr.find(q(W, "numPr")), None, 0
        if np_ is not None:
            n, i = np_.find(q(W, "numId")), np_.find(q(W, "ilvl"))
            nid = n.get(q(W, "val")) if n is not None else None
            il = int(i.get(q(W, "val"))) if i is not None else 0
        else:
            ps = ppr.find(q(W, "pStyle"))
            if ps is not None and ps.get(q(W, "val")) in self.style_num:
                nid, il = self.style_num[ps.get(q(W, "val"))]
        if not nid or nid == "0" or nid not in self.nums:
            return "", None
        aid = self.nums[nid]
        lv = self.abstract.get(aid, {})
        if il not in lv:
            return "", None
        c = self.counters.setdefault(aid, {})
        fmt, txt, start = lv[il]
        c[il] = c.get(il, start - 1) + 1
        for k in [k for k in c if k > il]:
            del c[k]
        if fmt in ("bullet", "none"):
            return "", il

        def sub(m):
            k = int(m.group(1)) - 1
            f, _, st = lv.get(k, ("decimal", "", 1))
            return fmt_num(c.get(k, st), f)

        return re.sub(r"%(\d)", sub, txt).strip(), il


def ptext(node):
    s = []
    for ch in node:
        t = ch.tag
        if t == q(W, "r"):
            for x in ch:
                if x.tag in (q(W, "t"), q(W, "delText")):
                    s.append(x.text or "")
                elif x.tag == q(W, "tab"):
                    s.append("\t")
                elif x.tag in (q(W, "br"), q(W, "cr")):
                    s.append("\n")
                elif x.tag == q(W, "commentReference"):
                    s.append(f"[comment {x.get(q(W, 'id'))}]")
        elif t == q(W, "ins"):
            inner = ptext(ch)
            s.append(f"[+{inner}+]" if inner.strip() else inner)
        elif t == q(W, "del"):
            inner = ptext(ch)
            s.append(f"[-{inner}-]" if inner.strip() else inner)
        elif t in (q(W, "hyperlink"), q(W, "smartTag"), q(W, "sdt"), q(W, "sdtContent"), q(W, "fldSimple")):
            s.append(ptext(ch))
    return "".join(s)


def _blocks(parent):
    for ch in parent:
        if ch.tag in (q(W, "p"), q(W, "tbl")):
            yield ch
        elif ch.tag in (q(W, "sdt"), q(W, "sdtContent")):
            c = ch.find(q(W, "sdtContent")) if ch.tag == q(W, "sdt") else ch
            if c is not None:
                yield from _blocks(c)


def extract_docx(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        num = Numberer(z)
        comments = []
        if "word/comments.xml" in z.namelist():
            for c in ET.fromstring(z.read("word/comments.xml")).iter(q(W, "comment")):
                comments.append((c.get(q(W, "id")), c.get(q(W, "author")) or "",
                                 " ".join(ptext(p) for p in c.iter(q(W, "p")))))
    items = []
    for blk in _blocks(root.find(q(W, "body"))):
        if blk.tag == q(W, "tbl"):
            for tr in blk.iter(q(W, "tr")):
                cells = [" ".join(ptext(p) for p in tc.iter(q(W, "p"))).strip() for tc in tr.findall(q(W, "tc"))]
                if any(cells):
                    items.append((False, "", "[table] " + " | ".join(cells)))
            continue
        text = ptext(blk).strip()
        label, lvl = num.label(blk)
        if not text and not label:
            continue
        ppr = blk.find(q(W, "pPr"))
        ps = ppr.find(q(W, "pStyle")).get(q(W, "val")) if ppr is not None and ppr.find(q(W, "pStyle")) is not None else ""
        typed = clause_key(text)
        start = bool(label and lvl is not None and lvl <= 1) or ps.lower().startswith(("heading", "title")) or bool(typed)
        key = label or typed
        loc = (key + SEP + text[:50]).strip(SEP) if key else text[:60]
        items.append((start, loc, (label + " " + text).strip()))
    out = assemble(items)
    for cid, author, text in comments:
        out.append((f"comment {cid}", f"Comment by {author}: {text}".strip()))
    return out


# ---------------------------------------------------------------- PowerPoint
def _a_texts(el, out):
    if el.tag == q(A, "tbl"):
        for tr in el.iter(q(A, "tr")):
            cells = ["".join(t.text or "" for t in tc.iter(q(A, "t"))) for tc in tr.findall(q(A, "tc"))]
            if any(c.strip() for c in cells):
                out.append("[table] " + " | ".join(cells))
        return
    if el.tag == q(A, "p"):
        t = "".join(x.text or "" for x in el.iter(q(A, "t"))).strip()
        if t:
            out.append(t)
        return
    for ch in el:
        _a_texts(ch, out)


def extract_pptx(path):
    out = []
    with zipfile.ZipFile(path) as z:
        pres = "ppt/presentation.xml"
        pr = rels(z, pres)
        lst = ET.fromstring(z.read(pres)).find(q(P, "sldIdLst"))
        order = [resolve(pres, pr[s.get(q(R, "id"))][1]) for s in (lst if lst is not None else [])]
        for n, part in enumerate(order, 1):
            texts = []
            _a_texts(ET.fromstring(z.read(part)), texts)
            title = texts[0][:50] if texts else ""
            out.append((f"slide {n}" + (SEP + title if title else ""), "\n".join(texts)))
            for typ, tgt in rels(z, part).values():
                if typ.endswith("/notesSlide"):
                    nt = []
                    _a_texts(ET.fromstring(z.read(resolve(part, tgt))), nt)
                    nt = [t for t in nt if not t.isdigit()]
                    if nt:
                        out.append((f"slide {n} notes", "\n".join(nt)))
    return [(l, t) for l, t in out if t.strip()]


# ---------------------------------------------------------------- Excel / CSV
def _col(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n


def _row_chunks(name_suffix, rows, block=25):
    """rows: [(rownum, text)] -> chunks of `block` rows."""
    out = []
    for i in range(0, len(rows), block):
        part = rows[i:i + block]
        out.append((f"{name_suffix}rows {part[0][0]}-{part[-1][0]}", "\n".join(t for _, t in part)))
    return out


def extract_xlsx(path):
    out = []
    with zipfile.ZipFile(path) as z:
        wbp = "xl/workbook.xml"
        wr = rels(z, wbp)
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(q(S, "si")):
                shared.append("".join(t.text or "" for t in si.iter(q(S, "t"))))
        for sh in ET.fromstring(z.read(wbp)).find(q(S, "sheets")):
            name, state = sh.get("name"), sh.get("state", "visible")
            part = resolve(wbp, wr[sh.get(q(R, "id"))][1])
            tag = " (hidden sheet)" if state != "visible" else ""
            rows = []
            for row in ET.fromstring(z.read(part)).iter(q(S, "row")):
                cells = []
                for c in sorted(row.findall(q(S, "c")), key=lambda c: _col(c.get("r"))):
                    t, v, f = c.get("t"), c.find(q(S, "v")), c.find(q(S, "f"))
                    if t == "inlineStr":
                        val = "".join(x.text or "" for x in c.iter(q(S, "t")))
                    elif v is None or v.text is None:
                        val = ""
                    elif t == "s":
                        val = shared[int(v.text)]
                    elif t == "b":
                        val = "TRUE" if v.text == "1" else "FALSE"
                    else:
                        val = v.text
                    if f is not None and (f.text or "").strip():
                        val = f"{val} [formula: ={f.text}]"
                    if val != "":
                        cells.append(f"{c.get('r')}: {val}")
                if cells:
                    hid = " [hidden row]" if row.get("hidden") == "1" else ""
                    rows.append((int(row.get("r")), " | ".join(cells) + hid))
            out += _row_chunks(f"{name}!" if not tag else f"{name}{tag}!", rows)
    return out


def extract_csv(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    try:
        d = csv.Sniffer().sniff(text[:4096], delimiters=",\t;|")
    except csv.Error:
        d = csv.excel
    rows = [(i, " | ".join(c for c in r)) for i, r in enumerate(csv.reader(io.StringIO(text), d), 1) if any(c.strip() for c in r)]
    return _row_chunks("", rows)


# ---------------------------------------------------------------- PDF / text
def extract_pdf(path):
    if not shutil.which("pdftotext"):
        raise RuntimeError("pdftotext not found (install poppler-utils / Xpdf tools) to read PDFs")
    txt = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, errors="replace").stdout
    items = []
    for pn, page in enumerate(txt.split("\f"), 1):
        if not page.strip():
            continue
        first = True
        for line in page.splitlines():
            if not line.strip():
                continue
            key = clause_key(line)
            if first or key:
                items.append((True, f"p.{pn}" + (SEP + key if key else ""), line.strip()))
                first = False
            else:
                items.append((False, "", line.strip()))
    return assemble(items)


def extract_text(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    items = []
    for i, line in enumerate(text.splitlines(), 1):
        key = clause_key(line)
        items.append((bool(key) or i == 1, key or f"line {i}", line))
    return assemble(items)


EXTRACT = {"docx": extract_docx, "pptx": extract_pptx, "xlsx": extract_xlsx, "csv": extract_csv,
           "pdf": extract_pdf, "text": extract_text}


# ---------------------------------------------------------------- database
def connect(dbpath):
    d = os.path.dirname(os.path.abspath(dbpath))
    os.makedirs(d, exist_ok=True)
    db = sqlite3.connect(dbpath)
    db.execute("create table if not exists docs(id integer primary key, path text unique, kind text, sha256 text,"
               " size integer, ingested text, status text, note text)")
    db.execute("create virtual table if not exists chunks using fts5(text, doc unindexed, location unindexed,"
               " doc_id unindexed, seq unindexed, tokenize='porter unicode61')")
    return db


def display(path):
    rel = os.path.relpath(path)
    return path if rel.startswith("..") else rel


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def walk(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if not d.startswith("."))
                for f in sorted(files):
                    if not f.startswith(("~$", ".")):
                        yield os.path.join(root, f)
        elif os.path.exists(p):
            yield p
        else:
            print(f"not found: {p}", file=sys.stderr)


def ingest_file(db, path):
    ext = os.path.splitext(path)[1].lower()
    if ext not in KINDS and ext not in LEGACY:
        return None
    name, h = display(path), sha(path)
    row = db.execute("select id, sha256 from docs where path=?", (name,)).fetchone()
    if row and row[1] == h:
        return "unchanged"
    if row:
        db.execute("delete from chunks where doc_id=?", (row[0],))
        db.execute("delete from docs where id=?", (row[0],))
    status, note, chunks = "ok", "", []
    if ext in LEGACY:
        status, note = "unsupported", "legacy binary format: open in Office and Save As .docx/.pptx/.xlsx"
    else:
        try:
            chunks = EXTRACT[KINDS[ext]](path)
        except Exception as e:  # keep going on one bad file
            status, note = "error", f"{type(e).__name__}: {e}"
        if status == "ok" and not chunks:
            status = "no text layer" if ext == ".pdf" else "empty"
            note = "scanned PDF: OCR needed before it can be searched" if ext == ".pdf" else ""
    cur = db.execute("insert into docs(path, kind, sha256, size, ingested, status, note) values(?,?,?,?,?,?,?)",
                     (name, KINDS.get(ext, ext), h, os.path.getsize(path), datetime.now().isoformat(timespec="seconds"),
                      status, note))
    for i, (loc, text) in enumerate(chunks):
        db.execute("insert into chunks(text, doc, location, doc_id, seq) values(?,?,?,?,?)", (text, name, loc, cur.lastrowid, i))
    db.commit()
    return f"{status}" + (f" ({len(chunks)} chunks)" if status == "ok" else f" - {note}")


def fts_query(text, mode):
    toks = [t for t in re.split(r"\s+", text.strip()) if t]
    quoted = ['"' + t.replace('"', '""') + '"' for t in toks]
    if mode == "phrase":
        return '"' + text.replace('"', '""').strip() + '"'
    return (" OR " if mode == "any" else " ").join(quoted)


def prune(db, folder):
    """Drop indexed documents under `folder` whose files no longer exist (so superseded text stops matching)."""
    root = display(os.path.abspath(folder)).rstrip("/")
    gone = 0
    for did, name in db.execute("select id, path from docs").fetchall():
        if (root == "." or name.startswith(root + "/")) and not os.path.exists(name):
            db.execute("delete from chunks where doc_id=?", (did,))
            db.execute("delete from docs where id=?", (did,))
            print(f"{name}: removed (file no longer exists)")
            gone += 1
    db.commit()
    return gone


def cmd_ingest(a):
    db = connect(a.db)
    n = 0
    for p in walk(a.paths):
        r = ingest_file(db, p)
        if r is not None:
            print(f"{display(p)}: {r}")
            n += 1
    for p in a.paths:
        if os.path.isdir(p):
            n += prune(db, p)
    print(f"{n} change(s)/file(s) checked; index: {a.db}")


def cmd_stale(a):
    db = connect(a.db)
    seen = set()
    for p in walk(a.paths):
        ext = os.path.splitext(p)[1].lower()
        if ext not in KINDS and ext not in LEGACY:
            continue
        name = display(p)
        seen.add(name)
        row = db.execute("select sha256 from docs where path=?", (name,)).fetchone()
        if row is None:
            print(f"NEW      {name}")
        elif row[0] != sha(p):
            print(f"CHANGED  {name}")
    roots = [display(os.path.abspath(p)) for p in a.paths if os.path.isdir(p)]
    for (name,) in db.execute("select path from docs"):
        if name not in seen and any(name.startswith(r.rstrip("/") + "/") or r == "." for r in roots) and not os.path.exists(name):
            print(f"MISSING  {name}")
    print("done (nothing changed)")


def cmd_search(a):
    db = connect(a.db)
    mode = "phrase" if a.phrase else "any" if a.any else "all"
    sql = ("select doc, location, " + ("text" if a.full else "snippet(chunks, 0, '>>', '<<', '…', 30)")
           + " from chunks where chunks match ? " + ("and doc like ? " if a.doc else "") + "order by rank limit ?")
    args = [fts_query(a.query, mode)] + ([f"%{a.doc}%"] if a.doc else []) + [a.limit]
    rows = db.execute(sql, args).fetchall()
    if not rows:
        print("no matches (try --any, fewer words, or check `kb.py list` for unread files)")
    for i, (doc, loc, text) in enumerate(rows, 1):
        print(f"[{i}] {doc} | {loc}\n    " + text.replace("\n", "\n    "))


def cmd_show(a):
    db = connect(a.db)
    rows = db.execute("select doc, location, text from chunks where doc like ? and (location=? or location like ? or location like ?)"
                      " order by doc_id, seq", (f"%{a.doc}%", a.location, a.location + SEP + "%", a.location + " %")).fetchall()
    if not rows:
        print("no such location; use `search` to find it")
    for doc, loc, text in rows:
        print(f"== {doc} | {loc}\n{text}\n")


def cmd_list(a):
    db = connect(a.db)
    for path, kind, status, note, n in db.execute(
            "select d.path, d.kind, d.status, d.note, (select count(*) from chunks c where c.doc_id=d.id) from docs d order by d.path"):
        print(f"{path} [{kind}] {status}" + (f" ({n} chunks)" if status == "ok" else f" - {note}"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.environ.get("KB_DB", "case/kb.sqlite"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n, f in (("ingest", cmd_ingest), ("stale", cmd_stale)):
        p = sub.add_parser(n)
        p.add_argument("paths", nargs="+")
        p.set_defaults(fn=f)
    p = sub.add_parser("search")
    p.add_argument("query")
    p.add_argument("--phrase", action="store_true")
    p.add_argument("--any", action="store_true")
    p.add_argument("--doc")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--full", action="store_true")
    p.set_defaults(fn=cmd_search)
    p = sub.add_parser("show")
    p.add_argument("doc")
    p.add_argument("location")
    p.set_defaults(fn=cmd_show)
    p = sub.add_parser("list")
    p.set_defaults(fn=cmd_list)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
