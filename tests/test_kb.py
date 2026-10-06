"""Tests for tools/kb/kb.py using synthetic Office/PDF files."""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "tools", "kb"))
sys.path.insert(0, HERE)
import kb  # noqa: E402
import office_builders as ob  # noqa: E402


def docx_body():
    return "".join([
        ob.para(ob.run("ARTICLE 4 PAYMENT"), style="Heading1"),
        ob.para(ob.run("Payment"), num=(1, 0)),
        ob.para(ob.run("Retainage shall be ten percent (10%) of each payment."), num=(1, 1)),
        ob.para(ob.run("Owner shall pay within thirty (30) days of an approved application."), num=(1, 1)),
        ob.para(ob.run("Cure period is five days."), num=(1, 2)),
        ob.para(ob.run("Changes"), num=(1, 0)),
        ob.para(ob.run("Change orders require a signed writing."), num=(1, 1)),
        ob.para(ob.run("Schedule note: Retainage is ")
                + '<w:del w:id="1" w:author="EPC"><w:r><w:delText>ten</w:delText></w:r></w:del>'
                + '<w:ins w:id="2" w:author="EPC"><w:r><w:t>five</w:t></w:r></w:ins>' + ob.run(" percent.")
                + '<w:r><w:commentReference w:id="0"/></w:r>'),
        "<w:tbl><w:tr><w:tc>" + ob.para(ob.run("Rate")) + "</w:tc><w:tc>" + ob.para(ob.run("Value")) + "</w:tc></w:tr>"
        "<w:tr><w:tc>" + ob.para(ob.run("Liquidated damages")) + "</w:tc><w:tc>" + ob.para(ob.run("$5,000 per day")) + "</w:tc></w:tr></w:tbl>",
    ])


class KbTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.tmp.name, "case")
        os.makedirs(self.dir)
        self.db = kb.connect(os.path.join(self.tmp.name, "kb.sqlite"))
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)

    def tearDown(self):
        os.chdir(self.cwd)
        self.db.close()
        self.tmp.cleanup()

    def f(self, name):
        return os.path.join(self.dir, name)

    def search(self, text, mode="all", doc=None, limit=10):
        sql = "select doc, location, text from chunks where chunks match ? order by rank limit ?"
        return self.db.execute(sql, (kb.fts_query(text, mode), limit)).fetchall()

    def test_docx_numbering_changes_comments_tables(self):
        ob.write_docx(self.f("Contract.docx"), docx_body(), comments=[(0, "Counsel", "Confirm retainage with legal")])
        kb.ingest_file(self.db, self.f("Contract.docx"))
        locs = {l.split(kb.SEP)[0]: t for _, l, t in self.search("retainage")}
        self.assertIn("4.1", locs)                                    # auto-numbered label rebuilt (start at 4)
        self.assertTrue(any(l.startswith("5.1") for _, l, _ in self.search("signed writing")))   # restart at level 1
        self.assertTrue(any("(a) Cure period" in t for _, _, t in self.search("cure period")))
        tracked = [t for _, _, t in self.search("percent")]
        self.assertTrue(any("[-ten-][+five+]" in t for t in tracked), tracked)
        self.assertTrue(any(l == "comment 0" for _, l, _ in self.search("counsel")))
        self.assertTrue(any("$5,000 per day" in t for _, _, t in self.search("liquidated damages")))

    def test_pptx_order_and_notes(self):
        ob.write_pptx(self.f("Deck.pptx"), {1: ["Schedule", "Mechanical completion June"], 2: ["Safety", "No incidents"]},
                      order=[2, 1], notes={1: "EPC says piles done"})
        kb.ingest_file(self.db, self.f("Deck.pptx"))
        locs = [l for _, l, _ in self.db.execute("select doc, location, text from chunks order by seq")]
        self.assertEqual(locs[0].split(kb.SEP)[0], "slide 1")
        self.assertIn("Safety", locs[0])                             # slide2.xml is shown first
        self.assertTrue(any(l == "slide 2 notes" for l in locs))      # notes of the slide shown second
        self.assertTrue(self.search("piles done"))

    def test_xlsx_hidden_sheet_formula_hidden_row(self):
        ob.write_xlsx(self.f("Pay.xlsx"), [
            ("SOV", [["Item", "Amount"], ["Piling", 1000], ("hidden", ["Secret line", 5]), ["Total", (1005, "SUM(B2:B3)")]], False),
            ("Notes", [["Backup rates"]], True)])
        kb.ingest_file(self.db, self.f("Pay.xlsx"))
        texts = [t for _, _, t in self.search("total")]
        self.assertTrue(any("[formula: =SUM(B2:B3)]" in t for t in texts), texts)
        self.assertTrue(any("[hidden row]" in t for _, _, t in self.search("secret")))
        self.assertTrue(any("(hidden sheet)" in l for _, l, _ in self.search("backup rates")))

    def test_pdf_pages_and_scanned(self):
        if not shutil.which("pdftotext"):
            self.skipTest("pdftotext not installed")
        ob.write_pdf(self.f("Exhibit K-2.pdf"), [["Intro text"], ["5.1 Weather days require written notice within 7 days."]])
        ob.write_pdf(self.f("Scan.pdf"), [[]])
        kb.ingest_file(self.db, self.f("Exhibit K-2.pdf"))
        self.assertEqual(kb.ingest_file(self.db, self.f("Scan.pdf")).split(" ")[0], "no")
        hits = self.search("weather notice")
        self.assertTrue(hits and hits[0][1].startswith("p.2"), hits)
        status = self.db.execute("select status from docs where path like '%Scan%'").fetchone()[0]
        self.assertEqual(status, "no text layer")

    def test_hyphen_and_special_characters_in_queries(self):
        ob.write_docx(self.f("A.docx"), ob.para(ob.run("Per Exhibit K-2 the rate is 10% (ten percent).")))
        kb.ingest_file(self.db, self.f("A.docx"))
        for qy in ("K-2", 'Exhibit "K-2"', "10%", "ten (percent)", "rate: AND OR NOT"):
            self.search(qy)   # must not raise
        self.assertTrue(self.search("Exhibit K-2"))

    def test_incremental_ingest_and_stale(self):
        p = self.f("Notes.txt")
        with open(p, "w") as fh:
            fh.write("1. Scope\nWork includes piling.\n")
        self.assertTrue(kb.ingest_file(self.db, p).startswith("ok"))
        self.assertEqual(kb.ingest_file(self.db, p), "unchanged")
        with open(p, "w") as fh:
            fh.write("1. Scope\nWork includes trenching.\n")
        self.assertTrue(kb.ingest_file(self.db, p).startswith("ok"))
        self.assertFalse(self.search("piling"))                      # old text removed
        self.assertTrue(self.search("trenching"))

    def test_legacy_and_corrupt_files_do_not_crash(self):
        with open(self.f("Old.doc"), "wb") as fh:
            fh.write(b"\xd0\xcf\x11\xe0")
        with open(self.f("Bad.docx"), "wb") as fh:
            fh.write(b"not a zip")
        self.assertIn("unsupported", kb.ingest_file(self.db, self.f("Old.doc")))
        self.assertIn("error", kb.ingest_file(self.db, self.f("Bad.docx")))

    def test_clause_key_is_clean(self):
        self.assertEqual(kb.clause_key("2. Pay now"), "2.")
        self.assertEqual(kb.clause_key("4.1 Retainage"), "4.1")
        self.assertEqual(kb.clause_key("ARTICLE 4 PAYMENT"), "ARTICLE 4")
        self.assertEqual(kb.clause_key("10 days after notice"), "")

    def test_deleted_file_is_pruned(self):
        a, b = self.f("a.txt"), self.f("b.txt")
        for p, t in ((a, "1. Scope\nPiling.\n"), (b, "2. Pay\nNet 30.\n")):
            with open(p, "w") as fh:
                fh.write(t)
        kb.ingest_file(self.db, a)
        kb.ingest_file(self.db, b)
        os.remove(a)
        self.assertEqual(kb.prune(self.db, self.dir), 1)
        self.assertFalse(self.search("piling"))
        self.assertTrue(self.search("net 30"))

    def test_csv_cp1252(self):
        with open(self.f("Log.csv"), "wb") as fh:
            fh.write("RFI;Subject\n12;Caf\xe9 foundation\n".encode("cp1252"))
        kb.ingest_file(self.db, self.f("Log.csv"))
        self.assertTrue(self.search("caf\xe9"))


if __name__ == "__main__":
    unittest.main()
