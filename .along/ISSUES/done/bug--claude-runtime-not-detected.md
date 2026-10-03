---
protocol: along
protocol_version: "4.4.2"
slug: claude-runtime-not-detected
type: bug
status: done
completed: 2026-10-01
priority: high
created: 2026-10-01
updated: 2026-10-01
agent: claude-code
tags: [doctor, runtime, claude]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--claude-hook-manifest-flat-schema]
---

# detect_agent and doctor miss Claude Code env markers and hook schema

## Problem
`entities.detect_agent()` recognizes Claude Code by `CLAUDE_CODE`, `CLAUDE_PROJECT_DIR`,
`CLAUDE_CONVERSATION_ID`, `ANTHROPIC_CLI`. A Claude Code desktop session on 2026-10-01 exposes
none of them to Bash/PowerShell; it sets `CLAUDECODE=1`, `CLAUDE_CODE_ENTRYPOINT`,
`CLAUDE_CODE_SESSION_ID`. `along doctor` run from Claude therefore prints `Runtime: unknown`.

`runtime.along_hooks_registered()` greps for the substring `along_hook` in settings.json, so a
broken (flat) entry counts as registered and doctor reports `mechanical` enforcement while no
gate runs.

## Requirements
- REQ-1: `detect_agent` recognizes `CLAUDECODE`, `CLAUDE_CODE_ENTRYPOINT`, `CLAUDE_CODE_SESSION_ID`.
- REQ-2: Hook registration check parses settings.json and accepts only entries in the nested
  schema that point at `along_hook.py` for PreToolUse and Stop.
- REQ-3: Doctor warns when the runtime is hook-capable but `hooks_audit.jsonl` has no record for
  it in the last N days (hooks registered but never fired).

## Acceptance Criteria
- [x] `along doctor` from Claude Code prints `claude-code`
- [x] Flat schema is reported as not registered, with the fix command
- [x] Automated tests passing
