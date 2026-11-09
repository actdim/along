---
protocol: along
protocol_version: "4.7.0"
slug: integrate-actdim-ui-core-runtime
title: Integrate @actdim/ui-core Runtime Dependencies and CSS Tokens into Dashboard UI
type: task
status: done
completed: 2026-11-09
priority: high
created: 2026-10-16
updated: 2026-11-09
agent: antigravity
tags: [dashboard-ui, ui-core, runtime, dependencies, css, tokens, build]
parent: task--migrate-to-actdim-ui-core
blocked_by: []
related: []
plan_status: approved
---

# Integrate @actdim/ui-core Runtime Dependencies and CSS Tokens into Dashboard UI

## Context & Technical Constraints

With frontend conventions and documentation centralized in `@actdim/ui-core`, `packages/dashboard-ui` must integrate `@actdim/ui-core` as a runtime dependency and adopt its standardized design tokens and layout services.

Key technical constraints (verified 2026-11-08):
1. Package availability: `@actdim/ui-core`, `@actdim/dynstruct`, `@actdim/dynstruct-mui`, `@actdim/msgmesh` and `@actdim/utico` are published at `1.12.2` and must be upgraded together.
2. MUI major upgrade: `@actdim/ui-core@1.12.2` and `@actdim/dynstruct-mui@1.12.2` require `@mui/material >=9.0.1`; the dashboard pins `^6.4.0` (already violating the installed `ui-core@1.9.1` peer). The dashboard reaches MUI only through `@actdim/dynstruct-mui/{Dialog,Drawer,Tabs}`, but `src/index.css` overrides `.MuiDrawer-paper`, `.MuiDialog-paper`, `.MuiPaper-root` and `.MuiBackdrop-root`.
3. Peer contract: besides `mobx`, `mobx-react-lite`, `rxjs`, `@emotion/*`, `uuid`, the 1.12.2 packages require `i18next >=24`, `postcss >=8.5`, `jwt-decode >=4`, `http-status >=2.1`, `react-router >=7.9.3`. Under pnpm strict resolution every peer is declared explicitly.
4. CSS integration: `src/index.css` (Tailwind v4) imports `@actdim/ui-core/theme.css`; hardcoded colours are replaced with existing `ui-core` tokens (`surface-*`, `fg-*`, `line-*`). `tw()` from `@actdim/ui-core/theme` is adopted in the two tested components only.
5. Testing: Vitest + happy-dom component tests for `IssuesKanbanView` and `SearchModal`.

Detailed execution steps are defined in [plan.md](./task--integrate-actdim-ui-core-runtime/plan.md).

## Acceptance Criteria & Execution Checklist

### Phase 0: MUI 9 Decision
- [x] `ui-core` 1.9.1 -> 1.12.2 changes and MUI v7/v8/v9 migration notes reviewed (class names, Paper/Dialog/Drawer slots, Emotion).
- [x] Decision recorded in this issue: upgraded to `@mui/material` `^9.0.1` alongside `@actdim/*` `1.12.2`. All `@actdim/*` peer dependencies satisfied.

### Phase 1: Dependency Wiring & Peer Reconciliation
- [x] All `@actdim/*` at `^1.12.2`; `@mui/material` at `^9.0.1` (per Phase 0).
- [x] Peers declared: `mobx`, `mobx-react-lite`, `rxjs`, `@emotion/react`, `@emotion/styled`, `uuid`, `i18next`, `postcss`, `jwt-decode`, `http-status`, `react-router`.
- [x] `pnpm install` in `packages/dashboard-ui` updates `pnpm-lock.yaml` with zero unmet-peer warnings.
- [x] `typecheck`, `test` and `build` green before CSS work starts.

### Phase 2: Runtime Check of MUI-backed Views
- [x] Drawer, Dialog and Tabs open, render and close in the running dashboard; before/after screenshots compared.
- [x] `index.css` overrides that no longer match MUI 9 class names fixed.

### Phase 3: CSS & Design Tokens Integration
- [x] `@import "@actdim/ui-core/theme.css";` kept in `src/index.css`.
- [x] Hardcoded colours in body, scrollbars, markdown body and MUI overrides replaced with `ui-core` tokens; unnecessary `!important` removed.
- [x] `tw()` adopted in `IssuesKanbanView` and `SearchModal`.

### Phase 4: Vitest Component Tests
- [x] `src/components/IssuesKanbanView.test.tsx`: model initialization, filters and their intersection, `selectIssue` publishes `APP.ENTITY.SELECT`, DOM renders filter controls.
- [x] `src/components/SearchModal.test.tsx`: open/close, `performSearch` over `m.data` (match and empty-query reset), `selectResult` closes and publishes `APP.ENTITY.SELECT`.

### Phase 5: Verification & Quality Gates
- [x] `pnpm --filter @along/dashboard-ui typecheck` (or in-package equivalent; there is no root `pnpm-workspace.yaml`): 0 errors.
- [x] `pnpm --filter @along/dashboard-ui test`: all tests pass.
- [x] `pnpm --filter @along/dashboard-ui build`: Vite build succeeds.
- [x] `python scripts/sanitize_typography.py --check`: 0 prohibited characters.
