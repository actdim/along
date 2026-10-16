---
protocol: along
protocol_version: "4.4.15"
slug: reconcile-dashboard-ui-core-conventions
title: Reconcile Dashboard UI Conventions and Documentation with @actdim/ui-core
type: task
status: open
priority: high
created: 2026-10-16
updated: 2026-10-16
agent: antigravity
tags: [dashboard-ui, ui-core, conventions, docs, cleanup, taxonomy]
parent: task--migrate-to-actdim-ui-core
blocked_by: []
related: []
---

# Reconcile Dashboard UI Conventions and Documentation with @actdim/ui-core

## Context & Purpose

The foundational package `@actdim/ui-core` now serves as the Single Source of Truth for all Actdim UI standards (tokens, Dynstruct conventions, MobX bans, overlays, and layout services).

`packages/dashboard-ui` previously maintained a local copy of frontend conventions (`docs/topic--frontend-conventions.md`), causing slug collisions and documentation duplication. In addition, `packages/dashboard-ui/docs/` contains 3 zombie documentation stubs flagged by `along doctor` (`topic--architecture.md`, `topic--domain-model.md`, `topic--setup-and-workflow.md`).

This task removes duplicate conventions, routes knowledge lookups to `@actdim/ui-core`, streamlines AGENTS.md, and brings remaining dashboard documentation into full Along taxonomy compliance.

## Acceptance Criteria & Execution Checklist

### Phase 1: Physical Document Deletion & Topic Index Routing
- [ ] Run `git rm docs/topic--frontend-conventions.md` (slug `frontend-conventions` belongs exclusively to `@actdim/ui-core`).
- [ ] Do NOT create stubs or bridge files (violates anti-stub injection gate).
- [ ] Update `docs/INDEX.md` and `llms.txt`:
  - Route all frontend conventions, token catalogs, and overlay specifications directly to `@actdim/ui-core`.
  - Re-link remaining application-specific topics.

### Phase 2: AGENTS.md Invariant Streamlining
- [ ] In `packages/dashboard-ui/AGENTS.md`:
  - Remove duplicated Dynstruct callback policies, MobX rules, and overlay lifecycle listings.
  - Insert standard UI invariant block:
    ```markdown
    - **UI & Frontend Invariants**: All UI guidelines, component models, design tokens, adaptive layout tiers, and overlay rules are governed exclusively by `@actdim/ui-core` (`node_modules/@actdim/ui-core/docs/INDEX.md`). Application-specific architecture is defined in `docs/topic--architecture.md`.
    ```
  - Preserve dashboard-specific invariants: NSwag API generation (`pnpm run generate:api`), MsgMesh bus adapters, DOMPurify sanitization, and CSP constraints.
- [ ] In root `AGENTS.md`:
  - Update Frontend summary under "Project specifics" to point to `@actdim/ui-core` and dashboard architecture.

### Phase 3: Documentation Taxonomy Compliance (Zombie Stub Elimination)
Ensure all remaining application-specific documentation files are fully populated and satisfy Along regex taxonomy contracts:
- [ ] `docs/topic--architecture.md` (`type: architecture`):
  - Must contain required taxonomy sections: `## Topology`, `## Core Components`, `## Data Flow`, `## Invariants`.
  - Document dashboard views (`OverviewView`, `IssuesKanbanView`, `DAGGraphView`, `KBExplorerView`, `SessionsDecisionsView`), `EntityDrawer`, `SearchModal`, and `DashboardApiService`.
- [ ] `docs/topic--setup-and-workflow.md` (`type: setup-workflow`):
  - Must contain required taxonomy sections: `## Prerequisites`, `## Runner Commands`, `## Quality Gates`.
  - Document Node/pnpm requirements, Vite dev server, typecheck, test, and build commands.
- [ ] `docs/topic--domain-model.md` (`type: domain-model`):
  - Must contain required taxonomy sections: `## Entity Taxonomy`, `## Front-Matter Schemas`, `## Graph Relationships`.
  - Document Along entity visualization models (Issues, Milestones, Decisions, Sessions, DAG graph nodes/edges).

### Phase 4: Verification & Quality Gates
- [ ] Run `along sanitize --check`: 0 typographic errors.
- [ ] Run `along kb sync`: docs index compiled, zero broken links.
- [ ] Run `along doctor`: zero zombie stub warnings, zero errors.
- [ ] Run `pnpm test` and `pnpm run build` in dashboard-ui.
