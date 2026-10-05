---
protocol: along
protocol_version: "4.4.5"
slug: wrap-zero-byte-audit-unscoped
type: bug
status: done
completed: 2026-10-05
priority: medium
created: 2026-10-05
updated: 2026-10-05
agent: claude-code
tags: [wrap, gates]
blocked_by: []
related: []
---

# Wrap aborts on any empty file in the working tree

## Problem
`gates.zero_byte_working_tree_audit` flags every modified or untracked 0-byte file, and
`execute_wrap` aborts on it. An unrelated empty file anywhere in the repository (a
placeholder README in another package, an empty `__init__.py`) blocks the wrap of an
unrelated issue.

## Requirements
- REQ-1: The audit blocks only on likely corruption: a tracked file that was non-empty at
  `HEAD` and is now 0 bytes, or a 0-byte file the agent sessions of this context edited
  (activity traces `edited_files`).
- REQ-2: Other changed 0-byte files are reported as a warning and do not abort the wrap.
- REQ-3: Tests: an edited empty file aborts the wrap; an unrelated empty file only warns;
  a truncated tracked file aborts.

## Acceptance Criteria
- [x] REQ-1, REQ-2 implemented
- [x] REQ-3 tests pass
- [x] Automated tests passing
