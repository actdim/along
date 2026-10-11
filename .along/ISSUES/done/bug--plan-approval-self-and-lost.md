---
protocol: along
protocol_version: "4.4.9"
slug: plan-approval-self-and-lost
type: bug
status: done
completed: 2026-10-11
priority: medium
created: 2026-10-11
updated: 2026-10-11
agent: claude-code
tags: [plan-gate, hooks]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [debt--protocol-friction-cleanup]
parent: task--field-report-fixes
---

# Plan approval: agent self-approval and approval lost on along start

Reported from field use (2026-10-11).

## Problem

A. Self-approval: `along plan approve` can be called by the agent itself; the gate does not
check that the user replied after the plan appeared.

1. The user writes "yes" to an unrelated message.
2. The agent writes `plan.md`.
3. The agent calls `along plan approve`: approved.

B. Lost approval:

1. `EnterPlanMode` -> `ExitPlanMode` (the user approved).
2. `along start <slug>`.
3. `along plan status` shows `approved: false`; the agent has to call
   `plan approve --plan-file` again.

C. Hint after `along start` says "Claude Code: ExitPlanMode", but `ExitPlanMode` only works in
plan mode (overlaps `debt--protocol-friction-cleanup` REQ-1).

## Requirements

- REQ-1: A user-message hook (Claude Code: `UserPromptSubmit`) stores the timestamp of the last
  user message in session state.
- REQ-2: CLI `plan approve` is rejected when the plan file was modified after that timestamp:
  "plan changed after the user's last message; show it and wait for a reply".
- REQ-3: Session state and log record `approved_via` (`exit-plan-mode` or `cli`), timestamp
  and plan hash.
- REQ-4: `along start` picks up the session's latest `ExitPlanMode` approval when it happened
  after the user's last message and the plan file has not changed since.
- REQ-5: Hint text: "Call EnterPlanMode, write the plan, then ExitPlanMode. If plan mode is
  unavailable, show the plan in chat and wait for the user's reply; run `along plan approve`
  only after that reply."
- REQ-6 (nice to have): step-wise approval `along plan approve --step N` unlocking only that
  step's files; a non-empty "Open decisions" plan section blocks approval.

## Resolution (2026-10-11)

REQ-1..REQ-5 implemented (UserPromptSubmit hook, CLI approval check, approved_via / plan hash,
ExitPlanMode carry-over on `along start`, hint text). REQ-6 (step-wise approval, "Open
decisions" section) is not implemented: it was marked nice-to-have and stays open for a
follow-up issue.

## Acceptance Criteria
- [ ] Approve rejected when the plan is newer than the last user message, accepted when older
- [ ] Approval survives `along start`
- [ ] Hint text updated
- [ ] Automated tests passing
