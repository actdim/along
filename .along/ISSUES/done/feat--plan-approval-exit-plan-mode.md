---
protocol: along
protocol_version: "4.4.2"
slug: plan-approval-exit-plan-mode
type: feat
status: done
completed: 2026-10-01
priority: high
created: 2026-10-01
updated: 2026-10-01
agent: claude-code
tags: [gates, plan, claude]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--session-state-cross-session-leak]
---

# Session-scoped plan approval via ExitPlanMode and along plan approve

## Problem
`require_plan_approval` defaults to phase `inquiry` when no session exists, so working Claude
hooks would deny every edit and every non-read-only command in any Along repository until
`along start`. `along start` itself sets `plan_approved: true`, so approval is a CLI call the agent
makes on its own and proves nothing about the user. Decision (user, 2026-10-01): approve through
Claude Code's ExitPlanMode plus a CLI fallback; without a bound issue source edits stay blocked,
read-only work is allowed.

## Requirements
- REQ-1: PostToolUse on `ExitPlanMode` (the user accepted the plan in the UI) sets
  `plan_approved: true` and `phase: execution` for the issue bound to that session id.
- REQ-2: `along plan approve [<slug>]` is the manual fallback; the skill text says it is run only
  after the user's explicit yes.
- REQ-3: `along start` binds the session and sets `phase: planning`, `plan_approved: false`;
  `along start --approved` keeps the old behaviour for scripted runs.
- REQ-4: Without a bound slug, mutations get one clear message (create/start an issue), not two
  overlapping gate errors.

## Acceptance Criteria
- [x] ExitPlanMode approval unlocks edits for that session only
- [x] Automated tests passing
