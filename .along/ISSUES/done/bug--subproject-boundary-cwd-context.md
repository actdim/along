---
protocol: along
protocol_version: "4.4.9"
slug: subproject-boundary-cwd-context
type: bug
status: done
completed: 2026-10-11
priority: medium
created: 2026-10-11
updated: 2026-10-11
agent: claude-code
tags: [subproject, gates, containment]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--cross-context-parent-dangling, feat--subproject-boundary-by-active-issue, bug--containment-root-from-shell-cwd]
parent: task--field-report-fixes
---

# subproject-boundary derives context from cwd instead of target file

Reported from field use (2026-10-11).

## Problem

Fixture as in `bug--cross-context-parent-dangling`; the agent session is bound to
`task--umbrella` (root).

1. In the agent's shell tool run `cd ws/sub`.
2. Edit `ws/.along/ISSUES/task--umbrella.md` (absolute path): rejected with
   "Cannot write to root ... while working inside subproject 'sub'".
3. `cd ws` and repeat the same edit: it passes.

The persisted shell cwd decides the outcome, not the file being written.

## Requirements

- REQ-1: The context is the nearest `.along/` above the absolute path of the target file.
- REQ-2: That context is checked against the bound issue and its child issues (cross-context
  `parent` per `bug--cross-context-parent-dangling`).
- REQ-3: cwd has no influence on the decision.

## Acceptance Criteria
- [ ] The same edit gives the same result for any cwd (hermetic test, several cwds)
- [ ] Automated tests passing
