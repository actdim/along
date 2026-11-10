---
protocol: along
protocol_version: "4.7.0"
slug: dependencies
title: Dependencies & Submodules AI Documentation and Rules
type: topic
created: 2026-11-10
updated: 2026-11-10
tags: [dependencies, ai-context, submodules, vendor, rules]
---

# Dependencies & Submodules AI Documentation and Rules

> [!NOTE]
> This document maintains a unified registry of internal subprojects, submodules, and external dependencies.
> Consult linked guidelines when developing, refactoring, or integrating components across the repository.

## Internal Subprojects, Modules & Submodules

| Subproject / Module | Path | Ecosystems | AI Documentation & Context |
| :--- | :--- | :--- | :--- |
| **`@along/dashboard-ui`** | `packages/dashboard-ui` | `npm` | [AGENTS.md](../packages/dashboard-ui/AGENTS.md) <br> [llms-full.txt](../packages/dashboard-ui/llms-full.txt) <br> [llms.txt](../packages/dashboard-ui/llms.txt) <br> [docs/](../packages/dashboard-ui/docs) |

## Internal Monorepo Dependency Graph

No internal monorepo package inter-dependencies detected.

## Declared External Dependencies with AI Guidelines

| Package | Scope / Project | Ecosystem | Version | AI Guidelines / Instructions |
| :--- | :--- | :--- | :--- | :--- |
| **`@actdim/dynstruct`** | `packages/dashboard-ui` | `npm` | `1.12.2` | [AGENTS.md](../packages/dashboard-ui/node_modules/.pnpm/@actdim+dynstruct@1.12.2_@a_9cc227333c0ecf4368f7602292dd8c27/node_modules/@actdim/dynstruct/AGENTS.md) <br> [CLAUDE.md](../packages/dashboard-ui/node_modules/.pnpm/@actdim+dynstruct@1.12.2_@a_9cc227333c0ecf4368f7602292dd8c27/node_modules/@actdim/dynstruct/CLAUDE.md) <br> [llms-full.txt](../packages/dashboard-ui/node_modules/.pnpm/@actdim+dynstruct@1.12.2_@a_9cc227333c0ecf4368f7602292dd8c27/node_modules/@actdim/dynstruct/llms-full.txt) <br> [llms.txt](../packages/dashboard-ui/node_modules/.pnpm/@actdim+dynstruct@1.12.2_@a_9cc227333c0ecf4368f7602292dd8c27/node_modules/@actdim/dynstruct/llms.txt) <br> [docs/](../packages/dashboard-ui/node_modules/@actdim/dynstruct/docs) <br> manifest metadata (`ai`) |
| **`@actdim/dynstruct-mui`** | `packages/dashboard-ui` | `npm` | `1.12.2` | [AGENTS.md](../packages/dashboard-ui/node_modules/.pnpm/@actdim+dynstruct-mui@1.12._dbfecc25c230812454a35b7fc03c90af/node_modules/@actdim/dynstruct-mui/AGENTS.md) <br> [CLAUDE.md](../packages/dashboard-ui/node_modules/.pnpm/@actdim+dynstruct-mui@1.12._dbfecc25c230812454a35b7fc03c90af/node_modules/@actdim/dynstruct-mui/CLAUDE.md) <br> [llms-full.txt](../packages/dashboard-ui/node_modules/.pnpm/@actdim+dynstruct-mui@1.12._dbfecc25c230812454a35b7fc03c90af/node_modules/@actdim/dynstruct-mui/llms-full.txt) <br> [llms.txt](../packages/dashboard-ui/node_modules/.pnpm/@actdim+dynstruct-mui@1.12._dbfecc25c230812454a35b7fc03c90af/node_modules/@actdim/dynstruct-mui/llms.txt) <br> [docs/](../packages/dashboard-ui/node_modules/@actdim/dynstruct-mui/docs) <br> manifest metadata (`ai`) |
| **`@actdim/msgmesh`** | `packages/dashboard-ui` | `npm` | `1.12.2` | [AGENTS.md](../packages/dashboard-ui/node_modules/.pnpm/@actdim+msgmesh@1.12.2_@act_ada671f90b40be71a7baed66a398f37c/node_modules/@actdim/msgmesh/AGENTS.md) <br> [CLAUDE.md](../packages/dashboard-ui/node_modules/.pnpm/@actdim+msgmesh@1.12.2_@act_ada671f90b40be71a7baed66a398f37c/node_modules/@actdim/msgmesh/CLAUDE.md) <br> [llms-full.txt](../packages/dashboard-ui/node_modules/.pnpm/@actdim+msgmesh@1.12.2_@act_ada671f90b40be71a7baed66a398f37c/node_modules/@actdim/msgmesh/llms-full.txt) <br> [llms.txt](../packages/dashboard-ui/node_modules/.pnpm/@actdim+msgmesh@1.12.2_@act_ada671f90b40be71a7baed66a398f37c/node_modules/@actdim/msgmesh/llms.txt) <br> [docs/](../packages/dashboard-ui/node_modules/@actdim/msgmesh/docs) <br> manifest metadata (`ai`) |
| **`@actdim/ui-core`** | `packages/dashboard-ui` | `npm` | `1.12.2` | [AGENTS.md](../packages/dashboard-ui/node_modules/.pnpm/@actdim+ui-core@1.12.2_cf596066e6c8cf207f71129b8d105d17/node_modules/@actdim/ui-core/AGENTS.md) <br> [CLAUDE.md](../packages/dashboard-ui/node_modules/.pnpm/@actdim+ui-core@1.12.2_cf596066e6c8cf207f71129b8d105d17/node_modules/@actdim/ui-core/CLAUDE.md) <br> [llms-full.txt](../packages/dashboard-ui/node_modules/.pnpm/@actdim+ui-core@1.12.2_cf596066e6c8cf207f71129b8d105d17/node_modules/@actdim/ui-core/llms-full.txt) <br> [llms.txt](../packages/dashboard-ui/node_modules/.pnpm/@actdim+ui-core@1.12.2_cf596066e6c8cf207f71129b8d105d17/node_modules/@actdim/ui-core/llms.txt) <br> [docs/](../packages/dashboard-ui/node_modules/@actdim/ui-core/docs) <br> manifest metadata (`ai`) |
| **`@actdim/utico`** | `packages/dashboard-ui` | `npm` | `1.12.2` | [AGENTS.md](../packages/dashboard-ui/node_modules/.pnpm/@actdim+utico@1.12.2_dexie@4.4.5_luxon@3.7.2_uuid@13.0.2/node_modules/@actdim/utico/AGENTS.md) <br> [CLAUDE.md](../packages/dashboard-ui/node_modules/.pnpm/@actdim+utico@1.12.2_dexie@4.4.5_luxon@3.7.2_uuid@13.0.2/node_modules/@actdim/utico/CLAUDE.md) <br> [llms-full.txt](../packages/dashboard-ui/node_modules/.pnpm/@actdim+utico@1.12.2_dexie@4.4.5_luxon@3.7.2_uuid@13.0.2/node_modules/@actdim/utico/llms-full.txt) <br> [llms.txt](../packages/dashboard-ui/node_modules/.pnpm/@actdim+utico@1.12.2_dexie@4.4.5_luxon@3.7.2_uuid@13.0.2/node_modules/@actdim/utico/llms.txt) <br> [docs/](../packages/dashboard-ui/node_modules/@actdim/utico/docs) <br> manifest metadata (`ai`) |
| **`@mui/material`** | `packages/dashboard-ui` | `npm` | `9.5.0` | [docs/](../packages/dashboard-ui/node_modules/@mui/material/docs) |
| **`cytoscape`** | `packages/dashboard-ui` | `npm` | `3.34.2` | [AGENTS.md](../packages/dashboard-ui/node_modules/.pnpm/cytoscape@3.34.2/node_modules/cytoscape/AGENTS.md) |
| **`react-router`** | `packages/dashboard-ui` | `npm` | `7.18.2` | [docs/](../packages/dashboard-ui/node_modules/react-router/docs) |

## Transitive Dependency Guidelines & Invariants

No exported invariants detected across repository dependencies.

## Custom Project Dependency Hooks (`.along/scripts/dep_scan.py`)

While Along natively auto-discovers dependencies across Node.js (`package.json`), Python (`pyproject.toml`, `requirements*.txt`), .NET NuGet (`*.csproj`), Rust (`Cargo.toml`), and Go (`go.mod`), repositories using other ecosystems or internal package managers can supply a custom discovery hook:

- **Hook Path**: `.along/scripts/dep_scan.py` (or `scan_deps.py`).
- **Invocation**: `/along-dep-scan` or `along dep-scan` executes the script passing `--json` with working directory set to the project root.
- **Output Schema**: The script must write a JSON list to stdout:
  ```json
  [
    {
      "package": "custom-package",
      "ecosystem": "hex",
      "version": "1.0.0",
      "files": [
        {
          "filename": "AGENTS.md",
          "path": "deps/custom-package/AGENTS.md"
        }
      ]
    }
  ]
  ```
- **Monorepo Localization**: In multi-package repositories or submodules, subproject-specific hooks placed in `packages/<subproject>/.along/scripts/dep_scan.py` are executed automatically when scanning that subproject.

## Usage in Agent Sessions
When working on features involving any of the modules or external libraries above:
1. **Internal Submodules**: Follow conventions in the nearest `AGENTS.md` or subproject `docs/`.
2. **Third-Party Libraries**: Read the linked instruction files directly for framework-specific patterns and best practices.
