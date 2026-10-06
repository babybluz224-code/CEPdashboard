# xer_tool

Reads native Primavera P6 `.xer` files and compares schedule updates. Python 3 standard library only; no network, no AI. Run it on your own machine so project files never leave it.

```sh
python3 tools/xer/xer_tool.py summary  FILE
python3 tools/xer/xer_tool.py check    FILE
python3 tools/xer/xer_tool.py export   FILE findings/out
python3 tools/xer/xer_tool.py diff     OLD NEW --out findings/diff.md
```

`diff` matches activities by Activity ID and reports: removed and added activities, retroactive edits to actual dates, status regressions, original-duration changes on incomplete work, remaining duration cut with no progress, constraint and calendar changes, milestone shifts, float changes (`--float-days`), and relationships removed, added or with changed lag.

`check` reports: out-of-sequence progress, actuals after the data date, status inconsistencies, open ends, constraints (mandatory ones flagged), leads and long lags, negative float.

Limits: tested only on synthetic XERs (`python3 -m unittest tests.test_xer_tool`), not on real exports. Real files vary by P6 version, so run `summary` first and sanity-check counts against P6. Multi-project XERs use the first project unless `--project` is given. Findings are inconsistencies to investigate, not proof of intent.

Outputs contain project data: keep them in `findings/` (gitignored).
