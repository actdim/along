---
protocol: along
slug: untracked-dashboard-artifacts-and-projection-policy
title: "Untracked Dashboard Artifacts and Derived Projection Boundary"
date: 2026-09-09
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-09-09--untracked-dashboard-artifacts-and-projection-policy - Untracked Dashboard Artifacts and Derived Projection Boundary

- Date: 2026-09-09
- Status: accepted
- Context:
  1. `.along/dashboard.html` (205 KB static HTML bundle) was tracked in Git and churned across 18 of 109 commits as a side-effect of running tests and commits (`[debt--generated-dashboard-artifact-committed]`).
  2. `.along/DASHBOARD.md` (3 KB) was listed as a derived projection in `AGENTS.md`, but had no generator implementation (the `--markdown` flag never existed), was unmaintained since August 27, and caused confusion regarding active projections.
  3. Proposing `merge=ours` in `.gitattributes` for projections introduces a breaking failure mode because standard Git lacks a built-in `ours` driver, requiring explicit user gitconfig setup.
- Decision:
  1. **Untracked Generated Artifacts**:
     - `.along/dashboard.html` and `.along/DASHBOARD.md` are deleted from Git tracking and added to `.gitignore`.
     - Generated dashboards and reports are created on demand via `--export` and must never be committed to Git.
  2. **Clear Projection Taxonomy**:
     - **Tracked Derived Projections**: Strictly `.along/ISSUES.md` and `docs/INDEX.md`. These provide human-readable overview and documentation entry points on Git hosts.
     - **Untracked Export Artifacts**: `.along/dashboard.html`, `.along/DASHBOARD.md`. Kept strictly out of Git.
  3. **Zero-Manual-Merge Rule vs .gitattributes**:
     - Reject `merge=ours` in `.gitattributes` due to standard Git driver absence across developer machines and CI.
     - The Zero-Manual-Merge Rule remains a protocol recompile convention: upon Git conflict in tracked projections, accept either branch (`git checkout --ours` or `git checkout --theirs`) and recompile from source files via `/along-issue-sync` or `/along-kb-sync`.
  4. **Automated Guard Gate**:
     - Enforce in `tests/test_zz_hermetic_suite.py` that no forbidden derived projections (`dashboard.html`, `DASHBOARD.md`) are tracked in Git, ensuring repository cleanliness and preventing regressions.
- Consequences:
  - Repository size and history churn from generated HTML blobs are eliminated.
  - Zero risk of unresolvable textual merge conflicts in 205 KB HTML bundles across parallel branches.
  - Clear architectural boundary between tracked human entry points and ephemeral/export artifacts.
