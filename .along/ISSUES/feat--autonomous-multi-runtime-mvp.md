---
protocol: along
protocol_version: "4.4.16"
slug: autonomous-multi-runtime-mvp
type: feat
status: open
priority: high
created: 2026-10-17
updated: 2026-10-17
agent: claude-code
tags: [epic, vps, multi-runtime, autonomous, mvp]
milestone: v5.0.0-agent-run-protocol-and-observability
blocked_by: []
related: [feat--agent-run-protocol-and-observability, feat--byoc-kubernetes-operator-and-private-sandboxes]
---

# Epic: autonomous multi-runtime mode on an isolated VPS (MVP)

## Goal

Run a mix of agent runtimes (Claude Code, Codex, OpenCode, and Antigravity or its replacement)
semi-autonomously on a dedicated Ubuntu VPS. Runtimes cooperate only through files in the
repository (`.along/` issues, ADRs, session blackboard), a strong model plans and reviews, a cheaper
model implements, and the operator observes and answers through Telegram. One command deploys an
isolated environment for a repository.

## Two Operating Modes

| | Interactive (Windows, human in the loop) | Autonomous (container on VPS) |
| --- | --- | --- |
| Isolation | none, at the operator's risk | Docker container + egress allowlist (ADR-2026-10-17--docker-isolation-now-gvisor-later) |
| Runtime permissions | normal, with prompts | no-confirmation modes inside the container |
| Gates | may ask | allow or deny only; escalation to Telegram for a short list |
| Plan approval | operator (plan mode) | architect or reviewer role, recorded in the issue file |

## Child Issues (MVP order)

1. `spike--headless-runtimes-on-linux` - what each runtime can do headless on Linux. Blocks everything else.
2. `debt--gate-simplification` - can start immediately; removes friction in interactive mode too.
3. `debt--entity-model-slimming` - can start immediately, in parallel with 2.
4. `feat--isolated-environment-docker` - `along env up`.
5. `feat--cross-runtime-handoff-entities` - run records, review verdicts, questions, claims, `along brief`.
6. `feat--cross-runtime-supervisor-orchestrator` - MVP: implementer + reviewer loop.
7. `feat--vps-runner-daemon` - MVP: long polling, one run per repository.
8. `feat--agent-execution-gate-telegram` - MVP: one chat, one operator, status card.
9. `feat--autonomous-gate-profile` - gates that never ask in autonomous mode.

Related but not on the MVP path: `feat--agent-runtime-adapters-claude-codex-opencode` (launch part
is in scope, OTel mapping is not), `feat--agent-interactive-stdin-bridge` (replaced by the file-based
question protocol), `feat--byoc-kubernetes-operator-and-private-sandboxes` (v6 vision).

## Out of Scope for the MVP

- OpenTelemetry / OpenInference export, OTLP sinks (the JSONL event log and the Telegram card are enough).
- Telegram Mini App, inline issue search, multi-room and forum-topic routing, operator roles.
- Webhook ingress, priority queues, more than one concurrent run per repository.
- gVisor, Kubernetes, micro-VMs.

## Acceptance Criteria
- [ ] One command brings up an isolated environment for a repository on a fresh Ubuntu VPS.
- [ ] An issue dispatched from Telegram is implemented by one runtime and reviewed by another, with handoff only through files.
- [ ] A failed review re-runs the implementer with the reviewer's defects, up to a retry limit.
- [ ] An agent question reaches the operator in Telegram and the answer reaches the next run.
- [ ] No gate in autonomous mode waits for an interactive answer.
