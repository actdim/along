---
protocol: along
protocol_version: "4.4.6"
slug: runtime-plan-dir-containment
type: bug
status: done
completed: 2026-10-06
priority: medium
created: 2026-10-06
updated: 2026-10-06
agent: claude-code
tags: [gates, containment, claude]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: []
---

# workspace-containment blocks the Claude Code plan directory

Claude Code plan mode writes its plan to `~/.claude/plans/<name>.md`. The workspace-containment
gate denies it: the writable roots outside the workspace are the temp dir, the Antigravity brain
dir and `~/.claude/projects` (`alongkit/hooks/containment.py`); `~/.claude` is only a read root.
Plan mode then cannot record a plan, while Along itself requires an approved plan before edits.

Already in place and not part of this issue: the session scratchpad (under the OS temp dir) is
writable, and an approved `ExitPlanMode` is imported into the blackboard `plan.md`
(`session.record_accepted_plan`).

## Requirements
- REQ-1: `~/.claude/plans` is a writable runtime artifact root.

## Acceptance Criteria
- [x] Containment test: a write to `~/.claude/plans/x.md` is allowed, `~/.claude/settings.json` is not
- [x] Automated tests passing

## Resolution
`containment.CLAUDE_PLANS_DIR` (`~/.claude/plans`) joins the write roots in `build_policy`; the
rest of `~/.claude` stays read-only. Test: `test_workspace_containment.test_claude_plan_dir_writable`.
Docs: `docs/topic--declarative-gates-and-traceability.md`.
