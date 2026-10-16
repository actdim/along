---
protocol: along
protocol_version: "4.4.15"
slug: integrate-actdim-ui-core-runtime
title: Integrate @actdim/ui-core Runtime Dependencies and CSS Tokens into Dashboard UI
type: task
status: open
priority: high
created: 2026-10-16
updated: 2026-10-16
agent: antigravity
tags: [dashboard-ui, ui-core, runtime, dependencies, css, tokens, build]
parent: task--migrate-to-actdim-ui-core
blocked_by: [task--reconcile-dashboard-ui-core-conventions]
related: []
---

# Integrate @actdim/ui-core Runtime Dependencies and CSS Tokens into Dashboard UI

## Context & Technical Constraints

With frontend conventions and documentation centralized in `@actdim/ui-core`, `packages/dashboard-ui` must integrate `@actdim/ui-core` as a runtime dependency and adopt its standardized design tokens and layout services.

Key technical constraints to address:
1. Package availability: `@actdim/ui-core` is developed under `mempart/src/packages/ui-core` and is not yet published to the public npm registry. It must be installed via local workspace link (`pnpm add link:../../../../mempart/src/packages/ui-core` or `file:` reference) or published npm release.
2. Peer dependency compatibility: `@actdim/ui-core` requires `@actdim/dynstruct >=1.9.0`, `@actdim/dynstruct-mui >=1.9.0`, and `@actdim/msgmesh >=1.9.0`. The dashboard currently uses version `^1.8.3`. Dependency versions must be reconciled to prevent peer dependency conflicts.
3. CSS integration: The dashboard stylesheet is `src/index.css` (Tailwind v4), which must import `@actdim/ui-core` design tokens.

## Acceptance Criteria & Execution Checklist

### Phase 1: Dependency Wiring & Peer Reconciliation
- [ ] Install `@actdim/ui-core` in `packages/dashboard-ui/package.json` (`dependencies`):
  - Determine resolution mechanism (local `link:` / `file:` vs published npm release).
  - Align `@actdim/dynstruct`, `@actdim/dynstruct-mui`, `@actdim/msgmesh`, and `@actdim/utico` versions to meet `@actdim/ui-core` peerDependency requirements.
- [ ] Run `along dep-scan --link` (or update dependency docs) to register `@actdim/ui-core`.
- [ ] Ensure `pnpm install` resolves cleanly without lockfile corruption.

### Phase 2: CSS & Design Tokens Integration
- [ ] In `packages/dashboard-ui/src/index.css`:
  - Import `@actdim/ui-core` design tokens / CSS bundle.
  - Reconcile dark mode token scales and surface colors with `@actdim/ui-core` CSS variables.

### Phase 3: Runtime Component & Layout Bridges
- [ ] Evaluate dashboard views and overlays (`SearchModal`, `EntityDrawer`, `Header`) against `@actdim/ui-core`:
  - Adopt `@actdim/ui-core/components` or `@actdim/ui-core/layout` where applicable.
  - Ensure zero raw React state (`useState`, `useEffect`) and maintain strict Dynstruct + MobX bindings.

### Phase 4: Verification & Quality Gates
- [ ] Run `pnpm run typecheck`: 0 TypeScript compiler errors.
- [ ] Run `pnpm test`: 100% test pass rate.
- [ ] Run `pnpm run build`: Vite build passes cleanly.
- [ ] Run `along sanitize --check`: 0 non-ASCII or prohibited typographic characters.
