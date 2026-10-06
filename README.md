# CEPdashboard

## Ruflo agent setup

This repo ships a [Ruflo](https://github.com/ruvnet/claude-flow) (claude-flow v3)
multi-agent setup for Claude Code:

- `.mcp.json` – registers the `ruflo` MCP server (`npx -y ruflo@3.52.1 mcp start`).
  Claude Code asks you to approve it the first time you open the project.
- `.claude/skills/ruflo/SKILL.md` – the **ruflo** skill: when and how to use swarms,
  memory, routing.
- `.claude/agents/ruflo-orchestrator.md` – the **ruflo-orchestrator** subagent.

Requirements: Node.js 20+. Check with `claude mcp list`.

Usage: ask Claude e.g. "use the ruflo-orchestrator to build the dashboard API, UI and
tests", or "/ruflo".

To upgrade, change the pinned version in `.mcp.json` (`npm view ruflo version`).
