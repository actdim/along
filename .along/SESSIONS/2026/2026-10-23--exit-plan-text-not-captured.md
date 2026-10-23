---
protocol: along
protocol_version: "4.5.2"
date: 2026-10-23
slug: exit-plan-text-not-captured
agent: claude-code
branch: main
commit: 4a5cba1
summary: ExitPlanMode PostToolUse capture now reads the accepted plan from tool_input.plan, tool_response.plan, or the plan file (planFilePath / filePath); current Claude Code sends an empty tool_input. Regression tests with the real payload shape; replayed the real payload through the repo hook to record this issue's plan.
issues_advanced: []
issues_completed: [bug--exit-plan-text-not-captured]
decisions: []
files: [scripts/alongkit/hooks/predicates.py, tests/test_session_records.py]
---

# Session: Exit plan text not captured

## Summary
ExitPlanMode PostToolUse capture now reads the accepted plan from tool_input.plan, tool_response.plan, or the plan file (planFilePath / filePath); current Claude Code sends an empty tool_input. Regression tests with the real payload shape; replayed the real payload through the repo hook to record this issue's plan.

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

Plan: kept with the issue (`plan/plan.md`, 1 revision(s)).

### Execution Trace

#### Execution Trace: exit-plan-text-not-captured
- 2026-10-23T17:36:24Z phase: planning -> execution
- 2026-10-23T17:36:24Z plan approved (ExitPlanMode) approved_via: exit-plan-mode
- 2026-10-23T17:36:51Z edit scripts/alongkit/hooks/predicates.py (x2)
- 2026-10-23T17:36:53Z edit tests/test_session_records.py (x2)
- 2026-10-23T17:42:25Z plan recorded: revision 1 (ExitPlanMode)
- 2026-10-23T17:42:25Z plan approved (ExitPlanMode) approved_via: exit-plan-mode, plan_sha256: afc79b7ae281
