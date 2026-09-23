---
protocol: along
protocol_version: "4.0.2"
slug: relocate-dashboard-ui-frontend-architecture-to-package
type: debt
status: done
priority: high
created: 2026-09-23
updated: 2026-09-23
completed: 2026-09-23
agent: antigravity
tags: [debt, docs, dashboard-ui, architecture, subproject-boundary]
milestone:
blocked_by: []
related: []
parent:
superseded_by:
duplicate_of:
---

# Relocate Dashboard UI Frontend Architecture to Package Boundary

## Goal

Extract internal Dynstruct, MsgMesh, and NSwag architecture rules from the global Knowledge Base (`docs/topic--frontend-frameworks.md`) into `packages/dashboard-ui/` (`README.md` and `AGENTS.md`). Ensure the global protocol documentation and `mkdocs.yml` do not misrepresent internal dashboard constraints as universal frontend requirements for consumer repositories.
