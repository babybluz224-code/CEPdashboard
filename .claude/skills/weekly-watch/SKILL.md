---
name: weekly-watch
description: Weekly watchdog sweep for the EPC project: detects new or changed documents, diffs re-issued versions against the previous ones, checks metadata for back-dating, checks public records for liens, lawsuits, licences and permits, and lists upcoming deadlines. Use weekly, when new documents arrive, or when the user asks what changed or whether anything looks off.
---

# Weekly watch

1. Run the `watchdog` agent (documents and public records). It writes `findings/watchdog-<date>.md`.
2. Run `notice-deadline-tracker` for deadlines in the next 30 days, owner deadlines first.
3. Run `case-ledger-keeper` to update `case/ledger.md` from the findings.
4. Give the user a short summary: top items, what needs a person (portals the agent could not reach, questions for counsel), and what to ask the EPC.

The checklist template is in `templates/weekly-watch.md`. Rules: only the project's own documents and public records; no covert recording, no accessing others' accounts, no pretexting; project documents and findings stay in the gitignored `case/` and `findings/` folders, and are never sent to a web search. Metadata and diffs are questions to ask, not proof of intent.
