---
protocol: along
protocol_version: "4.5.2"
slug: exit-plan-text-not-captured
type: bug
status: in-progress
priority: high
created: 2026-10-23
updated: 2026-10-23
agent: claude-code
tags: [plan-approval, hooks]
blocked_by: []
related: []
plan_status: approved
---

# ExitPlanMode approval records no plan text (plan now in tool_response / plan file)

When the user accepts a plan through Claude Code's `ExitPlanMode`, the PostToolUse hook
records the approval but not the plan text, so the issue plan (`.along/ISSUES/<key>/plan.md`)
stays the scaffold. Evidence (2026-10-23): `feat--pre-approved-plans` and
`bug--wrap-misses-moved-issue-folder` traces show `plan approved (ExitPlanMode)` with no
`plan recorded` line.

Cause: the capture in `hooks/predicates.record_tool_activity` reads only `tool_input.plan`.
Current Claude Code calls `ExitPlanMode` with an empty input (`{}`); the plan lives in a plan
file (`~/.claude/plans/<name>.md`) and the tool result carries it:
`tool_response = {"plan": "...", "isAgent": false, "filePath": "<plan file>"}` (transcripts
31d67282, d526bdff). `tool_input` may also carry `plan` / `planFilePath` once normalized.

## Requirements
- REQ-1: The ExitPlanMode PostToolUse capture MUST take the plan text from `tool_input.plan`, then `tool_response.plan`, then the file named by `tool_input.planFilePath` / `tool_response.filePath`.
- REQ-2: The captured text MUST reach `session.record_accepted_plan`, so a bound slug's issue plan holds it.

## Acceptance Criteria
- [ ] A regression test with the real payload shape (empty `tool_input`, plan in `tool_response`) records the plan text in the issue plan.
- [ ] A regression test with only the plan file path records the file's text.
- [ ] `python .along/scripts/test.py -q` is green.
