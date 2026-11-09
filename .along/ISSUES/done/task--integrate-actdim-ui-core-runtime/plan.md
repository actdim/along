# Living Plan: Integrate @actdim/ui-core Runtime Dependencies and CSS Tokens into Dashboard UI

## Execution Mode
Role-Based (`along-team`): dependency upgrade across 5 `@actdim/*` packages plus a major MUI
upgrade, CSS reconciliation and new component tests.

## Revision note (2026-11-08 review)
Verified against npm and `packages/dashboard-ui`:
- All five packages are published at `1.12.2` (`ui-core`, `dynstruct`, `dynstruct-mui`,
  `msgmesh`, `utico`).
- `@actdim/ui-core@1.12.2` peers: `react`/`react-dom >=19.2.0`, `i18next >=24.0.0`,
  `postcss >=8.5.0`, `@mui/material >=9.0.1`, `@emotion/react >=11.14.0`,
  `@emotion/styled >=11.14.1`, `@actdim/{dynstruct,dynstruct-mui,msgmesh} >=1.12.2`.
- `@actdim/dynstruct-mui@1.12.2` peers additionally: `mobx >=6.15.0`, `rxjs >=7.8.2`,
  `uuid >=13.0.0`, `jwt-decode >=4.0.0`, `http-status >=2.1.0`, `react-router >=7.9.3`,
  `@actdim/utico >=1.12.2`.
- The dashboard pins `@mui/material ^6.4.0`. The installed `ui-core@1.9.1` already requires
  `>=9.0.1`, so the peer contract is broken today. The previous plan kept `^6.4.0` and rated the
  risk "low"; that was wrong.
- The dashboard does not import `@mui/material` directly; MUI arrives through
  `@actdim/dynstruct-mui/{Dialog,Drawer,Tabs}`. The direct exposure is the CSS overrides in
  `src/index.css` that target `.MuiDrawer-paper`, `.MuiDialog-paper`, `.MuiPaper-root`,
  `.MuiBackdrop-root`.
- `jwt-decode`, `http-status`, `react-router`, `postcss` are not declared in the dashboard.
- Tokens used by the plan exist in `theme.css` (`surface-page`, `surface-panel`, `surface-inset`,
  `surface-scrim`, `line-default`, `line-strong`, `line-muted`, `fg-default`, `fg-muted`);
  `tw()` is exported from `@actdim/ui-core/theme`.
- `useIssuesView` / `selectIssue` and `useSearchModal` / `performSearch` / `selectResult` exist;
  `performSearch` filters `m.data` locally (not `m.props.data`).
- No `pnpm-workspace.yaml` at the repo root; confirm `pnpm --filter @along/dashboard-ui ...`
  resolves, otherwise run the commands inside `packages/dashboard-ui`.

## Phase 0: Decide and de-risk the MUI 9 upgrade
1. Read the `@actdim/ui-core` changelog / docs (`node_modules/@actdim/ui-core/docs/INDEX.md`)
   for 1.9.1 -> 1.12.2 breaking notes; do not rely on SemVer alone.
2. Read the MUI v7, v8, v9 migration guides for: renamed global class names, `Paper`/`Dialog`/
   `Drawer` slot changes, Emotion requirements.
3. Decision recorded in the issue: upgrade to MUI 9 now (default), or pin `@actdim/*` to the last
   version that accepts MUI 6 (if any exists). If the change is non-trivial, record an ADR.

## Phase 1: Dependencies
1. `packages/dashboard-ui/package.json`: all `@actdim/*` -> `^1.12.2`; `@mui/material` -> `^9.0.1`;
   add `i18next ^24`, `jwt-decode ^4`, `http-status ^2.1`, `react-router ^7.9.3`, `postcss ^8.5`
   (dev or runtime per how Vite consumes it); keep `mobx`, `mobx-react-lite`, `rxjs`,
   `@emotion/*`, `uuid`.
2. `pnpm install` in `packages/dashboard-ui`; `pnpm-lock.yaml` updated; zero unmet-peer warnings
   (`pnpm install` output captured in the issue).
3. Gate: `typecheck`, `test`, `build` green before touching CSS.

## Phase 2: Runtime check of MUI-backed views
Start the dashboard (`/along-dev` or `npm run dev`) against a fixture repo and check Drawer,
Dialog and Tabs open, render and close; compare screenshots before/after. Fix the class-name
overrides in `index.css` that no longer match.

## Phase 3: CSS tokens
Replace hardcoded colours in `src/index.css` with `ui-core` tokens:
`body` -> `bg-surface-page text-fg-default`; scrollbar track/thumb/hover -> `surface-inset`,
`line-default`, `line-strong`; markdown headings/code/tables -> `fg-default`, `line-muted`,
`surface-inset`, `surface-panel`; MUI overrides -> `surface-panel`, `line-default`,
`fg-default`, backdrop -> `surface-scrim`. Re-check `!important` overrides are still needed after
MUI 9; remove those that are not.

## Phase 4: tw() adoption (scoped)
Use `tw()` only in `IssuesKanbanView` and `SearchModal` (the components being tested), keeping
`iconify lucide--*` classes concatenated. Wider adoption is a follow-up.

## Phase 5: Vitest component tests (happy-dom)
- `IssuesKanbanView.test.tsx`: initial model state, search/status/type/priority filters and their
  intersection, `selectIssue` publishes `APP.ENTITY.SELECT` with `{ id, type }`, DOM renders the
  filter controls.
- `SearchModal.test.tsx`: `open`/`close`, `performSearch` over `m.data` (match and empty query
  reset), `selectResult` closes and publishes `APP.ENTITY.SELECT`.
Follow the `@actdim/dynstruct` testing conventions from the `ui-core` docs; zero `any`/`as`.

## Verification
`pnpm --filter @along/dashboard-ui typecheck`, `... test`, `... build` (or in-package
equivalents); visual check from Phase 2; `python scripts/sanitize_typography.py --check`.

## Risks
- MUI 6 -> 9: high; contained by Phase 0 decision and the Phase 2 runtime check.
- New peers (`react-router`, `jwt-decode`, `http-status`) add bundle weight only if imported;
  confirm with the build size report.
