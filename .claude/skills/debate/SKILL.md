---
name: debate
description: Stages a structured debate between the two politicians (owner and EPC) on a finding, claim or question, then gives the user both sides and a neutral scorecard. Use when the user wants to hear both sides, stress-test a finding before raising it with the EPC, or asks how the other side will respond.
---

# Debate: hear both sides

Topic: a finding (from `findings/`), a claim in a submitted document, or a question (for example "the EPC's 8 weather days in March"). The contract package is in `case/contract/`; make sure the index is current (`python3 tools/kb/kb.py stale case`, then `ingest case`) and tell the user about any file it could not read.

Run the rounds in order with the Agent tool, one agent per turn, giving each the topic and the full transcript so far. Do not let either answer before the other has spoken.
1. `politician-owner`: opening statement (up to 400 words).
2. `politician-epc`: citation check and rebuttal (up to 400 words).
3. `politician-owner`: reply (up to 250 words), conceding any citation the EPC correctly challenged.
4. `politician-epc`: closing (up to 250 words).

Then write the neutral scorecard yourself, and do not take a side:
- **Agreed facts** (both conceded).
- **Strongest points** for each side, with the citation.
- **Citations challenged**: which were wrong, which held.
- **What is genuinely disputed** and the specific record that would settle each point.
- **Where the owner's case is weak** (from the owner's Vulnerability note and the EPC's attacks) and **where the EPC's is weak**.
- **How a neutral reader would likely see it**: leans owner, leans EPC, or unclear, with the reason and what would change it. Not a legal opinion.
- **Next steps**: documents to request, deadlines (hand to `notice-deadline-tracker`), questions for counsel.

Save the full transcript and scorecard to `findings/debate/<topic>-<date>.md` (gitignored). Then give the user both sides: each statement in full, one after the other, followed by the scorecard.

Rules: facts only from the record, every quote verified with `kb.py show`; the politicians argue and may label inferences but never invent; no accusations of intent; no legal advice. The EPC side is a stress test, not an endorsement. Project documents and findings are confidential and stay in `case/` and `findings/`.
