# Weekly watch checklist

Copy to `case/weekly-watch.md` (gitignored) and tick off each week. Or run `/weekly-watch`.

- [ ] Put new documents in `case/` (contract package in `case/contract/`).
- [ ] `python3 tools/kb/kb.py stale case`, then `ingest case`; note any file it could not read.
- [ ] For each re-issued document: `python3 tools/watch/watch.py diff OLD NEW --out findings/diff-<name>.md`.
- [ ] For each new document: `python3 tools/watch/watch.py meta FILE=<date it states>`.
- [ ] Forecast check: completion date, manpower and recovery plan versus last month.
- [ ] Public records: liens or lawsuits on the parcel, EPC and major subs; licence and insurance status; permit and inspection status; interconnection queue; recent news.
- [ ] Deadlines in the next 30 days (notice, pay-app dispute window, response times): `notice-deadline-tracker`.
- [ ] Update `case/ledger.md` (open items, requests, commitments, key dates).
- [ ] Anything for counsel? List it here and send it.
