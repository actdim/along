---
protocol: along
protocol_version: "4.4.14"
date: 2026-10-15
slug: align-dashboard-conventions
agent: antigravity
branch: main
commit: 7a8f8e1
summary: Refactor dashboard-ui to full Dynstruct and MsgMesh conventions compliance
issues_advanced: []
issues_completed: [debt--align-dashboard-conventions]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Align dashboard conventions

## Summary
Refactor dashboard-ui to full Dynstruct and MsgMesh conventions compliance

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `packages/dashboard-ui/.along/.session/align-dashboard-conventions/plan.md` | state | 1 | 2026-10-15T10:52:17Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |
| `packages/dashboard-ui/.along/ISSUES/debt--align-dashboard-conventions.md` | state | 1 | 2026-10-15T11:17:55Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |
| `packages/dashboard-ui/src/App.tsx` | source | 1 | 2026-10-15T10:58:41Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |
| `packages/dashboard-ui/src/bus.ts` | source | 7 | 2026-10-15T11:12:36Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |
| `packages/dashboard-ui/src/components/DAGGraphView.tsx` | source | 2 | 2026-10-15T11:03:06Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |
| `packages/dashboard-ui/src/components/EntityDrawer.tsx` | source | 8 | 2026-10-15T11:12:52Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |
| `packages/dashboard-ui/src/components/Header.tsx` | source | 2 | 2026-10-15T11:02:45Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |
| `packages/dashboard-ui/src/components/IssuesKanbanView.tsx` | source | 2 | 2026-10-15T11:03:00Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |
| `packages/dashboard-ui/src/components/KBExplorerView.tsx` | source | 2 | 2026-10-15T11:03:15Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |
| `packages/dashboard-ui/src/components/OverviewView.tsx` | source | 2 | 2026-10-15T11:02:54Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |
| `packages/dashboard-ui/src/components/SearchModal.tsx` | source | 2 | 2026-10-15T11:03:30Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |
| `packages/dashboard-ui/src/components/SessionsDecisionsView.tsx` | source | 2 | 2026-10-15T11:03:24Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |
| `packages/dashboard-ui/src/index.css` | source | 1 | 2026-10-15T10:52:30Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |
| `packages/dashboard-ui/src/main.tsx` | source | 3 | 2026-10-15T10:59:04Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |
| `packages/dashboard-ui/src/services/apiService.ts` | source | 3 | 2026-10-15T11:09:09Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |

### Plan

#### Plan: align-dashboard-conventions

##### Summary
Refactor `@along/dashboard-ui` to fully comply with all Dynstruct, MsgMesh, Overlays, and Styling conventions documented in `docs/topic--frontend-conventions.md`.

##### Steps
1. **CSS & Icons**:
   - Register `@plugin "@iconify/tailwind4";` in `src/index.css`.
   - Replace `@iconify/react` `<Icon icon="..." />` components with CSS classes (`iconify <prefix>--<name>`).
2. **Bus & Services**:
   - In `src/bus.ts`: type `dashboardBus` as `MsgBus<DashboardAppMsgStruct>` (eliminate `any`).
   - In `src/services/apiService.ts`: clean up types (eliminate `any`).
   - Deduplicate `DashboardApiService.start()` call between `src/main.tsx` and `src/App.tsx`.
3. **Overlays & Dialogs**:
   - In `src/components/SearchModal.tsx`:
     - Replace raw `@mui/material/Dialog` with `@actdim/dynstruct-mui/Dialog` (`useDialog`) in `def.children`.
     - Remove `onClose` callback prop. Implement two-way binding on `open`.
     - Eliminate `as any`.
   - In `src/components/EntityDrawer.tsx`:
     - Remove `onClose` callback prop. Host coordinates via two-way binding on `open`.
     - Render drawer content via host fragment child bound with `children: bind(() => <c.children.DrawerBody />)`.
     - Eliminate `(n: any)`.
4. **Components & Messaging**:
   - In `src/components/Header.tsx`: remove `onSearchClick` prop; use bus command `APP.SEARCH.OPEN` with `group: 'ex'`.
   - In all components: add explicit `group: 'ex'` for `c.msgBus.send`, `group: 'in'` for `c.msgBus.request`.
   - In `src/App.tsx`: remove callback props passed to children; use two-way bindings.
   - Fix all single-line control flow blocks into multi-line `{ ... }`.
5. **Verification**:
   - `pnpm run typecheck`
   - `pnpm test`
   - `pnpm run build`
   - `along kb sync`
   - `along sanitize`

##### Acceptance Criteria
- [x] Zero callback props in overlays and components
- [x] SearchModal uses useDialog from @actdim/dynstruct-mui
- [x] EntityDrawer content rendered via fragment child binding
- [x] Zero any and zero as type assertions in dashboard source code
- [x] Zero @iconify/react JSX tags; CSS classes used exclusively
- [x] pnpm run typecheck passes
- [x] pnpm test passes
- [x] pnpm run build passes
- [x] along sanitize clean

### Execution Trace

#### Execution Trace: align-dashboard-conventions
- 2026-10-15T10:52:17Z edit packages/dashboard-ui/.along/.session/align-dashboard-conventions/plan.md
- 2026-10-15T10:52:21Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: 43e81c755d1f
- 2026-10-15T10:52:30Z edit packages/dashboard-ui/src/index.css
- 2026-10-15T10:53:16Z edit packages/dashboard-ui/src/bus.ts
- 2026-10-15T10:53:29Z edit packages/dashboard-ui/src/services/apiService.ts
- 2026-10-15T10:53:34Z denied [require_plan_approval] run_command: Unclassified Tool Nature [gate: require-plan-approval]: Tool or command 'node const d = require('@actdim/dynstruct-mui/Dialog'); console.log(Object.keys(d))'...
- 2026-10-15T10:55:12Z edit packages/dashboard-ui/src/components/Header.tsx
- 2026-10-15T10:55:42Z edit packages/dashboard-ui/src/components/SearchModal.tsx
- 2026-10-15T10:56:10Z edit packages/dashboard-ui/src/components/EntityDrawer.tsx
- 2026-10-15T10:56:33Z edit packages/dashboard-ui/src/components/OverviewView.tsx
- 2026-10-15T10:56:57Z edit packages/dashboard-ui/src/components/IssuesKanbanView.tsx
- 2026-10-15T10:57:23Z edit packages/dashboard-ui/src/components/DAGGraphView.tsx
- 2026-10-15T10:57:54Z edit packages/dashboard-ui/src/components/KBExplorerView.tsx
- 2026-10-15T10:58:11Z edit packages/dashboard-ui/src/components/SessionsDecisionsView.tsx
- 2026-10-15T10:58:41Z edit packages/dashboard-ui/src/App.tsx
- 2026-10-15T10:59:04Z edit packages/dashboard-ui/src/main.tsx (x3)
- 2026-10-15T10:59:48Z denied [workspace_containment] run_command: Workspace containment violation [gate: workspace-containment]: Shell working directory outside the allowed scope: 'd:\src\my\actdim\mempart\src\apps\webapp'....
- 2026-10-15T11:00:15Z edit packages/dashboard-ui/src/bus.ts
- 2026-10-15T11:02:36Z edit packages/dashboard-ui/src/components/EntityDrawer.tsx (x2)
- 2026-10-15T11:02:45Z edit packages/dashboard-ui/src/components/Header.tsx
- 2026-10-15T11:02:54Z edit packages/dashboard-ui/src/components/OverviewView.tsx
- 2026-10-15T11:03:00Z edit packages/dashboard-ui/src/components/IssuesKanbanView.tsx
- 2026-10-15T11:03:06Z edit packages/dashboard-ui/src/components/DAGGraphView.tsx
- 2026-10-15T11:03:15Z edit packages/dashboard-ui/src/components/KBExplorerView.tsx
- 2026-10-15T11:03:24Z edit packages/dashboard-ui/src/components/SessionsDecisionsView.tsx
- 2026-10-15T11:03:30Z edit packages/dashboard-ui/src/components/SearchModal.tsx
- 2026-10-15T11:06:12Z edit packages/dashboard-ui/src/bus.ts
- 2026-10-15T11:06:17Z edit packages/dashboard-ui/src/components/EntityDrawer.tsx
- 2026-10-15T11:07:31Z denied [workspace_containment] run_command: Workspace containment violation [gate: workspace-containment]: Shell working directory outside the allowed scope: 'd:\src\my\actdim\mempart\src\apps\webapp'....
- 2026-10-15T11:08:47Z edit packages/dashboard-ui/src/bus.ts
- 2026-10-15T11:08:53Z edit packages/dashboard-ui/src/components/EntityDrawer.tsx
- 2026-10-15T11:09:09Z edit packages/dashboard-ui/src/services/apiService.ts (x2)
- 2026-10-15T11:11:08Z edit packages/dashboard-ui/src/components/EntityDrawer.tsx
- 2026-10-15T11:12:36Z edit packages/dashboard-ui/src/bus.ts (x3)
- 2026-10-15T11:12:52Z edit packages/dashboard-ui/src/components/EntityDrawer.tsx (x2)
- 2026-10-15T11:17:55Z edit packages/dashboard-ui/.along/ISSUES/debt--align-dashboard-conventions.md
- 2026-10-15T11:21:42Z test pass (along test)
- 2026-10-15T11:22:40Z test pass (Wrap Quality Gate)
