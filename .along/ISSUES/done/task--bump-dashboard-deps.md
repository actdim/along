---
protocol: along
protocol_version: "4.4.12"
slug: bump-dashboard-deps
type: task
status: done
completed: 2026-10-14
priority: medium
created: 2026-10-14
updated: 2026-10-14
agent: antigravity
tags: [dashboard-ui, deps]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: []
---

# Bump @actdim dashboard deps to 1.8.3

Update `@actdim/dynstruct`, `@actdim/dynstruct-mui`, `@actdim/msgmesh`, `@actdim/utico` from `^1.5.13` to `^1.8.3` in `packages/dashboard-ui/package.json`.

## Acceptance Criteria
- [x] Update packages/dashboard-ui/package.json with 1.8.3 specs
- [x] Run typecheck and tests cleanly
