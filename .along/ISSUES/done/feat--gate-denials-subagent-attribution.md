---
protocol: along
protocol_version: "4.6.0"
slug: gate-denials-subagent-attribution
type: feat
status: done
completed: 2026-11-06
priority: high
created: 2026-11-05
updated: 2026-11-06
agent: antigravity
tags: [gates, subagents, multi-agent, diagnostics]
blocked_by: []
related: []
plan_status: needs-approval
---

# Subagent attribution for gate denials and unresolved-gate-denial reporting

Record subagent identity and conversation context when capturing gate denials and display subagent attribution in `along gates stats`, `along gates denials`, and `[gate: unresolved-gate-denial]` error reports. Currently, when subagents trigger gate denials (e.g. attempting to delete outside workspace or run forbidden commands), the supervisor session inherits open denials without attribution, leaving the supervisor and user blind to which agent incurred the failure and why.

## Requirements
- REQ-1: Hook event adapters (`antigravity.py`, `claude.py`) and `HookEvent` MUST capture subagent identity (`agent_id`, `subagent_name`, or sub-conversation ID) from raw runtime payloads.
- REQ-2: `_record_denial_event` in `scripts/alongkit/hooks/predicates.py` MUST persist the agent/subagent attribution in the denial record and in blackboard `open_denials`.
- REQ-3: `along gates stats` and `along gates denials` MUST display which subagent or agent incurred each denial (e.g. `[d-1a2b3c] (subagent: researcher) gate: destructive_command`).
- REQ-4: When `check_unresolved_denials` blocks turn completion at Stop, the rejection message MUST specify the subagent name and actionable guidance for the supervisor agent to acknowledge or report the failure to the user.
- REQ-5: Hermetic unit tests in `tests/test_subagent_denials.py` verifying subagent attribution capture, denial formatting, and gate stats output.

## Acceptance Criteria
- [x] Subagent identity is captured by hook adapters into `HookEvent`.
- [x] Denial events and `open_denials` carry subagent attribution.
- [x] `along gates stats` and `along gates denials` display subagent tags.
- [x] `unresolved-gate-denial` error message names the responsible subagent.
