---
protocol: along
protocol_version: "4.4.12"
date: 2026-10-14
slug: update-overlay-conventions
agent: antigravity
branch: main
commit: 02c7b9c
summary: Apply generalized overlay and modal conventions from mempart
issues_advanced: []
issues_completed: [task--update-overlay-conventions]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Update overlay conventions

## Summary
Apply generalized overlay and modal conventions from mempart

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `packages/dashboard-ui/.along/.session/update-overlay-conventions/plan.md` | state | 1 | 2026-10-14T09:51:46Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |
| `packages/dashboard-ui/.along/ISSUES/task--update-overlay-conventions.md` | state | 1 | 2026-10-14T09:52:15Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |
| `packages/dashboard-ui/docs/topic--frontend-conventions.md` | docs | 1 | 2026-10-14T09:52:03Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |

### Plan

#### Plan: update-overlay-conventions

##### Summary
Apply generalized overlay and modal UI conventions (section 3a / 4) from `mempart/src/apps/webapp/docs/topic--frontend-conventions.md` into `packages/dashboard-ui/docs/topic--frontend-conventions.md`.

##### Steps
1. Update Section 4 in `packages/dashboard-ui/docs/topic--frontend-conventions.md` to incorporate the new expanded guidelines:
   - Explicit prohibition of `onClose`, `onOpen`, `onDismiss` callback props.
   - Clarified two-way binding on `open` (`bindProp` and `bind(get, set)` with code example for anchor cleanup).
   - Live content via fragment children (`<c.children.DialogBody />`).
   - Hardware Back button and escape lifecycle handling via `def.effects` and `onDestroy`.
   - Canonical overlay primitives (`useDrawer`, `useDialog`, `useMenu` from `@actdim/dynstruct-mui`).
2. Run `along kb sync` in dashboard-ui to keep index clean.
3. Verify typography with `along sanitize`.
4. Wrap the task.

##### Acceptance Criteria
- [x] Overlays & Modal UI section updated with generalized conventions and code examples
- [x] along kb sync passes cleanly
- [x] along sanitize passes cleanly

### Execution Trace

#### Execution Trace: update-overlay-conventions
- 2026-10-14T09:51:46Z edit packages/dashboard-ui/.along/.session/update-overlay-conventions/plan.md
- 2026-10-14T09:51:49Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: 9fb5a4cfbed3
- 2026-10-14T09:52:03Z edit packages/dashboard-ui/docs/topic--frontend-conventions.md
- 2026-10-14T09:52:15Z edit packages/dashboard-ui/.along/ISSUES/task--update-overlay-conventions.md
- 2026-10-14T09:52:19Z test pass (Wrap Quality Gate)
