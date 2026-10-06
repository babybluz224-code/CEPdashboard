"""Tests for tools/watch/watch.py using synthetic files."""
import os
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "tools", "watch"))
sys.path.insert(0, HERE)
import watch  # noqa: E402
import office_builders as ob  # noqa: E402

CORE = ('<?xml version="1.0" encoding="UTF-8"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/">'
        '<dc:creator>A. Contractor</dc:creator><cp:lastModifiedBy>B. Editor</cp:lastModifiedBy><cp:revision>7</cp:revision>'
        '<dcterms:created>{created}</dcterms:created><dcterms:modified>{modified}</dcterms:modified></cp:coreProperties>')


def add_core(path, created, modified):
    with zipfile.ZipFile(path, "a") as z:
        z.writestr("docProps/core.xml", CORE.format(created=created, modified=modified))


def doc(path, paras, **kw):
    ob.write_docx(path, "".join(ob.para(ob.run(p), num=(1, 1)) if isinstance(p, str) else p for p in paras), **kw)


class WatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def f(self, n):
        return os.path.join(self.tmp.name, n)

    def test_diff_changed_removed_added_and_numbers(self):
        doc(self.f("v1.docx"), ["Retainage shall be ten percent of each payment.", "Owner pays within thirty days.", "Weather days need notice."])
        doc(self.f("v2.docx"), ["Retainage shall be five percent of each payment.", "Weather days need notice.", "Contractor may suspend work for nonpayment."])
        ch, rem, add = watch.diff(self.f("v1.docx"), self.f("v2.docx"))
        self.assertTrue(any("[-ten-] [+five+]" in t for _, t in ch), ch)
        self.assertTrue(any("thirty days" in t for _, t in rem), rem)
        self.assertTrue(any("suspend work" in t for _, t in add), add)

    def test_diff_flags_number_changes(self):
        ob.write_xlsx(self.f("a.xlsx"), [("SOV", [["Piling", 1000], ["Trenching", 2000]], False)])
        ob.write_xlsx(self.f("b.xlsx"), [("SOV", [["Piling", 1500], ["Trenching", 2000]], False)])
        ch, rem, add = watch.diff(self.f("a.xlsx"), self.f("b.xlsx"))
        self.assertEqual(len(ch), 1)
        self.assertIn("numbers differ", ch[0][1])
        self.assertIn("B1: [-1000-] [+1500+]", ch[0][1])

    def test_renumbering_is_labelled(self):
        doc(self.f("v1.docx"), ["Scope of work.", "Weather days need notice."])
        doc(self.f("v2.docx"), ["Weather days need notice."])
        ch, rem, add = watch.diff(self.f("v1.docx"), self.f("v2.docx"))
        self.assertTrue(any("renumbered only" in t for _, t in ch), ch)
        self.assertTrue(any("Scope of work" in t for _, t in rem))

    def test_diff_identical_files_is_empty(self):
        doc(self.f("v1.docx"), ["Same text here."])
        doc(self.f("v1b.docx"), ["Same text here."])
        self.assertEqual(watch.diff(self.f("v1.docx"), self.f("v1b.docx")), ([], [], []))

    def test_meta_flags(self):
        p = self.f("PayApp.docx")
        doc(p, ["Application for payment"])
        add_core(p, "2026-03-12T10:00:00Z", "2026-03-20T09:00:00Z")
        _, info, notes, claimed = watch.check_file(p + "=2026-03-01")
        flags = {f for f, _ in notes}
        self.assertEqual(info["creator"], "A. Contractor")
        self.assertIn("CREATED AFTER CLAIMED DATE", flags)
        self.assertIn("EDITED AFTER CLAIMED DATE", flags)
        self.assertIn("DIFFERENT LAST EDITOR", flags)
        self.assertEqual(claimed, "2026-03-01")

    def test_meta_modified_before_created_and_clean_case(self):
        p = self.f("X.docx")
        doc(p, ["x"])
        add_core(p, "2026-03-12T10:00:00Z", "2026-03-01T09:00:00Z")
        self.assertIn("MODIFIED BEFORE CREATED", {f for f, _ in watch.check_file(p)[2]})
        q = self.f("Y.docx")
        doc(q, ["y"])
        add_core(q, "2026-02-20T10:00:00Z", "2026-02-25T09:00:00Z")
        flags = {f for f, _ in watch.check_file(q + "=2026-03-01")[2]}
        self.assertNotIn("CREATED AFTER CLAIMED DATE", flags)
        self.assertNotIn("EDITED AFTER CLAIMED DATE", flags)

    def test_meta_missing_metadata_tracked_changes_hidden_sheet(self):
        p = self.f("Z.docx")
        ob.write_docx(p, ob.para('<w:ins w:id="1" w:author="E"><w:r><w:t>new</w:t></w:r></w:ins>'))
        flags = {f for f, _ in watch.check_file(p)[2]}
        self.assertIn("NO METADATA", flags)
        self.assertIn("TRACKED CHANGES", flags)
        x = self.f("H.xlsx")
        ob.write_xlsx(x, [("Main", [["a"]], False), ("Backup", [["b"]], True)])
        self.assertIn("HIDDEN SHEETS", {f for f, _ in watch.check_file(x)[2]})

    def test_unsupported_and_text_types(self):
        t = self.f("n.txt")
        with open(t, "w") as fh:
            fh.write("hello\n")
        self.assertIn("SKIPPED", {f for f, _ in watch.check_file(t)[2]})


if __name__ == "__main__":
    unittest.main()
