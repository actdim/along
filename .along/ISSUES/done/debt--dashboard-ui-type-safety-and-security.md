---
protocol: along
protocol_version: "3.9.4"
slug: dashboard-ui-type-safety-and-security
type: debt
status: done
priority: high
created: 2026-09-16
updated: 2026-09-22
completed: 2026-09-22
agent: antigravity
tags: [frontend, nswag, typescript, security, xss, mobx, dynstruct]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: []
related: []
---

# Dashboard UI NSwag Generation, Type Safety, and Content Security Hardening

## Problem
The frontend dashboard (`packages/dashboard-ui`) deviates from architectural contracts specified in `docs/topic--frontend-frameworks.md`:
1. Type safety erosion and NSwag misconfiguration:
   - `packages/dashboard-ui/nswag.json:61` specifies `"inlineNamedAny": true`, generating 77 DTO interfaces with `[key: string]: any` and yielding ~142 `any` occurrences in `src/api/client.ts`.
   - Dual sources of truth: handwritten `src/types.ts` duplicates generated client models, glued together with unsafe casting (`as unknown as FullDashboardData` in `App.tsx:99`).
2. Protocol transport violations:
   - Manual `fetch('/api/data')` and untyped `new EventSource('/api/events')` in `src/services/apiService.ts:44,56` bypass the generated NSwag client methods (`getFullData`, SSE streaming).
3. Security and XSS vulnerabilities:
   - `src/components/EntityDrawer.tsx:107`: Markdown output rendered via `dangerouslySetInnerHTML` directly from `marked.parse` without sanitization.
   - `index.html:8-12`: External Mermaid library loaded from CDN with `securityLevel: 'loose'` without Content Security Policy (CSP).
4. Lifecycle leaks and stale constants:
   - `src/components/Header.tsx:54`: Hardcoded stale badge `v2.0.9` (while protocol is v3.6.0).
   - `src/App.tsx:199`: Global `window.addEventListener('keydown', ...)` in `onReady` lacks corresponding unmount cleanup.
   - Zero automated tests and missing linter rules (`noUnusedLocals: false`).

## Requirements
- Reconfigure `nswag.json` to disable `inlineNamedAny` and regenerate strongly-typed client DTOs.
- Eliminate handwritten duplicate models in `src/types.ts` in favor of generated client types.
- Wire `apiService.ts` to generated NSwag client methods instead of manual `fetch` and raw `EventSource`.
- Add DOMPurify sanitization before rendering markdown in `EntityDrawer.tsx`.
- Secure or bundle Mermaid with strict security settings and configure CSP.
- Replace hardcoded `v2.0.9` in `Header.tsx` with dynamic version from backend metrics payload.
- Add event listener cleanup on component destruction.
- Establish frontend test runner and typecheck script.

## Acceptance Criteria
- [x] Zero `any` types generated in `src/api/client.ts`.
- [x] No `as unknown as` assertions in `App.tsx` or service layer.
- [x] Markdown HTML passed through sanitization before DOM injection.
- [x] Header displays dynamic repository protocol version.
- [x] Keydown event listener safely removed on teardown.
- [x] Frontend build succeeds cleanly: `npm run build`.
