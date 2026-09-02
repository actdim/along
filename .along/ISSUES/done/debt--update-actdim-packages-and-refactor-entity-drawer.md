---
protocol: along
slug: update-actdim-packages-and-refactor-entity-drawer
type: debt
status: done
completed: 2026-09-02
priority: medium
created: 2026-09-02
updated: 2026-09-02
agent: antigravity
tags: [dynstruct, dynstruct-mui, msgmesh, utico, dashboard-ui, refactor]
milestone: v2.1.0-along
blocked_by: []
related: []
---

# Upgrade @actdim Packages and Refactor EntityDrawer to Dynstruct Standards

## Context & Motivation
1. The `@actdim` suite (`@actdim/dynstruct`, `@actdim/dynstruct-mui`, `@actdim/msgmesh`, `@actdim/utico`) in `packages/dashboard-ui` is at `^1.5.10` and needs to be updated to `^1.5.13`.
2. `packages/dashboard-ui/src/components/EntityDrawer.tsx` contained an architectural anti-pattern (`MarkdownContent`) using React `useRef`, `useEffect`, and untyped `window as any` instead of pure Dynstruct hook-constructor component architecture (`useMarkdownContent` / `ComponentDef` with `c.id` and lifecycle `events`).

## Acceptance Criteria
- [x] Upgrade `@actdim/dynstruct`, `@actdim/dynstruct-mui`, `@actdim/msgmesh`, `@actdim/utico` in `packages/dashboard-ui/package.json` to `^1.5.13`.
- [x] Run `pnpm install` in `packages/dashboard-ui`.
- [x] Refactor `EntityDrawer.tsx` to use pure Dynstruct component architecture (`useMarkdownContent`), removing React hooks (`useRef`, `useEffect`), removing `any` type casting (`window as any`, `entity: any`), and using `c.id` for DOM queries.
- [x] Verify `pnpm run typecheck` and `pnpm run build` succeed with 0 errors.
