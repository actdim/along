---
protocol: along
slug: subproject-scoped-dependencies
date: 2026-09-27
agent: antigravity
summary: "Implemented internal monorepo DAG resolution, subproject-scoped dependency documentation generation, transitive invariant extraction, and optional safe AGENTS.md link synchronization"
milestone: v4.2.0-monorepo-subprojects
issues_advanced: []
issues_completed: [feat--subproject-scoped-dependencies]
decisions: []
risks_logged: []
spikes_conducted: []
branch: main
commit: unknown
---

# Session Log: 2026-09-27 - Subproject-Scoped Dependencies & Internal Monorepo DAG

## 1. Initial Implementation Plan (Baseline)

The objective was to implement `feat--subproject-scoped-dependencies`:
- Extend `along-dep-scan` engine to resolve internal monorepo package relationships (DAG) across npm/pnpm, Python, Cargo, and .NET.
- Distinguish internal workspace packages from external third-party dependencies.
- Generate subproject-scoped `docs/topic--dependencies.md` for Along-initialized subprojects with calculated relative links.
- Render an internal monorepo dependency matrix in the root `docs/topic--dependencies.md`.
- Provide an opt-in `--link` flag to update managed blocks `<!-- BEGIN ALONG-DEPS -->` in subproject `AGENTS.md` without modifying unmanaged content.
- Discover exported invariants (`<!-- EXPORT-INVARIANTS: ... -->`) from dependencies without polluting `.along/CONSTRAINTS.md`.

## 2. Execution & Loop Trace (Fixes & Re-plans)

- **Step 1: Manifest Scanning & DAG Resolution**:
  - Enhanced `scripts/along_dep_scan.py` to index workspace manifests (`package.json`, `pyproject.toml`, `Cargo.toml`, `.csproj`).
  - Added topological dependency resolution mapping consumers to internal source directories.
- **Step 2: Subproject Knowledge Base Generation**:
  - Implemented scoped KB generation targeting individual subproject boundaries when requested via `--subproject` or `--all-subprojects`.
  - Calculated exact relative Markdown links from subproject documentation to internal package AI guidance (`AGENTS.md`, `llms.txt`, `docs/`).
- **Step 3: Root Matrix & Invariant Discovery**:
  - Added formatted Internal Monorepo Dependency Matrix table to root `docs/topic--dependencies.md`.
  - Added invariant extraction parsing declared dependency export blocks into a dedicated guidelines section.
- **Step 4: Non-Intrusive Managed Link Injection**:
  - Implemented `--link` flag updating `AGENTS.md` managed block with clean rollback and preservation of surrounding content.
- **Step 5: Testing & Verification**:
  - Authored comprehensive test cases in `tests/test_scan_deps.py` covering multi-project fixtures, relative link verification, and subproject scoping.

## 3. Verification Walkthrough & Gate Manifest

```text
Gate Execution Manifest:
- Internal DAG Resolution: EXECUTED (PASS) [Internal vs external packages distinguished]
- Subproject Scoping: EXECUTED (PASS) [docs/topic--dependencies.md localized per subproject]
- Invariant Extraction: EXECUTED (PASS) [Exported invariants mapped to guidelines section]
- Managed Link Injection: EXECUTED (PASS) [--link updates AGENTS.md managed block cleanly]
- Unit Test Suite: EXECUTED (PASS) [tests/test_scan_deps.py clean]
```
