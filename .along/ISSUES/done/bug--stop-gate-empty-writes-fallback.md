---
protocol: along
protocol_version: "4.9.0"
slug: stop-gate-empty-writes-fallback
type: bug
status: done
completed: 2026-11-15
priority: medium
created: 2026-11-15
updated: 2026-11-15
agent: claude-code
tags: [gates, hooks, stop, parallel-sessions]
blocked_by: []
related: [bug--stop-gate-false-positives]
plan_status: approved
---

# Stop gate counts foreign changes when the session wrote nothing this turn

## Problem

Found while reviewing `bug--stop-gate-false-positives` (commit `b4982cc`, v4.9.0). The Stop
branch of `require-plan-approval` (`check_mutation_authorization` in
`scripts/alongkit/hooks/predicates.py`) intersects the turn's working-tree changes with the
session's recorded writes (`trace["turn_writes"]`). When that set is empty it falls back to
"every change except the paths other sessions recorded in their `turn_writes`".

So the outcome for the same foreign change depends on whether this session wrote anything:

- session wrote nothing this turn, a file changed by something with no activity trace (the
  user's editor, a runtime without hooks) -> **denied**;
- session wrote one file, the same foreign change -> **ignored**.

Reproduced in a scratch git repo with `record_tool_activity` + `check_mutation_authorization`
(`enforce_unbound: true`).

The second case is the unsafe one. The hook cannot tell the user's editor from a write through a
tool the hooks do not see (for example an MCP tool): excusing untraced changes lets the session
bypass the plan as soon as it records one ordinary write. Decision (user, 2026-11-15): apply one
strict rule in both cases; an untraced change always counts.

## Requirements
- REQ-1: The Stop branch of `require-plan-approval` MUST excuse a changed path only when another
  session recorded it in its `turn_writes` and this session did not write it.
- REQ-2: Every other path the turn changed MUST count, whether or not this session recorded any
  writes of its own (same outcome for an untraced change in both cases).
- REQ-3: A trace without `turn_writes` (older hooks) MUST keep the whole-tree behavior.

## Acceptance Criteria
- [x] Regression test: no own writes + untraced change -> denied.
- [x] Regression test: one own write + untraced change -> denied, both paths reported.
- [x] Regression test: a path another session recorded is excused; a path both sessions wrote counts.
- [x] Existing `TestStopCountsSessionWrites` and `tests/test_shell_classification.py` pass unchanged.
- [x] `python .along/scripts/test.py` passes.
