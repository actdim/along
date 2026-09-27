---
protocol: along
protocol_version: "4.2.0"
slug: along-exec-argparse-migration
type: debt
status: open
priority: medium
created: 2026-09-27
updated: 2026-09-27
agent: cowork
tags: [cli, refactor, dx]
milestone: v4.4.0-multi-user-merge-automation
blocked_by: [bug--py310-fstring-syntax-error]
related: [bug--session-create-unsafe-yaml]
---

# Replace hand-rolled argv parsing in along_exec.py with argparse

## Problem

`scripts/along_exec.py` (1963 lines) dispatches every command (`issue`, `milestone`, `session`, `decision`, `worktree`, `scratch`, `circuit`, `telemetry`, `run`, ...) through manual `while i < len(args)` loops. Unknown or misspelled flags fall into `else: i += 1` and are silently ignored - `along issue create feat x-y --prioirty high` creates a `medium` issue with no warning. Help text is a hand-maintained `print_help()`. Other engines (`along_kb_search.py`) already use `argparse`, so behaviour is inconsistent across the CLI.

## Requirements

- REQ-1: One `argparse` parser with subparsers per command group; unknown flags exit with code 2 and a usage message.
- REQ-2: Split `along_exec.py` into a thin dispatcher plus per-command modules (e.g. `alongkit/commands/issue.py`, `session.py`, `decision.py`, `worktree.py`), each under ~400 lines.
- REQ-3: Preserve every existing flag and alias used by skills and docs; a test parses the `along ...` invocations found in `skills/*/SKILL.md` and `docs/topic--cli-reference.md` and asserts they are accepted.
- REQ-4: `--help` output is generated and `docs/topic--cli-reference.md` is checked against it.

## Acceptance Criteria

- [ ] Misspelled flags fail loudly
- [ ] All documented invocations still parse
- [ ] Automated tests passing
