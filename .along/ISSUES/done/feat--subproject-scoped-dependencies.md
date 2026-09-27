---
protocol: along
protocol_version: "4.1.0"
slug: subproject-scoped-dependencies
type: feat
status: done
completed: 2026-09-27
priority: high
created: 2026-09-27
updated: 2026-09-27
agent: antigravity
tags: [dep-scan, monorepo, subprojects, dependencies, kb, internal-dag]
milestone: v4.2.0-monorepo-subprojects
blocked_by: []
related: []
---

# Subproject-Scoped Dependencies & Internal Monorepo DAG

## Goal
Extend `along-dep-scan` engine to resolve internal monorepo package relationships (DAG), generate subproject-scoped dependency documentation, and provide clean relative links without polluting root context or violating Along architectural boundaries.

## Problem Statement
In monorepo environments, subprojects and applications (e.g. `apps/webapp`) consume internal packages (`packages/*`) and external libraries. Currently, `along_dep_scan.py` only generates a single flat `docs/topic--dependencies.md` in the root repository. Agents working within a specific subproject boundary lack localized visibility into which internal modules their subproject depends on, cannot easily navigate to dependency AI guidelines (`AGENTS.md`, `llms.txt`, `docs/`), and risk context bloat if links are naively dumped into `AGENTS.md` or constraints.

## Technical Specifications

### 1. Internal Workspace DAG Resolution
- Map discovered internal project/package names from their manifests (`package.json`, `pyproject.toml`, `Cargo.toml`, `.csproj`).
- Correlate declared dependencies in each project against discovered internal projects to distinguish `internal_workspace` dependencies from third-party external dependencies.
- Track precise relative file paths between dependent subprojects and dependency sources on disk.

### 2. Subproject-Scoped Knowledge Base Generation
- When scanning an Along-initialized subproject (or when `--subprojects` / `--all-subprojects` / `--root <subproject>` is specified):
  - Generate localized `docs/topic--dependencies.md` containing only dependencies consumed by that subproject.
  - Calculate accurate relative links from the subproject's `docs/` to dependency AI documentation (`AGENTS.md`, `llms.txt`, `docs/`).
  - Do not create unmanaged `docs/` directories in uninitialized subprojects unless explicitly requested.

### 3. Root KB Dependency Matrix
- In root `docs/topic--dependencies.md`, include:
  - Internal Monorepo Dependency Matrix: which subproject depends on which internal package.
  - Declared External Dependencies with AI guidelines (scoped by project).

### 4. Optional Safe Linking Flag (`--link`)
- Provide `--link` flag to inject/update a managed block `<!-- BEGIN ALONG-DEPS --> ... <!-- END ALONG-DEPS -->` into `AGENTS.md` (or `llms.txt`) strictly for direct internal workspace dependencies.
- Keep default behavior non-intrusive (no modification of `AGENTS.md` by default to preserve token budget).

### 5. Dependency Guidelines & Invariants Discovery
- Discover exported invariants/guidelines from dependencies (e.g. `<!-- EXPORT-INVARIANTS: ... -->` or guideline sections).
- Present them in `docs/topic--dependencies.md` under a dedicated guidelines section with links to original ADRs or sources.
- Never write directly to `.along/CONSTRAINTS.md`, respecting the ADR projection model and context limits.

## Acceptance Criteria
- [ ] Internal workspace dependencies are distinguished from external dependencies.
- [ ] Subproject-scoped dependency scans generate clean, localized `topic--dependencies.md` with valid relative links.
- [ ] Root `docs/topic--dependencies.md` reflects internal dependency graph.
- [ ] `--link` flag updates managed block in `AGENTS.md` safely without touching unmanaged sections.
- [ ] Unit tests in `tests/test_scan_deps.py` verify internal DAG resolution, subproject scoping, and relative link computation.
