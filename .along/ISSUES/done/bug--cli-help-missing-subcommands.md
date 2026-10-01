---
protocol: along
protocol_version: "4.4.1"
slug: cli-help-missing-subcommands
type: bug
status: done
completed: 2026-09-30
priority: low
created: 2026-09-30
updated: 2026-09-30
agent: claude
tags: [cli, help, docs]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: []
---

# along --help omits milestone create and scratch phase/approve

## Problem

The router help in `scripts/along_exec.py` listed only `milestone sync|list|show`, although `milestone create` is implemented. An agent relying on `--help` concluded the command did not exist and wrote a milestone file by hand, bypassing the version-collision check. `scratch phase` and `scratch approve` were implemented but undocumented both in `--help` and in `docs/topic--cli-reference.md`; `scratch init` was listed twice.

## Fix

- `--help`: added `milestone create`, `scratch phase`, `scratch approve`; removed the duplicate `scratch init` line.
- `docs/topic--cli-reference.md`: documented the same three subcommands with a usage example.
- Remaining subcommands (`issue`, `session`, `decision`, `worktree`) verified against the dispatch code; only aliases (`issue close/edit/get`, `decision add`) stay undocumented in `--help` by design.

## Acceptance Criteria
- [x] `along --help` lists every implemented non-alias subcommand of `milestone` and `scratch`
- [x] CLI reference documents the same commands
- [x] Automated tests passing (771 tests, OK)
