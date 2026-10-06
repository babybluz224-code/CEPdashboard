"""Build minimal .docx/.pptx/.xlsx/.pdf files for tests. Standard library only."""
import zipfile
from xml.sax.saxutils import escape

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
REL = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
OD = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
HDR = '<?xml version="1.0" encoding="UTF-8"?>'


def _zip(path, files):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, c in files.items():
            z.writestr(n, c)


def _rels(items):
    return HDR + f'<Relationships xmlns="{PKG}">' + "".join(
        f'<Relationship Id="{i}" Type="{t}" Target="{g}"/>' for i, t, g in items) + "</Relationships>"


def run(t):
    return f'<w:r><w:t xml:space="preserve">{escape(t)}</w:t></w:r>'


def para(inner, style=None, num=None):
    ppr = ""
    if style or num:
        ppr = "<w:pPr>" + (f'<w:pStyle w:val="{style}"/>' if style else "")
        if num:
            ppr += f'<w:numPr><w:ilvl w:val="{num[1]}"/><w:numId w:val="{num[0]}"/></w:numPr>'
        ppr += "</w:pPr>"
    return f"<w:p>{ppr}{inner}</w:p>"


def write_docx(path, body_xml, comments=None):
    numbering = HDR + f"<w:numbering {W}><w:abstractNum w:abstractNumId=\"0\">" \
        '<w:lvl w:ilvl="0"><w:start w:val="4"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1"/></w:lvl>' \
        '<w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1.%2"/></w:lvl>' \
        '<w:lvl w:ilvl="2"><w:start w:val="1"/><w:numFmt w:val="lowerLetter"/><w:lvlText w:val="(%3)"/></w:lvl>' \
        '</w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>'
    files = {
        "[Content_Types].xml": HDR + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="application/xml"/><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/></Types>',
        "_rels/.rels": _rels([("rId1", OD + "/officeDocument", "word/document.xml")]),
        "word/document.xml": HDR + f"<w:document {W} {REL}><w:body>{body_xml}</w:body></w:document>",
        "word/numbering.xml": numbering,
    }
    if comments:
        files["word/comments.xml"] = HDR + f"<w:comments {W}>" + "".join(
            f'<w:comment w:id="{i}" w:author="{escape(a)}"><w:p>{run(t)}</w:p></w:comment>' for i, a, t in comments) + "</w:comments>"
    _zip(path, files)


def write_pptx(path, slides, order=None, notes=None):
    """slides: {n: [texts]}; order: list of slide numbers as shown; notes: {n: text}."""
    order = order or sorted(slides)
    pres_rels = [(f"rId{n}", OD + "/slide", f"slides/slide{n}.xml") for n in slides]
    files = {
        "[Content_Types].xml": HDR + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/></Types>',
        "_rels/.rels": _rels([("rId1", OD + "/officeDocument", "ppt/presentation.xml")]),
        "ppt/presentation.xml": HDR + '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        f'{REL}><p:sldIdLst>' + "".join(f'<p:sldId id="{255 + n}" r:id="rId{n}"/>' for n in order) + "</p:sldIdLst></p:presentation>",
        "ppt/_rels/presentation.xml.rels": _rels(pres_rels),
    }
    ns = 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
    for n, texts in slides.items():
        body = "".join(f"<a:p><a:r><a:t>{escape(t)}</a:t></a:r></a:p>" for t in texts)
        files[f"ppt/slides/slide{n}.xml"] = HDR + f"<p:sld {ns}><p:cSld><p:spTree><p:sp><p:txBody>{body}</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
        if notes and n in notes:
            files[f"ppt/slides/_rels/slide{n}.xml.rels"] = _rels([("rId1", OD + "/notesSlide", f"../notesSlides/notesSlide{n}.xml")])
            files[f"ppt/notesSlides/notesSlide{n}.xml"] = HDR + f"<p:notes {ns}><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>{escape(notes[n])}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:notes>"
    _zip(path, files)


def write_xlsx(path, sheets):
    """sheets: [(name, rows, hidden)]; row cells are values or (value, formula) tuples; row may be ('hidden', cells)."""
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    files = {
        "[Content_Types].xml": HDR + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/></Types>',
        "_rels/.rels": _rels([("rId1", OD + "/officeDocument", "xl/workbook.xml")]),
    }
    wb, wr = [], []
    for i, (name, rows, hidden) in enumerate(sheets, 1):
        out = []
        for r, row in enumerate(rows, 1):
            hid = ""
            if isinstance(row, tuple) and row and row[0] == "hidden":
                hid, row = ' hidden="1"', row[1]
            cs = ""
            for c, v in enumerate(row):
                ref = f"{chr(65 + c)}{r}"
                if v is None or v == "":
                    continue
                f = None
                if isinstance(v, tuple):
                    v, f = v
                fx = f"<f>{escape(f)}</f>" if f else ""
                if isinstance(v, (int, float)):
                    cs += f'<c r="{ref}">{fx}<v>{v}</v></c>'
                else:
                    cs += f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(v))}</t></is></c>'
            out.append(f'<row r="{r}"{hid}>{cs}</row>')
        files[f"xl/worksheets/sheet{i}.xml"] = HDR + f'<worksheet xmlns="{ns}"><sheetData>{"".join(out)}</sheetData></worksheet>'
        st = ' state="hidden"' if hidden else ""
        wb.append(f'<sheet name="{escape(name)}" sheetId="{i}"{st} r:id="rId{i}"/>')
        wr.append((f"rId{i}", OD + "/worksheet", f"worksheets/sheet{i}.xml"))
    files["xl/workbook.xml"] = HDR + f'<workbook xmlns="{ns}" {REL}><sheets>{"".join(wb)}</sheets></workbook>'
    files["xl/_rels/workbook.xml.rels"] = _rels(wr)
    _zip(path, files)


def write_pdf(path, pages):
    """pages: list of list of text lines (an empty list makes a page with no text)."""
    objs = {}
    n_pages = len(pages)
    objs[1] = "<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n_pages))
    objs[2] = f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>"
    objs[3] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    for i, lines in enumerate(pages):
        pn, cn = 4 + 2 * i, 5 + 2 * i
        stream = "BT /F1 11 Tf 14 TL 50 740 Td " + " T* ".join(
            "(" + l.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") Tj" for l in lines) + " ET" if lines else ""
        objs[pn] = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {cn} 0 R /Resources << /Font << /F1 3 0 R >> >> >>"
        objs[cn] = f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream"
    out, offs = b"%PDF-1.4\n", {}
    for n in sorted(objs):
        offs[n] = len(out)
        out += f"{n} 0 obj\n{objs[n]}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for n in sorted(objs):
        out += f"{offs[n]:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    with open(path, "wb") as fh:
        fh.write(out)
