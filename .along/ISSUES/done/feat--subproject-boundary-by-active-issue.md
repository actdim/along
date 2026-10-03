---
protocol: along
protocol_version: "4.4.2"
slug: subproject-boundary-by-active-issue
type: feat
status: done
completed: 2026-10-01
priority: medium
created: 2026-10-01
updated: 2026-10-01
agent: claude-code
tags: [gates, subproject, monorepo]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: [bug--session-state-cross-session-leak]
related: []
---

# Subproject boundary gate and umbrella issues for multi-subproject work

## Problem
There is no rule for a feature that touches several subprojects (webapp + server).
`check_subproject_boundary` decides by the hook process `os.getcwd()`, which is the workspace
root in most runtimes, so it almost never fires, and it ignores which `.along/` owns the active
issue.

## Requirements
- REQ-1: Protocol rule: one issue per touched `.along/`, or an umbrella issue in the nearest
  common `.along/` whose `children:` lists the subproject issues.
- REQ-2: Gate: a source edit under subproject S requires a bound issue in S's `.along/` or an
  umbrella issue that lists a child in S; decided from the edited path, not the process cwd.

## Acceptance Criteria
- [ ] Edit in a subproject without a matching issue is denied
- [ ] Umbrella issue with a child in that subproject allows it
- [ ] Automated tests passing
