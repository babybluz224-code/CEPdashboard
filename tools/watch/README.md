# watch: version diffs and metadata checks

Local, standard-library Python (plus `pdftotext`/`pdfinfo` for PDFs). No network, no AI. Reads Word, PowerPoint, Excel, CSV, text and text-layer PDF files through the `tools/kb` reader.

```sh
python3 tools/watch/watch.py diff OLD NEW --out findings/diff-pay-app-3.md
python3 tools/watch/watch.py meta "Pay App 3.docx=2026-03-01" "Schedule.xlsx=2026-03-05"
```

**diff** lists changed lines (with `[-old-] [+new+]` marks), removed lines and added lines with their clause, slide or sheet location, and labels changes where numbers differ or a clause was only renumbered (check cross-references). Inserted or deleted spreadsheet rows shift cell references and can look like many changes.

**meta** shows the creator, last editor, revision, created and modified dates and application, and flags: created or edited after the date the document states (add `=YYYY-MM-DD` after the file name), modified before created, a different last editor, tracked changes left in, comments, hidden sheets, missing metadata.

Limits: tested only on synthetic files (`python3 -m unittest tests.test_watch`). Metadata is easy to change or reset: copying, converting, printing to PDF or opening and re-saving in another program can all rewrite dates, so a flag is a question for the author, never proof. Differences are word-level text differences; layout, images and formatting changes are not compared.
