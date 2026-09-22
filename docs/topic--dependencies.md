---
protocol: along
slug: dependencies
title: Dependencies & Submodules AI Documentation and Rules
type: topic
created: 2026-09-02
updated: 2026-09-19
tags: [dependencies, ai-context, submodules, vendor, rules]
sources:
  - path: pyproject.toml
    hash: "6f7a72d4e5eac4b4bb59b8d822e53e7b7dc61cca7abe98b387ff5a97a1505a95"
  - path: package.json
    hash: "4c732b953341c1070bacca0eea4a74c8cac5a640c2c4c114462ef8ce3a9180c7"
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
| **`@actdim/dynstruct`** | `packages/dashboard-ui` | `npm` | `1.5.13` | [AGENTS.md](../packages/dashboard-ui/node_modules/@actdim/dynstruct/AGENTS.md) <br> [CLAUDE.md](../packages/dashboard-ui/node_modules/@actdim/dynstruct/CLAUDE.md) <br> [docs/](../packages/dashboard-ui/node_modules/@actdim/dynstruct/docs) <br> manifest metadata (`ai`) |
| **`@actdim/dynstruct-mui`** | `packages/dashboard-ui` | `npm` | `1.5.13` | [docs/](../packages/dashboard-ui/node_modules/@actdim/dynstruct-mui/docs) |
| **`@actdim/msgmesh`** | `packages/dashboard-ui` | `npm` | `1.5.13` | [docs/](../packages/dashboard-ui/node_modules/@actdim/msgmesh/docs) |
| **`@actdim/utico`** | `packages/dashboard-ui` | `npm` | `1.5.13` | [AGENTS.md](../packages/dashboard-ui/node_modules/@actdim/utico/AGENTS.md) <br> [CLAUDE.md](../packages/dashboard-ui/node_modules/@actdim/utico/CLAUDE.md) <br> [docs/](../packages/dashboard-ui/node_modules/@actdim/utico/docs) <br> manifest metadata (`ai`) |
| **`cytoscape`** | `packages/dashboard-ui` | `npm` | `3.34.2` | [AGENTS.md](../packages/dashboard-ui/node_modules/cytoscape/AGENTS.md) |

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
