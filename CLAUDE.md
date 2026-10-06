# CEP Dashboard: owner's-rep EPC audit workspace

Solar development, owner's project manager. This repo holds audit agents (`.claude/agents/`), the `claims-audit` skill, and a local XER tool (`tools/xer/`). There is no application code.

## Rules
- Project documents are confidential and this repo may be public. Inputs go in `case/`, outputs in `findings/`; both are gitignored. Never commit contracts, pay apps, schedules, Procore exports or findings.
- Every finding needs a citation (file, page/cell, quote), a classification (CONFIRMED CONFLICT / PROBABLE / UNVERIFIED / EXPLAINED), the best innocent explanation, and the next document to request.
- Say "inconsistent with", never "lied". No legal advice; flag items for counsel.
- Native `.xer` files: use `python3 tools/xer/xer_tool.py` (summary, check, export, diff). Tested only on synthetic files so far.
- For a full review, use `/claims-audit`.
- Team mode (agent teams) is enabled in `.claude/settings.json`. For the narrative / PODs+meetings / P6 cross-check, use the prompt in `.claude/skills/claims-audit/SKILL.md`. Each teammate writes only to its own `findings/` file.
- The contract package lives in `case/contract/` (base agreement, amendments, change orders, exhibits, appendices). Whenever the user submits or points to any project document (meeting minutes, pay app, narrative, RFI, notice, change-order proposal, schedule update, email thread), FIRST run the `contract-expert` agent in submission mode on it (the `/contract-ref` skill) and show the user what the contract says about it, before any other analysis. Never answer contract questions from memory.

