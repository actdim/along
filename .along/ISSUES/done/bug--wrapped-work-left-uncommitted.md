---
protocol: along
protocol_version: "4.4.6"
slug: wrapped-work-left-uncommitted
type: bug
status: done
completed: 2026-10-09
priority: high
created: 2026-10-07
updated: 2026-10-09
agent: claude
tags: [session, closeout, commit]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [feat--parallel-session-closeout, task--release-v4-4-7]
---

# Wrapped work left uncommitted without warning

## Problem

On 2026-10-06/07 parallel sessions wrapped 9 bugs (issue moved to `done/`, session log
written) and stopped; none committed. At the `task--release-v4-4-7` closeout,
`along session list` showed 77 changed paths, all "unattributed": `along session close`
commits only attributed files, so the whole batch had to be committed by hand in one
mixed commit.

Nothing along the way said "issue X is done but its changes are not in git": not the wrap,
not the Stop gates, not `along doctor`.

## Requirements

- REQ-1: `along wrap` ends with a warning when files attributed to the slug (or changed in
  the session) remain uncommitted, with the exact `along commit -i <slug> --paths ...` to run.
- REQ-2: `along session list` / `along doctor` group unattributed changes by the done issue
  whose session log or event ledger names them, so they can be committed per issue.
- REQ-3: `along session close` can take a done slug and commit its files (from the session
  log's attributed table) even after the blackboard is gone.
- REQ-4: Optional Stop-gate warning (not block) for a session that wrapped but did not commit.

## Acceptance Criteria
- [x] Hermetic test: wrap with dirty attributed files prints the warning and command
- [x] Unattributed changes grouped by done issue in session list
- [x] Automated tests passing
