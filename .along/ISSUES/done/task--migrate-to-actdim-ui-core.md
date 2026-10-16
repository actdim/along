---
protocol: along
protocol_version: "4.4.15"
slug: migrate-to-actdim-ui-core
title: Migrate Dashboard UI to @actdim/ui-core and Reconcile Conventions
type: task
status: done
completed: 2026-10-16
priority: high
created: 2026-10-16
updated: 2026-10-16
agent: antigravity
tags: [ui-core, migration, conventions, cleanup, dynstruct, dashboard-ui]
blocked_by: []
related: [debt--consolidate-dashboard-ui-subproject]
---

# Migrate Dashboard UI to @actdim/ui-core and Reconcile Conventions

## Context & Purpose

The foundational library `@actdim/ui-core` (published at version `1.9.1` on npm) serves as the Single Source of Truth for all Actdim UI standards (semantic design tokens, Tailwind v4 integration, Dynstruct component conventions, adaptive overlays, and layout services).

All instructions for migration, Tailwind v4 setup, 1-liner code bridges, theme extension policy, and clean-room documentation purge are formally specified in `@actdim/ui-core/docs/topic--developer-guide.md` (specifically Section 5 "Theme Extension Policy" and Section 6 "Project Migration & Adoption Walkthrough").

Previous migration guidelines were overly rigid and caused unintended loss of application-specific documentation in other repositories. This task applies the calibrated Clean-Room procedure from Section 6:
1. Preserve all application-specific architecture, domain models, navigation routes, and backend adapters.
2. Purge only duplicate UI conventions (`topic--frontend-conventions.md`, `topic--theme-tokens.md`) to eliminate slug collisions.
3. Record only the application delta in architecture (permitted third-party Tailwind plugins, layout utilities, and local CSS variables per Section 5).
4. Establish 1-liner re-export bridges for theme, layout, and overlays to eliminate refactoring friction.

## Acceptance Criteria

### Phase 1: Package Upgrades & Dependency Registration
- [x] In `packages/dashboard-ui/package.json`:
  - Upgrade `@actdim/dynstruct` to `^1.9.1`.
  - Upgrade `@actdim/dynstruct-mui` to `^1.9.1`.
  - Upgrade `@actdim/msgmesh` to `^1.9.1`.
  - Upgrade `@actdim/utico` to `^1.9.1`.
  - Add `@actdim/ui-core`: `^1.9.1`.
- [x] Run `pnpm install` in `packages/dashboard-ui`.
- [x] Run `along dep-scan --link` to register `@actdim/ui-core/llms.txt` in `docs/topic--dependencies.md`.

### Phase 2: Direct Library Integration & Tailwind v4 (Section 6 Step 2)
- [x] In `src/index.css`: import `@actdim/ui-core/theme.css` alongside Tailwind v4, retaining local plugins (`@iconify/tailwind4`) per Section 5.
- [x] Direct library imports established: components import directly from `@actdim/ui-core/*` without redundant local wrappers or bridge files.

### Phase 3: Clean-Room Documentation Purge & AGENTS.md Streamlining (Section 6 Steps 3-5)
- [x] Run `git rm packages/dashboard-ui/docs/topic--frontend-conventions.md` (slug belongs exclusively to `@actdim/ui-core`).
- [x] Do NOT leave stubs.
- [x] Update `packages/dashboard-ui/docs/INDEX.md` and `llms.txt` to point frontend conventions lookups to `@actdim/ui-core`.
- [x] Streamline `packages/dashboard-ui/AGENTS.md` and root `AGENTS.md`:
  - Replace verbose UI rule listings with the standard 2-line invariant:
    ```markdown
    - **UI & Frontend Invariants**: All UI guidelines, component models, design tokens, adaptive layout tiers, and overlay rules are governed exclusively by `@actdim/ui-core` (`node_modules/@actdim/ui-core/docs/INDEX.md`). Application-specific architecture is defined in `docs/topic--architecture.md`.
    ```
  - Retain all application-specific invariants (NSwag generation, MsgMesh bus adapters, DOMPurify sanitization, CSP rules).
- [x] In `packages/dashboard-ui/docs/topic--architecture.md`:
  - Document the application delta per Section 6 Step 5: core tokens from `@actdim/ui-core` via `tw()`, application plugins, application layout utilities/CSS variables, and reference to `@actdim/ui-core/docs/topic--developer-guide.md`.
  - Satisfy Along taxonomy contracts (`## Topology`, `## Core Components`, `## Data Flow`, `## Invariants`).
- [x] Populate `topic--setup-and-workflow.md` and `topic--domain-model.md` to eliminate zombie stubs.

### Phase 4: Quality Gates & Verification
- [x] Run `pnpm run typecheck` in `packages/dashboard-ui`: 0 TypeScript compiler errors.
- [x] Run `pnpm test` in `packages/dashboard-ui`: 100% test pass rate.
- [x] Run `pnpm run build` in `packages/dashboard-ui`: clean bundle.
- [x] Run `along doctor`: 0 zombie stubs in `packages/dashboard-ui/docs/`.
- [x] Run `along kb-sync`: 0 broken relative Markdown links.
- [x] Run `along sanitize --check`: 0 banned Unicode characters.
