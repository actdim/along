---
protocol: along
protocol_version: "4.4.2"
slug: activity-trace-shared-across-sessions
type: bug
status: done
completed: 2026-10-01
priority: high
created: 2026-10-01
updated: 2026-10-01
agent: claude-code
tags: [session, gates, diagnostics]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--session-state-cross-session-leak]
---

# Activity trace and hook diagnostics are repo-global and tracked in git

## Problem
`predicates.record_tool_activity()` writes one `.along/diagnostics/activity_trace.json` per
repository. `test_before_stop` compares its `last_edit_time` and `last_test_time`, so an edit in
session A blocks the Stop of session B, and a test run in B unblocks A. `edited_files` grows
forever. `activity_trace.json`, `circuit_breaker.json` and `hooks_audit.jsonl` are tracked in
git, so every session dirties the tree and branches conflict on them.

## Requirements
- REQ-1: Activity is recorded per session id (`.along/diagnostics/activity/<runtime>--<id>.json`);
  events without an id fall back to the shared file.
- REQ-2: `test_before_stop` reads only the stopping session's trace.
- REQ-3: `.along/diagnostics/` runtime files are untracked (`.gitignore`, `git rm --cached`).

## Acceptance Criteria
- [ ] Edit in session A does not block Stop in session B
- [ ] Diagnostics no longer appear in `git status` after a session
- [ ] Automated tests passing
