# CEP Dashboard

CEP Dashboard. There is no application code yet; for now the repo only contains a
[Ruflo](https://github.com/ruvnet/claude-flow) (claude-flow v3) multi-agent setup for
Claude Code:

- `.mcp.json` registers the `ruflo` MCP server (`npx -y ruflo@3.52.1 mcp start`).
- `.claude/skills/ruflo/SKILL.md` is the **ruflo** skill: when and how to use swarms,
  memory and routing.
- `.claude/agents/ruflo-orchestrator.md` is the **ruflo-orchestrator** subagent.

## Requirements

- Node.js 20+ (the server is launched through `npx`)
- [Claude Code](https://claude.com/claude-code)

## Setup

Open the project in Claude Code. On first open it asks whether to approve the
project-scoped `ruflo` MCP server from `.mcp.json`; approve it. Then check it is
connected:

```sh
claude mcp list
```

## Usage

- Run the skill: `/ruflo`
- Or ask for the agent: "use the ruflo-orchestrator to build the dashboard API, UI and
  tests".

Ruflo tools appear to Claude as `mcp__ruflo__<tool>`.

## Troubleshooting

- **Ruflo tools missing**: the server is not connected. Run `claude mcp list`, confirm
  Node.js 20+ is installed and the server was approved, then restart the Claude Code
  session.
- **First run is slow**: `npx` downloads the pinned package the first time.
- **`agent_spawn` did nothing**: it only registers an agent for coordination and does
  not run any work. Launch real Claude Code subagents (or use `agent_execute`, which
  needs `ANTHROPIC_API_KEY`) to do the work.

## Upgrading Ruflo

The version is pinned in `.mcp.json` (`ruflo@3.52.1`). Check the latest with
`npm view ruflo version`, edit the version in `args`, then restart the session.
