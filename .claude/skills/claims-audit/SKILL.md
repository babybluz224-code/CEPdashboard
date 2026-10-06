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
| 1 | `contract-obligations-mapper` | contract, exhibits, amendments |
| 2 (parallel) | `schedule-forensics` | P6 updates |
| 2 | `pay-app-auditor` | pay apps + backup |
| 2 | `field-reports-reconciler` | dailies, PODs, Procore logs |
| 2 | `logistics-tracker` | BOLs, delivery tickets, inventory |
| 2 | `civil-mech-quantities-verifier` | quantities, QC, survey |
| 2 | `commitments-tracker` | meeting minutes, emails |
| 2 | `procore-records-analyst` | Procore exports |
| 2 | `delay-claims-skeptic` | claims, notices, change requests |
| 3 | `cross-document-reconciler` | all of `findings/` |
| 4 | `red-team-skeptic` | reconciled findings |
| 5 | `findings-reporter` and/or `meeting-prep-interviewer` | surviving findings |

Skip rows whose inputs don't exist, and say so in the final report. For a single pay app, steps 1, then `pay-app-auditor`, `field-reports-reconciler`, `logistics-tracker`, then 3-5 is usually enough.

## Using Ruflo (optional)
For a long case, `swarm_init` (hierarchical) and `memory_store` per-case notes (no document contents, no personal data), so later sessions can recall what was already checked. Ruflo registers agents but the real work is done by the subagents above.

## Evidence standard
Every finding needs a citation (file, page/cell, quote), a classification (CONFIRMED CONFLICT / PROBABLE / UNVERIFIED / EXPLAINED), the best innocent explanation, and the next document to request. Only findings that survive `red-team-skeptic` go into the memo or meeting prep.
