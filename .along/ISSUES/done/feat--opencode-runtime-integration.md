---
protocol: along
protocol_version: "4.8.1"
slug: opencode-runtime-integration
type: feat
status: done
completed: 2026-11-13
priority: high
created: 2026-11-13
updated: 2026-11-13
agent: antigravity
tags: [runtime, opencode, hooks, subprojects, discovery]
blocked_by: []
related: [feat--agent-runtime-adapters-claude-codex-opencode, feat--runtime-hooks-cursor-opencode]
plan_status: approved
---

# OpenCode Runtime Integration and Multi-Subproject Discovery

## Problem Statement

During an automated session where an OpenCode agent executed a sequence of Along tasks in a monorepo with nested subprojects, two classes of failures occurred:
1. Discovery failure across subproject boundaries: The agent searched only the repository root and reported nested subproject tasks as non-existent because Along provided no command to discover issues across nested contexts.
2. Semantic status ambiguity and lack of mechanical enforcement: OpenCode lacked runtime hook integration (`tool.execute.before`, `tool.execute.after`, `shell.env`), so no mechanical gates guided the agent or bound sessions. Furthermore, `ISSUES.md` rendered `plan ready` for approved plans, and plan markdown files contained contradictory free-text `Status: proposed` headers, leading the model to conclude plans were unapproved.

## Requirements

- REQ-1: The Along hook infrastructure MUST provide an OpenCode plugin (`along-opencode-plugin.js`) that intercepts tool executions (`tool.execute.before`, `tool.execute.after`) and injects session environment variables (`shell.env`) via `scripts/along_hook.py`.
- REQ-2: `along hook install --runtime opencode` (and `--runtime all`) MUST install the plugin into `~/.config/opencode/plugins/` (or `.opencode/plugins/`) and ensure registration in OpenCode configuration.
- REQ-3: `alongkit.session` MUST register OpenCode session environment variables (`OPENCODE_SESSION_ID`, `OPENCODE_CONVERSATION_ID`) in `SESSION_ENV_MARKERS` to bind executing sessions deterministically.
- REQ-4: `alongkit.runtime` and `along doctor` MUST detect OpenCode plugin installation and report mechanical enforcement status when hooks are active.
- REQ-5: `along issue find <slug_or_key>` MUST search the root context and all child contexts discovered via `repo.find_agent_contexts()`, returning context relative path, issue path, status, and `plan_status`.
- REQ-6: `along start <slug>` MUST search child subproject contexts when an issue is not found locally, printing the exact command `(cd <subproject_rel> && along start <slug>)` rather than failing with `not found`.
- REQ-7: `alongkit.entities.projections` MUST render `plan_status: approved` as `- plan approved` instead of `- plan ready`.
- REQ-8: `along doctor entities` MUST verify that `ISSUES.md` plan status annotations match the corresponding issue front matter `plan_status`.
- REQ-9: `along issue lint` MUST warn when a `plan.md` file contains contradictory free-text status headers (such as `Status: proposed` or `Status: needs approval`) when front matter is `plan_status: approved`.
- REQ-10: `AGENTS.md` and `PROTOCOL.md` MUST explicitly document that `ISSUES.md` is a compiled digest, that authoritative state comes from CLI/front matter, and explain sub-agent execution boundaries across runtimes.

## Acceptance Criteria

- [x] OpenCode plugin template and installation logic implemented and tested.
- [x] `along hook install --runtime opencode` installs the plugin cleanly.
- [x] `along doctor` reports mechanical enforcement when the OpenCode plugin is present.
- [x] `along issue find <slug>` resolves entities across root and nested subprojects.
- [x] `along start <slug>` at root for a nested issue provides the navigation hint.
- [x] `_PLAN_STATUS_NOTES["approved"]` outputs `- plan approved`.
- [x] `along doctor entities` checks `ISSUES.md` projection consistency against front matter.
- [x] `along issue lint` audits stale free-text plan headers.
- [x] All unit and regression tests pass hermetically.
