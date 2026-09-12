---
protocol: along
slug: unified-along-wrap-commit-and-lifecycle-runners
title: "Unified /along-wrap, Smart /along-commit, and Lifecycle Execution Suite (/along-build, /along-test, /along-dev)"
date: 2026-08-27
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-08-27--unified-along-wrap-commit-and-lifecycle-runners - Unified /along-wrap, Smart /along-commit, and Lifecycle Execution Suite (/along-build, /along-test, /along-dev)

- Date: 2026-08-27
- Status: accepted
- Context: Separate `along-wrap-session` and `along-wrap-stage` skills created redundant duplication and prompt bloat. Developers also needed safe pre-commit ASCII checks, automated Conventional Commit formatting, and project lifecycle runners (`build`, `test`, `dev`).
- Decision:
  1. Consolidate `along-wrap-session` and `along-wrap-stage` into a single canonical skill: **`/along-wrap`**.
  2. Implement **`/along-commit`** (`scripts/along_commit.py`) to enforce pre-commit typography checks, auto-link active `.along/` issues, and format Conventional Commits.
  3. Deploy non-destructive lifecycle suite (**`/along-build`**, **`/along-test`**, **`/along-dev`** via `scripts/along_exec.py`), utilizing `.along/scripts/` with `# Status: verified` vs `# Status: unconfigured` markers.
  4. Refine `along-bump-version` to update files on disk by default, committing only when `--commit` is explicitly passed.
- Consequences: Reduced skill token footprint, unified wrap mental model, and robust development lifecycle automation.
