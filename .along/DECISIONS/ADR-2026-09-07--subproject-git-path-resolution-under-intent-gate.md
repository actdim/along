---
protocol: along
slug: subproject-git-path-resolution-under-intent-gate
title: "Relative Path Prefixing for Subproject Git Revisions under Intent Gate"
date: 2026-09-07
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-09-07--subproject-git-path-resolution-under-intent-gate - Relative Path Prefixing for Subproject Git Revisions under Intent Gate

- Date: 2026-09-07
- Status: accepted
- Context:
  1. In Git revision syntax, `HEAD:<path>` without a `./` or `../` prefix resolves relative to the top-level repository working tree root regardless of process `cwd`.
  2. In monorepos with nested subprojects sharing identical document paths (such as `docs/topic--architecture.md`), `along_kb_sync.py` executing with `cwd=subproject` evaluated `git show HEAD:docs/topic--architecture.md`.
  3. Git returned the top-level root file instead of the subproject file, triggering false-positive content reduction (70-90% line loss) and aborting compilation via the Intent Gate with exit code 2.
- Decision:
  1. **Enforce Relative Path Prefixing**: In `along_kb_sync.py`, query paths passed to `git show HEAD:...` are prefixed with `./` (`git_rel = rel_to_repo if rel_to_repo.startswith("./") else f"./{rel_to_repo}"`).
  2. **CWD-Aware Git Resolution**: The `./` prefix forces Git to resolve revision paths relative to the subproject working directory `cwd` (`repo_root`), preventing cross-directory contamination in monorepos.
  3. **Hermetic Test Coverage**: Added `test_23b_subproject_content_reduction_intent_gate` verifying zero false positives during cascading and direct sync, while maintaining genuine content reduction enforcement.
- Consequences:
  - Eliminates false-positive Intent Gate aborts across monorepo subprojects.
  - Preserves Intent Gate protection against real unintended content deletions in both root and nested subprojects.
