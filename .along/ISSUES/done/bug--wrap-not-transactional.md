---
protocol: along
protocol_version: "4.4.9"
slug: wrap-not-transactional
type: bug
status: done
completed: 2026-10-11
priority: medium
created: 2026-10-11
updated: 2026-10-11
agent: claude-code
tags: [wrap, transaction, gates]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--cross-context-parent-dangling, bug--history-append-blocked-after-wrap]
parent: task--field-report-fixes
---

# along wrap mutates before validating; --force-reason ignores graph gate

Reported from field use (2026-10-11).

## Problem

Fixture: any workspace with an invalid entity graph (e.g. the fixture of
`bug--cross-context-parent-dangling` before its fix), plus `bug--child` in `in-progress`.

`along wrap child --no-decisions`:

- the issue is moved to `done/`, the session log is written, the blackboard is purged;
- then "Wrap failed: entity graph has dangling references";
- the `HISTORY.md` line is not appended;
- rerunning with `--force-reason "..."` fails the same way.

## Requirements

- REQ-1: All checks (graph, tests, schema) run before any mutation (plan -> validate -> apply),
  e.g. via `alongkit.transaction.FileTransaction`.
- REQ-2: On failure nothing changes on disk.
- REQ-3: `--force-reason` also covers the graph gate; the reason is written to the session log.

## Acceptance Criteria
- [ ] After a failed wrap, `git status --porcelain` is identical to the state before the run (hermetic test)
- [ ] `--force-reason` passes the graph gate and is recorded in the session log
- [ ] Automated tests passing
