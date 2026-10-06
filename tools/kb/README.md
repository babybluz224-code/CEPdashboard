# kb: local document knowledge base

Reads Word, PowerPoint, Excel, CSV, text and text-layer PDF files into a local SQLite full-text index with the document and location of every passage, so answers can quote exactly. Python 3 standard library plus the `pdftotext` command for PDFs. No network, no AI. The index lives in `case/kb.sqlite` (gitignored); keep it on your own machine.

```sh
python3 tools/kb/kb.py ingest case                  # add/refresh; deleted files are dropped
python3 tools/kb/kb.py stale case                   # NEW / CHANGED / MISSING, changes nothing
python3 tools/kb/kb.py search "retainage"           # all words;  --any  or  --phrase
python3 tools/kb/kb.py search "weather notice" --doc "Exhibit K-2"
python3 tools/kb/kb.py show "Contract.docx" "4.1"   # full text at a location
python3 tools/kb/kb.py list                         # what was read, and what was not
```

| Format | Location shown | Notes |
|---|---|---|
| .docx | clause number, e.g. `4.1 · text` | Automatic numbering rebuilt; tracked changes inline as `[+new+]` `[-old-]`; comments indexed; tables included |
| .pptx | `slide N`, `slide N notes` | Slides in presentation order |
| .xlsx / .xlsm | `Sheet!rows 5-29` | Cached values; formulas as `[formula: =...]`; hidden sheets and rows flagged; dates are Excel serial numbers |
| .csv / .tsv | `rows 1-25` | cp1252 and semicolon files handled |
| .pdf | `p.N` plus clause when detected | Needs `pdftotext`; scanned PDFs are reported as `no text layer` (OCR first) |
| .txt / .md | clause or `line N` | |

Not read: legacy `.doc`, `.ppt`, `.xls` (open in Office, Save As .docx/.pptx/.xlsx), password-protected files, images, formulas not evaluated, Word headers/footers, Excel comments.

Limits: tested only on synthetic files (`python3 -m unittest tests.test_kb`). Real contracts have layouts it hasn't seen, so confirm clause numbers and quotes against the document the first few times. Search is word-based (with stemming), not meaning-based: try synonyms.
