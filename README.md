# CEP Dashboard

Workspace for owner's-rep oversight of a solar EPC contractor. There is no application code; the repo holds Claude Code agents, a skill, and a local P6 tool.

## What's here
- `.claude/agents/`: 23 audit agents (contract-expert, rfi-channel-monitor, case-ledger-keeper, notice-deadline-tracker, compliance-checker, commissioning-closeout-checker, weather-checker, photo-evidence-checker, narrative-analyst, pods-meetings-analyst, contract-obligations-mapper, schedule-forensics, pay-app-auditor, field-reports-reconciler, logistics-tracker, civil-mech-quantities-verifier, commitments-tracker, procore-records-analyst, delay-claims-skeptic, cross-document-reconciler, red-team-skeptic, meeting-prep-interviewer, findings-reporter).
- `.claude/skills/claims-audit/`: the `/claims-audit` skill that runs them in order, including a three-teammate agent team (narrative, PODs + meetings, P6) that cross-checks each other. Agent teams are experimental and enabled in `.claude/settings.json`.
- `tools/xer/`: reads native Primavera P6 `.xer` files and diffs schedule updates (standard-library Python, runs locally). See `tools/xer/README.md`.
- `templates/case-ledger.md`: starting point for the running case ledger (`case/ledger.md`, gitignored).
- `CLAUDE.md`: the working rules Claude follows in this repo.

## Confidentiality
This repo may be public. Put project documents in `case/` and write results to `findings/`; both are gitignored, as are `.xer`, `.xlsx`, `.xls` and `.pdf` files. Never commit contracts, pay apps, schedules or findings. Prefer running Claude Code locally for real project files.

## Tests
`python3 -m unittest tests.test_xer_tool`
