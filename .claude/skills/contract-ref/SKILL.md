---
name: contract-ref
description: Cross-references any submitted project document against the EPC contract package and says what the contract says about it. Use whenever the user drops, attaches or points to a project document: monthly or weekly meeting minutes, a pay app, a progress narrative, an RFI or answer, a notice, a change-order proposal, a schedule update or an email thread. Also use when the user asks what the contract says about something.
---

# Contract reference for every submission

Every project document gets a contract check first.

1. Identify the document (path under `case/`) and what kind it is. The contract package lives in `case/contract/`. If it is missing, tell the user and stop.
2. Make sure the index is current (`python3 tools/kb/kb.py stale case`, then `ingest case` if needed) and tell the user about any file it could not read.
3. Run the `contract-expert` subagent in **submission mode** on the document. Give it the file path and the document type. It updates its working files if the package changed, then writes `findings/contract/ref-<name>-<date>.md`.
   The agent first checks every contract citation in the document ("per Exhibit K-2", article numbers, change orders) against the actual text, current version and qualifiers, and lists them in a "Citations checked" table.
4. Show the user the result before any other analysis: the plain summary, the inconsistencies, the clocks that start or run, and the questions for counsel. Keep it short and point to the file for detail.
5. If the sheet lists deadlines, offer to run `notice-deadline-tracker`. If it flags an RFI or direction going outside the protocol, offer `rfi-channel-monitor`. If the user wants more, continue with `/claims-audit`.

Rules: quote the contract exactly with clause numbers; use the conformed (as-amended) text; never answer from memory; no legal advice, flag questions for counsel. Contract documents and findings are confidential and stay in the gitignored `case/` and `findings/` folders.
