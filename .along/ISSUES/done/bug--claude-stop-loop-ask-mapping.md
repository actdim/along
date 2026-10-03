---
protocol: along
protocol_version: "4.4.2"
slug: claude-stop-loop-ask-mapping
type: bug
status: done
completed: 2026-10-01
priority: high
created: 2026-10-01
updated: 2026-10-01
agent: claude-code
tags: [hooks, claude, stop]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--claude-hook-manifest-flat-schema]
---

# Claude Stop gates can loop and ASK decisions are downgraded to DENY

## Problem
- Stop gates answer with exit 2, which makes Claude Code continue the turn. The adapter ignores
  the payload's `stop_hook_active` flag, so an unsatisfiable Stop gate re-blocks forever.
- `HookEngine.evaluate()` converts `ASK` into `DENY` for every runtime except antigravity, and
  `ClaudeCodeAdapter.format_response()` only knows exit codes. Claude Code supports a native ask
  through the PreToolUse JSON output (`hookSpecificOutput.permissionDecision: "ask"`).

## Requirements
- REQ-1: On Stop with `stop_hook_active: true` the gate result is reported once more as a
  warning, not a block (no second forced continuation).
- REQ-2: Claude adapter emits JSON decisions for PreToolUse (`deny` with reason, `ask` with
  reason) and keeps exit 2 as fallback; ASK reaches Claude as ask.

## Acceptance Criteria
- [ ] Stop with `stop_hook_active` does not block
- [ ] Workspace-containment read outside scope asks in Claude instead of denying
- [ ] Automated tests passing
