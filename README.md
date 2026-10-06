# CEP Dashboard

Workspace for owner's-rep oversight of a solar EPC contractor. There is no application code; the repo holds Claude Code agents, a skill, and a local P6 tool.

## What's here
- `.claude/agents/`: 24 audit agents (watchdog, contract-expert, rfi-channel-monitor, case-ledger-keeper, notice-deadline-tracker, compliance-checker, commissioning-closeout-checker, weather-checker, photo-evidence-checker, narrative-analyst, pods-meetings-analyst, contract-obligations-mapper, schedule-forensics, pay-app-auditor, field-reports-reconciler, logistics-tracker, civil-mech-quantities-verifier, commitments-tracker, procore-records-analyst, delay-claims-skeptic, cross-document-reconciler, red-team-skeptic, meeting-prep-interviewer, findings-reporter).
- `.claude/skills/contract-ref/`: `/contract-ref` runs `contract-expert` on any submitted document and reports what the contract says about it (also a standing rule in `CLAUDE.md`). Contract package goes in `case/contract/`.
- `.claude/skills/claims-audit/`: the `/claims-audit` skill that runs them in order, including a three-teammate agent team (narrative, PODs + meetings, P6) that cross-checks each other. Agent teams are experimental and enabled in `.claude/settings.json`.
- `tools/watch/`: version diffs and metadata checks for re-issued documents; used by the `watchdog` agent and `/weekly-watch`. See `tools/watch/README.md`.
- `templates/weekly-watch.md`: weekly checklist.
- `tools/kb/`: local searchable index of Word, PowerPoint, Excel, CSV, text and PDF files (clause/slide/sheet/page locations, exact quotes). See `tools/kb/README.md`.
- `tools/xer/`: reads native Primavera P6 `.xer` files and diffs schedule updates (standard-library Python, runs locally). See `tools/xer/README.md`.
- `templates/case-ledger.md`: starting point for the running case ledger (`case/ledger.md`, gitignored).
- `CLAUDE.md`: the working rules Claude follows in this repo.

## Confidentiality
This repo may be public. Put project documents in `case/` and write results to `findings/`; both are gitignored, as are `.xer`, `.xlsx`, `.xls` and `.pdf` files. Never commit contracts, pay apps, schedules or findings. Prefer running Claude Code locally for real project files.

## Tests
`python3 -m unittest tests.test_xer_tool tests.test_kb tests.test_watch`
