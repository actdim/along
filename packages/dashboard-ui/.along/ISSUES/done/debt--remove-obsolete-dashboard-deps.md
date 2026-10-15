---
protocol: along
protocol_version: "4.4.13"
slug: remove-obsolete-dashboard-deps
type: debt
status: done
completed: 2026-10-15
priority: low
created: 2026-10-15
updated: 2026-10-15
agent: antigravity
tags: [deps, cleanup]
blocked_by: []
related: []
---

# Remove obsolete dependencies from dashboard-ui

Remove unused `@iconify/react` and `jsdom` dependencies from `packages/dashboard-ui/package.json` following migration to `@iconify/tailwind4` and `happy-dom`.

## Acceptance Criteria
- [x] Remove `@iconify/react` from dependencies
- [x] Remove `jsdom` from devDependencies
- [x] Verify `pnpm install`, `pnpm typecheck`, `pnpm test`, and `pnpm build` pass cleanly
