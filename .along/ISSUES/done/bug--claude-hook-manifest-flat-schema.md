---
protocol: along
protocol_version: "4.4.2"
slug: claude-hook-manifest-flat-schema
type: bug
status: done
completed: 2026-10-01
priority: critical
created: 2026-10-01
updated: 2026-10-01
agent: claude-code
tags: [hooks, claude, install]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--claude-runtime-not-detected, bug--claude-stop-loop-ask-mapping]
---

# Claude Code hooks written in flat schema are ignored

## Problem
`get_claude_hook_manifest()` (`scripts/alongkit/hooks/config.py`) emits hook entries as
`{"matcher": ..., "command": ...}`. Claude Code reads only the nested form
`{"matcher": ..., "hooks": [{"type": "command", "command": ..., "timeout": N}]}`, so every
Along gate is silently skipped in Claude Code. Evidence on 2026-10-01: `~/.claude/settings.json`
carries the flat entries, and `.along/diagnostics/hooks_audit.jsonl` of this repository has
238 antigravity and 5 generic records and none with `runtime: claude`. A consumer repository
showed the same (659 records, no claude).

`install_claude_hooks()` matches existing entries by `item["command"]`, so it cannot find nested
entries either, and `purge_local_along_hooks()` has the same blind spot. The Codex manifest uses
the same flat shape and needs the same check.

## Requirements
- REQ-1: The Claude manifest emits the nested schema with `type: command` and a timeout.
- REQ-2: `install_claude_hooks` migrates legacy flat Along entries in place (no duplicates) and
  keeps foreign hooks untouched; re-running is idempotent.
- REQ-3: Entry matching and purge understand both flat and nested entries.
- REQ-4: The Codex manifest is verified against the Codex hook format and fixed if it differs.

## Acceptance Criteria
- [x] Fresh install writes nested entries; legacy flat entries are migrated
- [x] Purge removes nested and flat Along entries
- [x] A real Claude Code session produces `runtime: claude` records in `hooks_audit.jsonl`
- [x] Automated tests passing
