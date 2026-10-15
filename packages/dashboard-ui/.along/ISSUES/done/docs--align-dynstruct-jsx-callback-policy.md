---
protocol: along
protocol_version: "4.4.13"
slug: align-dynstruct-jsx-callback-policy
type: docs
status: done
completed: 2026-10-15
priority: medium
created: 2026-10-15
updated: 2026-10-15
agent: antigravity
tags: [conventions, dynstruct, jsx, callbacks]
blocked_by: []
related: []
---

# Align Dynstruct Conventions, Prop-Less JSX & Callback Policy

Incorporate the updated conventions on prop-less JSX, low-level event handlers in def.children, inter-component coordination without callback-drilling, and overlay dialog patterns into `packages/dashboard-ui/docs/topic--frontend-conventions.md`. Verify and align dashboard-ui implementation with these requirements.

## Acceptance Criteria
- [x] Update `packages/dashboard-ui/docs/topic--frontend-conventions.md` with the Dynstruct prop-less JSX and callback policy section
- [x] Audit and align dashboard-ui components (`SearchModal.tsx`, `App.tsx`, `EntityDrawer.tsx`) with canonical binding and handler patterns
- [x] Run `pnpm run typecheck`, `pnpm test`, and `pnpm run build`
- [x] Verify `along sanitize` and `along kb sync` pass cleanly
