---
protocol: along
date: 2026-08-28
slug: dynstruct-msgmesh-adapters-nswag-v209
agent: antigravity
branch: master
summary: Upgraded ActDim packages to v1.5.9, integrated NSwag client generation with clean camelCase operationIds, dynamic ToMsgStruct adapters, and formalized Decision #011.
issues_advanced: []
issues_completed: []
decisions: ["#011"]
risks_logged: []
spikes_conducted: []
commit: unknown
milestone: v2.0.0-along-transition
---

# Session Log: Dynstruct + MsgMesh Adapters + NSwag Integration (v2.0.9)

## Summary of Changes
1. **ActDim Package Upgrades to v1.5.9**:
   - Upgraded `@actdim/dynstruct`, `@actdim/dynstruct-mui`, `@actdim/msgmesh`, and `@actdim/utico` to `^1.5.9` in `packages/dashboard-ui/package.json`.
   - Resolved peer dependencies and built cleanly.

2. **Automated NSwag Client Generation**:
   - Configured FastAPI `custom_generate_unique_id` to generate clean `camelCase` operation IDs (`getFullData`, `searchKb`, `getMetrics`, `listIssues`, etc.).
   - Configured `packages/dashboard-ui/nswag.json` and added `"generate:api": "npx nswag run nswag.json"`.
   - Auto-generated [src/api/client.ts](../../../packages/dashboard-ui/src/api/client.ts) implementing `DashboardApiClient`.

3. **Dynamic Adapter Wiring (`@actdim/msgmesh/adapters`)**:
   - Replaced manual channel structs with dynamic `ToMsgChannelPrefix` and `ToMsgStruct` derived at compile-time directly from `DashboardApiClient`.
   - Wired the service using `getMsgChannelSelector` and `registerAdapters` in `DashboardApiService`.
   - Connected UI components via `c.msgBus` proxy and scoped `msgScope`.

4. **Protocol & Architectural Records**:
   - Recorded **Decision #011** in `.along/DECISIONS.md`.
   - Expanded `.along/KB/04-frontend-frameworks.md` with complete architectural documentation.
   - Updated `AGENTS.md` project specifics.

5. **Release Bumping**:
   - Bumped Along release to **v2.0.9**.

## Verification & Code Review
- `pnpm run build` compiled with 0 errors in 2.15s.
- FastAPI backend endpoints verified with TestClient.
- Typography sanitized (clean ASCII).

