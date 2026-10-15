---
protocol: along
protocol_version: "4.4.14"
date: 2026-10-15
slug: align-dynstruct-jsx-callback-policy
agent: antigravity
branch: main
commit: 7a8f8e1
summary: Incorporate Dynstruct prop-less JSX and callback policy into frontend conventions
issues_advanced: []
issues_completed: [docs--align-dynstruct-jsx-callback-policy]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Align dynstruct jsx callback policy

## Summary
Incorporate Dynstruct prop-less JSX and callback policy into frontend conventions

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `packages/dashboard-ui/.along/.session/align-dynstruct-jsx-callback-policy/plan.md` | state | 1 | 2026-10-15T16:06:39Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |
| `packages/dashboard-ui/.along/ISSUES/docs--align-dynstruct-jsx-callback-policy.md` | state | 1 | 2026-10-15T16:11:22Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |
| `packages/dashboard-ui/docs/topic--frontend-conventions.md` | docs | 3 | 2026-10-15T16:09:03Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |
| `packages/dashboard-ui/src/App.tsx` | source | 2 | 2026-10-15T16:09:46Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |
| `packages/dashboard-ui/src/components/SearchModal.tsx` | source | 3 | 2026-10-15T16:10:27Z | antigravity--27a574d6-2242-47a0-8958-963a30913aec |

### Plan

#### Plan: Align Dynstruct Conventions, Prop-Less JSX & Callback Policy

Execution Mode: Direct

1. Documentation Update:
   - Update `packages/dashboard-ui/docs/topic--frontend-conventions.md` to add dedicated section "2. Dynstruct Conventions, Prop-Less JSX & Callback Policy" containing:
     - Prop-less JSX (`<c.children.Name />` without inline props/callbacks).
     - Low-level event handlers in `def.children` (`onClick`, `onClose`, `onChange` on MUI/DOM primitives are allowed and standard).
     - Inter-component coordination without callback-drilling (MsgMesh bus events + two-way `bindProp`).
     - Overlays & dialogs policy (`AdaptiveDialog`, `useDialog` with `onClose` and `open: bindProp(...)`).
   - Renumber subsequent sections accordingly.

2. Implementation Verification & Alignment:
   - Verify `packages/dashboard-ui/src/App.tsx`:
     - Ensure `useEntityDrawer` uses canonical `selectedEntityId: bindProp(() => m, 'selectedEntityId')`.
   - Verify `packages/dashboard-ui/src/components/SearchModal.tsx`:
     - Ensure `dialog: useDialog` uses `open: bindProp(() => m, 'isOpen')` and `onClose: () => { m.close(); }`.
   - Confirm all other views maintain clean prop-less JSX and communicate strictly via MsgMesh.

3. Quality Gates & Verification:
   - Run `pnpm run typecheck`
   - Run `pnpm test`
   - Run `pnpm run build`
   - Run `along sanitize`
   - Run `along kb sync`

4. Issue Closeout & Wrap:
   - Tick acceptance criteria in `docs--align-dynstruct-jsx-callback-policy.md`.
   - Run `along test` and `along wrap align-dynstruct-jsx-callback-policy`.

### Execution Trace

#### Execution Trace: align-dynstruct-jsx-callback-policy
- 2026-10-15T16:06:39Z edit packages/dashboard-ui/.along/.session/align-dynstruct-jsx-callback-policy/plan.md
- 2026-10-15T16:06:47Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: 7ce58e84a6a5
- 2026-10-15T16:09:03Z edit packages/dashboard-ui/docs/topic--frontend-conventions.md (x3)
- 2026-10-15T16:09:27Z edit packages/dashboard-ui/src/components/SearchModal.tsx (x2)
- 2026-10-15T16:09:46Z edit packages/dashboard-ui/src/App.tsx (x2)
- 2026-10-15T16:10:27Z edit packages/dashboard-ui/src/components/SearchModal.tsx
- 2026-10-15T16:11:22Z edit packages/dashboard-ui/.along/ISSUES/docs--align-dynstruct-jsx-callback-policy.md
- 2026-10-15T16:15:29Z test pass (along test)
- 2026-10-15T16:15:44Z test pass (Wrap Quality Gate)
