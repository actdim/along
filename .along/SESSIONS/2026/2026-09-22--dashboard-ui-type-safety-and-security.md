---
protocol: along
protocol_version: "3.9.4"
date: 2026-09-22
slug: dashboard-ui-type-safety-and-security
title: "Dashboard UI NSwag Generation, Type Safety, and Content Security Hardening"
agent: antigravity
branch: main
issues_completed: [debt--dashboard-ui-type-safety-and-security]
issues_advanced: []
decisions: []
tags: [frontend, nswag, typescript, security, xss, mobx, dynstruct]
summary: "Hardened packages/dashboard-ui: regenerated NSwag client eliminating 55 dummy interfaces and all any index signatures, re-exported client schemas in types.ts, replaced manual fetch with client.getFullData, added DOMPurify XSS sanitization, hardened Mermaid security to strict with CSP, replaced stale v2.0.9 badge with dynamic version, added onDestroy keydown and SSE cleanup, and configured vitest test runner with strict linter options."
---

# Session: Dashboard UI NSwag Generation, Type Safety, and Content Security Hardening

## Initial Implementation Plan (Baseline)
1. **Step 1: Backend Protocol Version Schema & OpenAPI Generation**: Add `protocol_version` to `DashboardMetricsSchema`, populate it in `collector.py`, configure camelCase operationId generator in `dashboard/app.py`, and export normalized OpenAPI 3.0.3 schema to `openapi.json`.
2. **Step 2: NSwag Configuration, Client Regeneration, and Type Re-export**: Configure `nswag.json` without `inlineNamedAny`, regenerate client, and replace handwritten duplicate interfaces in `src/types.ts` with direct re-exports from `src/api/client.ts`.
3. **Step 3: API Service Protocol Transport & Lifecycle Cleanup**: Replace manual `fetch('/api/data')` in `apiService.ts` with `DashboardApiClient.prototype.getFullData()`, implement `DashboardApiService.stop()`, add `onDestroy` in `App.tsx` for keydown listener and SSE disconnect, and bind dynamic version to `Header.tsx`.
4. **Step 4: Markdown DOMPurify Sanitization, Mermaid Strictness & CSP Hardening**: Install `dompurify` and `@types/dompurify`, wrap `marked.parse` calls in `EntityDrawer.tsx` and `KBExplorerView.tsx` with `DOMPurify.sanitize()`, configure Mermaid `securityLevel: 'strict'` and add CSP meta tag in `index.html`.
5. **Step 5: Test Infrastructure, Strict TypeScript Checks & Build Verification**: Install `vitest` and `jsdom`, enable `noUnusedLocals` and `noUnusedParameters` in `tsconfig.json`, write comprehensive unit tests, and verify clean production build.

## Execution & Loop Trace (Fixes & Re-plans)
- **Step 1 (Backend Schema & OpenAPI)**: Implemented `custom_generate_unique_id` in `dashboard/app.py` to preserve camelCase operationIds (`getFullData`, `getMetrics`, `listIssues`) across FastAPI exports. Exported normalized OpenAPI 3.0.3 schema with `nullable: true` and `additionalProperties: false`. Reviewer verdict: PASS.
- **Step 2 (NSwag & Types)**: Regenerated `client.ts` with `"inlineNamedAny": false`. Eliminated 55 dummy interfaces with `[key: string]: any;`. Re-exported schemas from `src/api/client.ts` in `src/types.ts`. Fixed property alignment in `SearchModal.tsx` (`file_path: string`, `tags: string[]`, `dec.decision`). Reviewer verdict: PASS.
- **Step 3 (Transport & Lifecycle)**: Replaced `fetch('/api/data')` with `this.client.getFullData()`. Implemented `DashboardApiService.stop()`. Bound dynamic `protocolVersion` prop in `Header.tsx`. Added `onDestroy` in `App.tsx`. Reviewer verdict: PASS.
- **Step 4 (DOMPurify & CSP)**: Installed `dompurify` and `@types/dompurify`. Wrapped markdown rendering with `DOMPurify.sanitize()` in `EntityDrawer.tsx` and `KBExplorerView.tsx`. Declared `Window.mermaid` global interface. Configured CSP meta tag and Mermaid `securityLevel: 'strict'`. Removed duplicate `marked` import. Reviewer verdict: PASS.
- **Step 5 (Testing & Strict Linter)**: Configured `"enumStyle": "StringLiteral"` in `nswag.json` to generate clean string literal union types. Enabled `noUnusedLocals: true` and `noUnusedParameters: true` in `tsconfig.json`. Removed unused `React` and symbol imports across all 10 component files. Installed `vitest` and `jsdom`. Created `client.test.ts` unit test suite (5 tests). Resolved Node environment to v22.15.0. Reviewer verdict: PASS.

## Verification Walkthrough & Gate Manifest
- **Automated Tests**:
  - `pnpm --filter @along/dashboard-ui run test`: 5 passed (5 tests) in 787ms.
  - `pnpm --filter @along/dashboard-ui run typecheck`: 0 errors with strict unused locals/params.
  - `pnpm --filter @along/dashboard-ui run build`: 1220 modules transformed, build completed in 2.47s.
  - `python .along/scripts/test.py`: 520 passed cleanly across entire repository suite.

```text
Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [vitest: 5/5; typecheck: 0 errors; build: 0 errors; test.py: 520/520]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-1, REQ-2, REQ-3, REQ-4, REQ-5, REQ-6]
- Blast Radius: EXECUTED (PASS)
- Documentation Parity: EXECUTED (PASS)
- Clean Typography: EXECUTED (PASS)
```
