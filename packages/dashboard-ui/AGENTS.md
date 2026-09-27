<!-- BEGIN ALONG-PROTOCOL ref=../../AGENTS.md (managed by along-init - do not edit by hand) -->
This folder belongs to a repository that uses the ALONG structure. The full working
guidance + agent-context protocol live once in the nearest ancestor `AGENTS.md` (`../../AGENTS.md`) -
read it there. This folder keeps its OWN `.along/` state; use the nearest one.
Only this folder's specifics follow.
<!-- END ALONG-PROTOCOL -->

# Agent Context: Along Dashboard UI (`@along/dashboard-ui`)

This document defines the local agent context boundary and engineering rules for `packages/dashboard-ui/`.

## Nearest Context Boundary

When working on the dashboard frontend:
- Follow all architectural rules and invariants documented in [README.md](./README.md).
- Adhere to the strict Dynstruct component model (`@actdim/dynstruct` + `@actdim/dynstruct-mui`).
- Never introduce raw React component state (`useState`, `useMemo`, `useCallback`, `useEffect`). All component state belongs in `c.model` (MobX).
- Never use untyped casting (`any` or `as ...`). Maintain 100% strict TypeScript typing.
- Never write manual `fetch` calls or manual API channel maps. Use NSwag client generator (`pnpm run generate:api`) and dynamic bus adapters (`@actdim/msgmesh/adapters`).
- Sanitize all rendered Markdown using DOMPurify and enforce strict CSP on Mermaid diagrams.

## Verification & Quality Gates

Run the following checks before concluding any change in this package:
```bash
pnpm run typecheck
pnpm test
pnpm run build
```

## Project specifics

<!-- BEGIN ALONG-RULES -->
See the following engineering guidelines:
- `[languages/typescript.md](.along/rules/languages/typescript.md)`
- `[platforms/web.md](.along/rules/platforms/web.md)`
<!-- END ALONG-RULES -->
