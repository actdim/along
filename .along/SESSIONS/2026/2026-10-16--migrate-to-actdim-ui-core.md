---
protocol: along
protocol_version: "4.4.16"
date: 2026-10-16
slug: migrate-to-actdim-ui-core
agent: antigravity
branch: main
commit: a14d96d
summary: Migrate dashboard UI foundations to @actdim/ui-core
issues_advanced: []
issues_completed: [task--migrate-to-actdim-ui-core]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Migrate Dashboard UI to @actdim/ui-core and Reconcile Conventions

## Summary
Migrate dashboard UI foundations to @actdim/ui-core

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

| Step | Title | Status | Retries | Review |
| --- | --- | --- | --- | --- |
| 1 | Migrate Dashboard UI to @actdim/ui-core and Reconcile Conventions | passed | 0 | no |

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/task--migrate-to-actdim-ui-core.md` | state | 4 | 2026-10-16T14:31:32Z | antigravity--3ddfa7ba-c12b-4979-8d1d-392e7a080b3e |
| `AGENTS.md` | docs | 1 | 2026-10-16T14:21:13Z | antigravity--3ddfa7ba-c12b-4979-8d1d-392e7a080b3e |
| `packages/dashboard-ui/AGENTS.md` | source | 1 | 2026-10-16T14:21:04Z | antigravity--3ddfa7ba-c12b-4979-8d1d-392e7a080b3e |
| `packages/dashboard-ui/README.md` | source | 1 | 2026-10-16T14:22:29Z | antigravity--3ddfa7ba-c12b-4979-8d1d-392e7a080b3e |
| `packages/dashboard-ui/docs/topic--architecture.md` | docs | 2 | 2026-10-16T14:29:20Z | antigravity--3ddfa7ba-c12b-4979-8d1d-392e7a080b3e |
| `packages/dashboard-ui/docs/topic--domain-model.md` | docs | 1 | 2026-10-16T14:22:00Z | antigravity--3ddfa7ba-c12b-4979-8d1d-392e7a080b3e |
| `packages/dashboard-ui/docs/topic--setup-and-workflow.md` | docs | 1 | 2026-10-16T14:21:51Z | antigravity--3ddfa7ba-c12b-4979-8d1d-392e7a080b3e |
| `packages/dashboard-ui/package.json` | source | 1 | 2026-10-16T14:19:41Z | antigravity--3ddfa7ba-c12b-4979-8d1d-392e7a080b3e |
| `packages/dashboard-ui/src/components/core/ActionSheet.tsx` | source | 1 | 2026-10-16T14:20:27Z | antigravity--3ddfa7ba-c12b-4979-8d1d-392e7a080b3e |
| `packages/dashboard-ui/src/components/core/AdaptiveDialog.tsx` | source | 1 | 2026-10-16T14:20:22Z | antigravity--3ddfa7ba-c12b-4979-8d1d-392e7a080b3e |
| `packages/dashboard-ui/src/components/core/AdaptiveMenu.tsx` | source | 1 | 2026-10-16T14:20:31Z | antigravity--3ddfa7ba-c12b-4979-8d1d-392e7a080b3e |
| `packages/dashboard-ui/src/config/muiTheme.ts` | source | 1 | 2026-10-16T14:20:19Z | antigravity--3ddfa7ba-c12b-4979-8d1d-392e7a080b3e |
| `packages/dashboard-ui/src/index.css` | source | 1 | 2026-10-16T14:20:45Z | antigravity--3ddfa7ba-c12b-4979-8d1d-392e7a080b3e |
| `packages/dashboard-ui/src/services/BackStackService.tsx` | source | 2 | 2026-10-16T14:23:09Z | antigravity--3ddfa7ba-c12b-4979-8d1d-392e7a080b3e |
| `packages/dashboard-ui/src/services/LayoutService.tsx` | source | 1 | 2026-10-16T14:20:34Z | antigravity--3ddfa7ba-c12b-4979-8d1d-392e7a080b3e |
| `packages/dashboard-ui/src/theme/tw.ts` | source | 1 | 2026-10-16T14:20:16Z | antigravity--3ddfa7ba-c12b-4979-8d1d-392e7a080b3e |

### Plan

#### Living Plan: migrate-to-actdim-ui-core

Title: Migrate Dashboard UI to @actdim/ui-core and Reconcile Conventions

##### Steps
- [x] Step 1: Upgrade @actdim dependencies to 1.9.1 and add @actdim/ui-core in package.json
- [x] Step 2: Register @actdim/ui-core in dependencies docs via along dep-scan --link
- [x] Step 3: Integrate @actdim/ui-core theme.css into src/index.css and establish direct library imports
- [x] Step 4: Clean-room documentation purge of duplicate topic--frontend-conventions.md and streamline AGENTS.md
- [x] Step 5: Populate dashboard architecture, setup, and domain model docs to eliminate zombie stubs
- [x] Step 6: Verify TypeScript types, unit tests, Vite production build, link integrity, and clean ASCII

### Execution Trace

#### Execution Trace: migrate-to-actdim-ui-core
- 2026-10-16T14:19:02Z plan approved (along start --approved; approved_via: cli-unverified)
- 2026-10-16T14:19:33Z edit .along/ISSUES/task--migrate-to-actdim-ui-core.md
- 2026-10-16T14:19:41Z edit packages/dashboard-ui/package.json
- 2026-10-16T14:20:16Z edit packages/dashboard-ui/src/theme/tw.ts
- 2026-10-16T14:20:19Z edit packages/dashboard-ui/src/config/muiTheme.ts
- 2026-10-16T14:20:22Z edit packages/dashboard-ui/src/components/core/AdaptiveDialog.tsx
- 2026-10-16T14:20:27Z edit packages/dashboard-ui/src/components/core/ActionSheet.tsx
- 2026-10-16T14:20:31Z edit packages/dashboard-ui/src/components/core/AdaptiveMenu.tsx
- 2026-10-16T14:20:34Z edit packages/dashboard-ui/src/services/LayoutService.tsx
- 2026-10-16T14:20:38Z edit packages/dashboard-ui/src/services/BackStackService.tsx
- 2026-10-16T14:20:45Z edit packages/dashboard-ui/src/index.css
- 2026-10-16T14:21:04Z edit packages/dashboard-ui/AGENTS.md
- 2026-10-16T14:21:13Z edit AGENTS.md
- 2026-10-16T14:21:43Z edit packages/dashboard-ui/docs/topic--architecture.md
- 2026-10-16T14:21:51Z edit packages/dashboard-ui/docs/topic--setup-and-workflow.md
- 2026-10-16T14:22:00Z edit packages/dashboard-ui/docs/topic--domain-model.md
- 2026-10-16T14:22:13Z denied [projection_protection] write_to_file: Projection Protection Violation: Direct manual edits to 'd:\Src\my\actdim\public\along\packages\dashboard-ui\docs\INDEX.md' are forbidden. The Single Source ...
- 2026-10-16T14:22:29Z edit packages/dashboard-ui/README.md
- 2026-10-16T14:23:09Z edit packages/dashboard-ui/src/services/BackStackService.tsx
- 2026-10-16T14:29:20Z edit packages/dashboard-ui/docs/topic--architecture.md
- 2026-10-16T14:31:32Z edit .along/ISSUES/task--migrate-to-actdim-ui-core.md (x3)
- 2026-10-16T14:35:44Z test pass (Wrap Quality Gate)
