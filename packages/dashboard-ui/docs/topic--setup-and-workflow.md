---
protocol: along
slug: setup-and-workflow
title: Dashboard UI Setup, Installation & Developer Workflow
type: setup-workflow
created: 2026-09-29
updated: 2026-10-16
tags: [setup, workflow, installation, lifecycle, quality-gates]
---

# Dashboard UI Setup, Installation & Developer Workflow

This guide details the development environment setup, execution commands, and verification gates for `@along/dashboard-ui`.

---

## Prerequisites

To build and run the Dashboard UI package:

- **Node.js**: Version 20 LTS or higher (`node -v >= 20.0.0`).
- **Package Manager**: `pnpm` version 10.x (`pnpm -v >= 10.0.0`).
- **Dependencies**: All packages listed in `package.json`, including `@actdim/ui-core@^1.9.1` and `@actdim/dynstruct@^1.9.1`.
- **Along CLI**: `along` command available on `PATH` for running protocol gates and KB sync.

---

## Runner Commands

All scripts are executed from the `packages/dashboard-ui` working directory:

### Development Server
Starts the Vite dev server with hot module replacement (HMR):
```bash
pnpm run dev
```

### Static Build
Compiles TypeScript types and produces optimized production bundles in `dist/`:
```bash
pnpm run build
```

### Type Checking
Performs strict TypeScript verification without emitting javascript files:
```bash
pnpm run typecheck
```

### Automated Unit Tests
Runs the test suite using Vitest with Happy-DOM:
```bash
pnpm test
```

### API Client Generation
Re-generates typed TypeScript API clients from `openapi.json` using NSwag:
```bash
pnpm run generate:api
```

---

## Quality Gates

Before submitting changes or closing tasks in `packages/dashboard-ui`, all of the following quality checks must pass:

1. **Type Safety (`typecheck`)**:
   `pnpm run typecheck` must finish with 0 compiler errors. No `any` or `as` type casts.
2. **Test Suite (`test`)**:
   `pnpm test` must achieve a 100% pass rate.
3. **Production Build (`build`)**:
   `pnpm run build` must produce clean Vite output without bundling warnings.
4. **Clean ASCII Gate (`along sanitize`)**:
   `along sanitize --check` must detect 0 prohibited typographic or invisible characters.
5. **Knowledge Base Integrity (`along kb-sync`)**:
   `along kb-sync` must verify 0 broken relative Markdown links across topic files.
