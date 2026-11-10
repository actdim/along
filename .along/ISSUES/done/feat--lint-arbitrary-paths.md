---
protocol: along
protocol_version: "4.6.1"
slug: lint-arbitrary-paths
type: feat
status: done
completed: 2026-11-10
priority: low
created: 2026-11-08
updated: 2026-11-10
agent: claude-code
tags: [cli, feedback]
blocked_by: []
related: []
---

# along lint <paths...> for unstaged files

## Problem

Field report (2026-11-08): `along lint` takes only `--ci`, `--range`, `--no-links`, `--json` and checks staged changes. Checking new, unstaged plan files for ASCII typography before committing needed a hand-written grep. `along sanitize` covers typography only.

## Requirements
- REQ-1: `along lint <paths...>` MUST run the commit-time checks on the named files or directories, staged or not.
- REQ-2: With no paths, behavior MUST stay as today (staged changes).
- REQ-3: Exit codes MUST match the staged mode (0 clean, 1 findings, 2 usage error).

## Acceptance Criteria
- [x] `along lint .along/ISSUES/x/plans/01--y.md` reports a non-ASCII dash in an unstaged file.
- [x] `along lint --help` documents the paths argument.
- [x] Automated tests passing
