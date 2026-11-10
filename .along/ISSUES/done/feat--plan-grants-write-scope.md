---
protocol: along
protocol_version: "4.6.1"
slug: plan-grants-write-scope
type: feat
status: done
completed: 2026-11-10
priority: medium
created: 2026-11-08
updated: 2026-11-10
agent: claude-code
tags: [gates, feedback]
blocked_by: []
related: []
---

# Approved plan grants its Files to change as write scope

## Problem

Field report (2026-11-08): `[gate: require-active-issue]` denied a write to a file outside the bound subproject although the user-approved plan listed that path under "Files to change". The denial follows the rules, but it asks the user to approve the same path twice, and the usual way to widen scope (`along start --write-scope`) then hit `bug--start-dirty-check-misattribution`.

## Requirements
- REQ-1: `along plan approve` MUST read the plan's "Files to change" section and add its paths outside the issue's context to the issue's `write_scope`, or list them and ask for confirmation once.
- REQ-2: Paths MUST still pass `[gate: workspace-containment]`; the plan cannot grant paths outside the workspace or `allowed_roots`.
- ~~REQ-3: A command MUST exist to extend the bound issue's scope without the start-time checks (for example `along scope add <path>`), so scope changes never need a re-start.~~ (Covered by bug--start-dirty-check-misattribution REQ-2: re-starting an active issue with `--write-scope` skips dirty checks).

## Acceptance Criteria
- [x] Approving a plan whose "Files to change" lists `../other/x.ts` lets the session write `../other/x.ts` with no further step.
- [x] Paths outside the workspace in that list are reported, not granted.
- [x] Automated tests passing
