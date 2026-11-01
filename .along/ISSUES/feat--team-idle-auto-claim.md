---
protocol: along
protocol_version: "4.5.4"
slug: team-idle-auto-claim
type: feat
status: open
priority: medium
created: 2026-10-30
updated: 2026-10-30
agent: antigravity
tags: [team, hooks, blackboard, auto-claim]
milestone: v5.1.0-language-ecosystem-expansion
blocked_by: []
related: []
---

# Reactive turn-stop and idle hook auto-claim for along-team blackboard

Implement a reactive idle and turn-stop hook integration that inspects blackboard state and automatically advances unblocked steps to available agent roles.

## Context and Problem Statement
Currently, multi-agent orchestration in `along-team` transitions between roles (e.g. Research -> Architect -> Implementer -> Reviewer) through active polling or explicit sequential prompt cycles driven by the Supervisor. This creates unnecessary latency and token overhead as the Supervisor must repeatedly inspect the blackboard, synthesize a prompt, and invoke the next worker.

By introducing an event-driven idle hook (similar to `teammate-idle` and post-turn completion hooks in agent harnesses), the along runtime can reactively detect when a subagent finishes its step, verify the step output against the blackboard contract, and automatically trigger the next unblocked step.

## Requirements
- REQ-1: Hook Dispatcher: Implement a post-turn / idle event handler in `scripts/along_hook.py` that triggers upon subagent completion.
- REQ-2: State Advancement: When a step passes its exit verification, the hook MUST atomically advance the blackboard step state (`state.json`) and release the corresponding `claim.lock`.
- REQ-3: Auto-Claim Queue: Unblocked downstream steps MUST be made available for immediate execution; when `--auto-claim` is enabled, the next role MUST be initialized and briefed deterministically via `along brief`.
- REQ-4: Safety Circuit Breaker: If step execution results in test failures, gate denials, or schema violations, auto-claim MUST halt immediately, preserving error traces and escalating to the Supervisor or human operator.

## Acceptance Criteria
- [ ] Idle and turn-stop hook handlers implemented in `scripts/along_hook.py`
- [ ] Atomic blackboard state advance and claim release logic in `scripts/along_team.py`
- [ ] Automated role brief generation on step handover
- [ ] Circuit breaker halts execution on gate failure with zero state corruption
- [ ] Unit tests in `tests/test_alongkit.py` covering auto-advance and error escalation paths
