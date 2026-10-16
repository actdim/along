---
protocol: along
protocol_version: "4.4.15"
slug: migrate-to-actdim-ui-core
title: Migrate Dashboard UI to @actdim/ui-core and Reconcile Conventions
type: task
status: open
priority: high
created: 2026-10-16
updated: 2026-10-16
agent: antigravity
tags: [ui-core, migration, conventions, cleanup, dynstruct, dashboard-ui]
blocked_by: []
related: [debt--consolidate-dashboard-ui-subproject]
---

# Migrate Dashboard UI to @actdim/ui-core and Reconcile Conventions

## Context & Problem

The foundational package `@actdim/ui-core` (developed in `mempart/src/packages/ui-core`) serves as the Single Source of Truth for Actdim UI standards, including design tokens, Dynstruct component conventions, callback prohibitions, adaptive overlays, and layout services.

Currently, `packages/dashboard-ui` maintains duplicate frontend conventions in `packages/dashboard-ui/docs/topic--frontend-conventions.md` (causing slug collisions with `@actdim/ui-core`), duplicate rules in `packages/dashboard-ui/AGENTS.md` and root `AGENTS.md`, and 3 zombie documentation stubs in `packages/dashboard-ui/docs/` (`topic--architecture.md`, `topic--domain-model.md`, `topic--setup-and-workflow.md`).

Furthermore, `@actdim/ui-core` needs to be linked or installed into `packages/dashboard-ui`, reconciling peer dependency version requirements (`@actdim/dynstruct` 1.9.0 vs 1.8.3) and migrating CSS tokens.

## Scope & Child Tasks

This migration is divided into two sequential child tasks localized in `packages/dashboard-ui/.along/`:

1. `task--reconcile-dashboard-ui-core-conventions`:
   - Delete duplicate `packages/dashboard-ui/docs/topic--frontend-conventions.md`.
   - Update `packages/dashboard-ui/docs/INDEX.md` and `llms.txt` to route UI conventions to `@actdim/ui-core`.
   - Streamline `packages/dashboard-ui/AGENTS.md` and root `AGENTS.md` with the standard `@actdim/ui-core` invariant block.
   - Populate remaining dashboard documentation (`topic--architecture.md`, `topic--setup-and-workflow.md`, `topic--domain-model.md`) to satisfy Along regex taxonomy contracts and eliminate zombie stubs.

2. `task--integrate-actdim-ui-core-runtime`:
   - Resolve `@actdim/ui-core` package installation (local workspace link vs npm publish) and reconcile `@actdim/*` peer dependency versions.
   - Register dependency in `docs/topic--dependencies.md` via `along dep-scan --link`.
   - Import `@actdim/ui-core` tokens into `packages/dashboard-ui/src/index.css`.
   - Verify build, tests, and type checking (`pnpm run typecheck`, `pnpm test`, `pnpm run build`).

## Acceptance Criteria

- [ ] Child task `task--reconcile-dashboard-ui-core-conventions` completed and verified.
- [ ] Child task `task--integrate-actdim-ui-core-runtime` completed and verified.
- [ ] Root `AGENTS.md` references `@actdim/ui-core` instead of deleted local conventions.
- [ ] `along doctor` reports 0 zombie stubs and 0 slug collisions.
- [ ] Full repository automated tests pass cleanly.
