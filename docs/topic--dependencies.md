---
protocol: along
protocol_version: "2.2.27"
slug: dependencies
title: Dependencies & Submodules AI Documentation and Rules
type: topic
created: 2026-09-02
updated: 2026-09-09
tags: [dependencies, ai-context, submodules, vendor, rules]
sources:
  - path: pyproject.toml
    hash: "2ca12e69d7ceafb95b69040a3ffb58aba74e7757c6fba6d66406b23e1f066526"
  - path: package.json
    hash: "febb2e71352d6091afce25991d7e2a4d09e92564938317a307ae5bec7c2a4c50"
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
