---
name: claims-audit
description: Owner's-rep audit of an EPC contractor on a solar build: tests what the EPC says (contract compliance, P6 schedules, pay apps, daily reports and PODs, Procore, meeting minutes, deliveries, civil and mechanical quantities) against what the records show. Use when the user is doing an EPC deep dive, reviewing a pay app, checking a schedule update, preparing for an owner/EPC meeting, or looking for inconsistencies in contractor paperwork.
---

# Claims audit (owner's rep, utility-scale solar)

Goal: find where the EPC's paperwork contradicts itself or the record, with evidence strong enough to act on. The agents flag *inconsistencies*; they do not accuse anyone of lying and they do not give legal advice.

## Confidentiality first
This repo may be public. Keep project documents and results out of it. Put them in `case/` (inputs) and `findings/` (outputs); both are gitignored. Never commit contracts, pay apps, schedules, Procore exports or findings. If asked to, refuse and explain.

## Setup
1. Ask the user where the documents are, or have them placed under `case/`: contract + exhibits + amendments; P6 exports (XER preferred); pay apps with backup; daily reports/PODs/Procore daily logs; Procore exports (RFIs, submittals, NCRs, change events); meeting minutes; delivery tickets/BOLs; QC/test records.
2. Note what is missing; each missing input limits specific agents.

## Run order (use the Agent tool, one subagent per row; independent rows in parallel)
| Step | Agent | Needs |
|------|-------|-------|
| 0 | `case-ledger-keeper` | `case/ledger.md` (read first: what is open, what is overdue) |
| 1 | `contract-expert` and `contract-obligations-mapper` | contract, exhibits, amendments, change orders |
| 2 (parallel) | `schedule-forensics` | P6 updates |
| 2 | `pay-app-auditor` | pay apps + backup |
| 2 | `field-reports-reconciler` | dailies, PODs, Procore logs |
| 2 | `logistics-tracker` | BOLs, delivery tickets, inventory |
| 2 | `civil-mech-quantities-verifier` | quantities, QC, survey |
| 2 | `commitments-tracker` | meeting minutes, emails |
| 2 | `procore-records-analyst` | Procore exports |
| 2 | `delay-claims-skeptic` | claims, notices, change requests |
| 2 | `notice-deadline-tracker` | contract clauses + dated events |
| 2 | `rfi-channel-monitor` | contract protocol, RFI log, emails, EOR correspondence |
| 2 (as needed) | `compliance-checker`, `commissioning-closeout-checker`, `weather-checker`, `photo-evidence-checker` | compliance records / test and closeout records / weather claims / photos |
| 3 | `cross-document-reconciler` | all of `findings/` |
| 4 | `red-team-skeptic` | reconciled findings |
| 5 | `findings-reporter` and/or `meeting-prep-interviewer` | surviving findings |
| 6 | `case-ledger-keeper` | update `case/ledger.md` from `findings/` |

Skip rows whose inputs don't exist, and say so in the final report. For a single pay app, steps 1, then `pay-app-auditor`, `field-reports-reconciler`, `logistics-tracker`, then 3-5 is usually enough.

## Team mode (agent teams)
For the core three-way cross-check, run an agent team so the teammates can challenge each other's findings while they work. Requires Claude Code v2.1.32+ and an interactive session; agent teams are experimental, off by default, and are enabled for this project in `.claude/settings.json`. They use noticeably more tokens than subagents. Teammates cannot spawn teammates, and `/resume` does not restore them.

Ask the lead for exactly this (adjust the case folder paths):

```text
Create an agent team of three teammates for an owner's-rep audit of this EPC. Use these agent types and names:
- "narrative" (narrative-analyst): the monthly progress reports, pay app and schedule narratives, recovery plans and notices in case/narratives/.
- "pods" (pods-meetings-analyst): the PODs, daily logs and weekly/monthly meeting minutes in case/field/ and case/meetings/.
- "p6" (schedule-forensics): the P6 XER updates in case/schedules/ (use tools/xer/xer_tool.py).
Each teammate writes only to its own file in findings/ (narrative.md, pods.md, p6.md). After a first pass each one must message the other two the claims and numbers they can test, and answer the claims sent to them with CONFIRMED / CONTRADICTED / CANNOT TEST plus citations. Wait for all three to finish before you do anything else. When all three are done, run cross-document-reconciler on findings/, then red-team-skeptic on its result, one after the other, and give me the surviving findings.
```

Add `contract-expert` as a fourth teammate so the others can ask it what the contract says (it answers with quotes), or `pay-app-auditor` / `logistics-tracker`, as a fourth teammate if the case calls for it; keep it to three to five.

Note: while agent teams are enabled, a subagent Claude names launches as a teammate, so the reconciler and red-team step may appear as extra teammates. That is fine; they only read `findings/`. To get plain subagents again, set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` to `0` in `.claude/settings.json`.

If the lead keeps working instead of waiting, tell it: "Wait for your teammates to complete their tasks before proceeding."

## Reading the documents
Use the document skills already available in Claude: `pdf` for contracts, pay apps and scanned pages (including OCR), `xlsx` for SOV, pay app and Procore spreadsheet exports, `docx` for Word contracts and meeting minutes. Native P6 files go through `tools/xer/xer_tool.py` (see `schedule-forensics`). For a deliverable, `docx` or `xlsx` can produce the memo or the findings table.

## Evidence standard
Every finding needs a citation (file, page/cell, quote), a classification (CONFIRMED CONFLICT / PROBABLE / UNVERIFIED / EXPLAINED), the best innocent explanation, and the next document to request. Only findings that survive `red-team-skeptic` go into the memo or meeting prep.
