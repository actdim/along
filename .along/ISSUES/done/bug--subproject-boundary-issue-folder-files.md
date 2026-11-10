---
protocol: along
protocol_version: "4.6.1"
slug: subproject-boundary-issue-folder-files
type: bug
status: done
completed: 2026-11-10
priority: high
created: 2026-11-08
updated: 2026-11-10
agent: claude-code
tags: [gates, feedback]
blocked_by: []
related: []
---

# subproject-boundary denies files inside an umbrella issue's folder

## Problem

Field report (2026-11-08): a session bound to a subproject issue tried to edit a plan file of the root umbrella issue, `.along/ISSUES/task--forms-dynstruct-validation/plans/01--<name>.md`. `[gate: subproject-boundary]` denied it and said root entities on the bound issue's parent chain are allowed. The agent added `parent: task--forms-dynstruct-validation` to the bound issue; the same write was still denied. The report guessed the gate reads a stale session snapshot.

Root cause (`scripts/alongkit/hooks/predicates.py`, `_bound_subproject_owns_root_entity`): the parent chain IS read live from the bound issue's front matter. The gate derives the target entity from the file's basename (`01--<name>`), not from the issue folder that holds it, so a file inside `ISSUES/<key>/` never matches the umbrella key. Only the ticket `ISSUES/<key>.md` itself passes.

## Requirements
- REQ-1: The gate MUST map a root path under `.along/ISSUES/<key>/...` or `.along/ISSUES/done/<key>/...` to `<key>` before comparing it with the bound issue's parent chain.
- REQ-2: Ticket paths (`ISSUES/<key>.md`, `ISSUES/done/<key>.md`) MUST keep their current behavior.
- REQ-3: Files of a root issue NOT on the parent chain MUST still be denied.
- REQ-4: A `parent:` added mid-session MUST take effect on the next write (covered by a test, since the report suspected otherwise).

## Acceptance Criteria
- [x] A test: subproject-bound session, bound issue has `parent: task--umbrella`; writing `.along/ISSUES/task--umbrella/plans/01--x.md` is allowed; writing `.along/ISSUES/task--other/plan.md` is denied.
- [x] A test: the write is denied, `parent:` is then added to the bound issue, the same write is allowed.
- [x] Automated tests passing
