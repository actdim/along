---
protocol: along
protocol_version: "4.4.16"
slug: autonomous-gate-profile
type: feat
status: open
priority: high
created: 2026-10-17
updated: 2026-10-17
agent: claude-code
tags: [gates, autonomous, profile, mvp]
milestone: v5.0.0-agent-run-protocol-and-observability
parent: feat--autonomous-multi-runtime-mvp
blocked_by: [debt--gate-simplification]
related: [feat--agent-execution-gate-telegram, feat--isolated-environment-docker]
---

# Autonomous gate profile: no ask decisions, deterministic allow/deny, Telegram escalation for a short list

## Problem

In autonomous mode nobody sits at the terminal. Any gate decision `ask` stalls the run until a
timeout. Gates were designed for the interactive mode.

## Design

- Profile `autonomous`, selected by the environment (`feat--isolated-environment-docker`) and by
  `along daemon`. Builds on the existing profile mechanism (strict, standard, light) instead of a new one.
- Every `ask` becomes `deny` with a one-line reason the agent can act on, except the escalation list.
- Escalation list (sent to Telegram as an approval request, run waits with a timeout, default deny):
  push to the default branch, tag or release, package publish, deploy commands, the narrow deletion
  check from `debt--gate-simplification`.
- Plan approval is a state in the issue or blackboard written by the architect or reviewer role, not
  an interactive session token.
- Interactive profile keeps `ask` for the same short list only.

## Acceptance Criteria
- [ ] No gate returns `ask` under the autonomous profile, except the escalation list routed to Telegram.
- [ ] Escalation timeout denies and records the outcome in the run record.
- [ ] Plan approval written by a role unlocks source edits for the implementer.
- [ ] Automated tests passing.
