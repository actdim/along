---
protocol: along
protocol_version: "4.4.12"
slug: dashboard-docs-kb-alignment
type: task
status: done
completed: 2026-10-14
priority: medium
created: 2026-10-14
updated: 2026-10-14
agent: antigravity
tags: [docs, dashboard, kb]
blocked_by: []
related: []
---

# Align dashboard docs and AGENTS references with Knowledge Base

Align root and subproject documentation with Knowledge Base topic model:
- Created `packages/dashboard-ui/docs/topic--frontend-conventions.md` containing complete Dynstruct, MsgMesh, overlays, reactivity, and styling conventions.
- Slimmed `packages/dashboard-ui/README.md` to landing page / overview.
- Updated root `AGENTS.md` and subproject `AGENTS.md` to reference `docs/topic--frontend-conventions.md`.
- Synchronized Knowledge Base across root and subproject via `along kb sync`.

## Acceptance Criteria
- [x] Root AGENTS.md references packages/dashboard-ui/docs/topic--frontend-conventions.md
- [x] Subproject AGENTS.md references docs/topic--frontend-conventions.md
- [x] All relative Markdown links verified by along kb sync
- [x] Typography clean per along sanitize
