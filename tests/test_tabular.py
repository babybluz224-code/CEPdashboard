import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.common import tabular  # noqa: E402
from tests.xlsx_builder import write_xlsx  # noqa: E402


class TabularTests(unittest.TestCase):
    def test_xlsx_roundtrip_and_sparse_cells(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.xlsx")
            write_xlsx(p, [["Item", "Amount"], ["1", 1500.5], ["", "", "x"]])
            rows = tabular.read_table(p)
            self.assertEqual(rows[0], ["Item", "Amount"])
            self.assertEqual(tabular.to_number(rows[1][1]), 1500.5)
            self.assertEqual(rows[2], ["", "", "x"])

    def test_csv_with_cp1252_and_semicolons(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.csv")
            with open(p, "wb") as fh:
                fh.write("Name;Value\nCaf\xe9;1,5\n".encode("cp1252"))
            rows = tabular.read_table(p)
            self.assertEqual(rows[1][0], "Caf\xe9")

    def test_to_number(self):
        self.assertEqual(tabular.to_number("$1,234.50"), 1234.5)
        self.assertEqual(tabular.to_number("(1,000)"), -1000)
        self.assertEqual(tabular.to_number("12%"), 12.0)
        self.assertIsNone(tabular.to_number("n/a"))

    def test_excel_date(self):
        self.assertEqual(str(tabular.excel_date("45700")), "2025-02-12")
        self.assertEqual(str(tabular.excel_date("2026-03-01")), "2026-03-01")
        self.assertIsNone(tabular.excel_date("soon"))

    def test_find_header(self):
        rows = [["Project X"], [], ["Item No.", "Description of Work", "Scheduled Value"]]
        self.assertEqual(tabular.find_header(rows, ["item", "description", "scheduled value"]), 2)

    def test_unknown_sheet(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.xlsx")
            write_xlsx(p, [["a"]])
            with self.assertRaises(ValueError):
                tabular.read_table(p, sheet="nope")


if __name__ == "__main__":
    unittest.main()
