---
protocol: along
protocol_version: "2.2.8"
slug: dependencies
title: Dependencies & Submodules AI Documentation and Rules
type: topic
created: 2026-09-01
updated: 2026-09-02
tags: [dependencies, ai-context, submodules, vendor, rules]
---

# Dependencies & Submodules AI Documentation and Rules

> [!NOTE]
> This document maintains a unified registry of internal subprojects, submodules, and external dependencies.
> Consult linked guidelines when developing, refactoring, or integrating components across the repository.

## Internal Subprojects, Modules & Submodules

| Subproject / Module | Path | Ecosystems | AI Documentation & Context |
| :--- | :--- | :--- | :--- |
| **`@along/dashboard-ui`** | `packages/dashboard-ui` | `npm` | - |

## Declared External Dependencies with AI Guidelines

| Package | Scope / Project | Ecosystem | Version | AI Guidelines / Instructions |
| :--- | :--- | :--- | :--- | :--- |
| **`@actdim/dynstruct`** | `packages/dashboard-ui` | `npm` | `1.5.10` | [AGENTS.md](../packages/dashboard-ui/node_modules/@actdim/dynstruct/AGENTS.md) <br> [CLAUDE.md](../packages/dashboard-ui/node_modules/@actdim/dynstruct/CLAUDE.md) <br> [llms.txt](../packages/dashboard-ui/node_modules/@actdim/dynstruct/llms.txt) <br> [docs/](../packages/dashboard-ui/node_modules/@actdim/dynstruct/docs) <br> manifest metadata (`ai`) |
| **`@actdim/msgmesh`** | `packages/dashboard-ui` | `npm` | `1.5.10` | [docs/](../packages/dashboard-ui/node_modules/@actdim/msgmesh/docs) |
| **`@actdim/utico`** | `packages/dashboard-ui` | `npm` | `1.5.10` | [AGENTS.md](../packages/dashboard-ui/node_modules/@actdim/utico/AGENTS.md) <br> [CLAUDE.md](../packages/dashboard-ui/node_modules/@actdim/utico/CLAUDE.md) <br> [llms.txt](../packages/dashboard-ui/node_modules/@actdim/utico/llms.txt) <br> manifest metadata (`ai`) |
| **`cytoscape`** | `packages/dashboard-ui` | `npm` | `3.34.2` | [AGENTS.md](../packages/dashboard-ui/node_modules/cytoscape/AGENTS.md) |

## Usage in Agent Sessions
When working on features involving any of the modules or external libraries above:
1. **Internal Submodules**: Follow conventions in the nearest `AGENTS.md` or subproject `docs/`.
2. **Third-Party Libraries**: Read the linked instruction files directly for framework-specific patterns and best practices.
