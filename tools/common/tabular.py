"""Minimal CSV/XLSX table reader and cell parsers. Standard library only.

read_table(path, sheet=None) -> list of rows (each a list of str).
XLSX limits: cell values only (no formulas evaluated; cached values are used), dates
come back as Excel serial numbers (use excel_date), merged cells are not expanded.
"""
import csv
import io
import re
import zipfile
from datetime import date, timedelta
import xml.etree.ElementTree as ET

M = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _col(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def xlsx_sheets(path):
    """Return [(sheet name, zip path)] in workbook order."""
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        relmap = {r.get("Id"): r.get("Target") for r in rels}
        out = []
        for s in wb.find(f"{{{M}}}sheets"):
            t = relmap[s.get(f"{{{R}}}id")].lstrip("/")
            out.append((s.get("name"), t if t.startswith("xl/") else "xl/" + t))
        return out


def read_xlsx(path, sheet=None):
    sheets = xlsx_sheets(path)
    if sheet is None:
        name, target = sheets[0]
    else:
        match = [s for s in sheets if s[0] == sheet]
        if not match:
            raise ValueError(f"sheet {sheet!r} not found; available: {[s[0] for s in sheets]}")
        name, target = match[0]
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(f"{{{M}}}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{M}}}t")))
        root = ET.fromstring(z.read(target))
    rows = []
    for row in root.iter(f"{{{M}}}row"):
        cells = {}
        for c in row.findall(f"{{{M}}}c"):
            t = c.get("t")
            v = c.find(f"{{{M}}}v")
            if t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter(f"{{{M}}}t"))
            elif v is None or v.text is None:
                val = ""
            elif t == "s":
                val = shared[int(v.text)]
            elif t == "b":
                val = "TRUE" if v.text == "1" else "FALSE"
            else:
                val = v.text
            cells[_col(c.get("r"))] = val
        if cells:
            width = max(cells) + 1
            rows.append([cells.get(i, "") for i in range(width)])
        else:
            rows.append([])
    return rows


def read_csv(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",\t;|")
    except csv.Error:
        dialect = csv.excel
    return [row for row in csv.reader(io.StringIO(text), dialect)]


def read_table(path, sheet=None):
    p = path.lower()
    if p.endswith((".xlsx", ".xlsm")):
        return read_xlsx(path, sheet)
    if p.endswith((".csv", ".tsv", ".txt")):
        return read_csv(path)
    raise ValueError(f"unsupported file type: {path} (use .xlsx, .xlsm or .csv)")


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def find_header(rows, keywords, min_hits=2, scan=40):
    """Index of the first row (within the first `scan`) with >= min_hits keyword matches."""
    keys = [norm(k) for k in keywords]
    for i, row in enumerate(rows[:scan]):
        cells = [norm(c) for c in row]
        hits = sum(any(k in c for c in cells) for k in keys)
        if hits >= min_hits:
            return i
    return None


def to_number(s):
    """'$1,234.50' -> 1234.5; '(1,234)' -> -1234; '12%' -> 12.0; '' or text -> None."""
    s = (s or "").strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[,$%\s()]", "", s)
    if s.startswith("-"):
        neg, s = True, s[1:]
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def excel_date(v):
    """Excel serial (e.g. '45700') or ISO/US text date -> datetime.date, else None."""
    s = (v or "").strip()
    if not s:
        return None
    try:
        n = float(s)
        if 20000 < n < 80000:
            return date(1899, 12, 30) + timedelta(days=int(n))
        return None
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d-%b-%Y", "%b %d, %Y", "%Y-%m-%d %H:%M"):
        try:
            from datetime import datetime
            return datetime.strptime(s[:19] if "%H" in fmt else s, fmt).date()
        except ValueError:
            continue
    return None
