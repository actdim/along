---
protocol: along
date: 2026-09-07
slug: kb-sync-subproject-intent-gate
agent: antigravity
branch: main
commit: pending
summary: Fix Intent Gate false positive during subproject cascading sync by prefixing git show path with ./
milestone: v3.0.0-global-quality-revision
issues_advanced: []
issues_completed: [kb-sync-subproject-intent-gate]
decisions: [ADR-2026-09-07--subproject-git-path-resolution-under-intent-gate]
risks_logged: []
spikes_conducted: []
---

# Session: KB sync subproject intent gate false positive fix

## Summary
Fixed an issue where `along_kb_sync.py` falsely triggered the content reduction Intent Gate during cascading sync on monorepo subprojects by prefixing the Git query path with `./`, forcing Git to resolve paths relative to the subproject working directory instead of the repository root.

## Work Completed
- Fixed path resolution in `scripts/along_kb_sync.py` around line 940: `git_rel = rel_to_repo if rel_to_repo.startswith("./") else f"./{rel_to_repo}"` and passed `HEAD:{git_rel}` to `git show`. This ensures Git resolves paths relative to `cwd=repo_root` (the subproject directory) rather than the top-level repository work tree.
- Updated `docs/topic--llm-wiki-architecture.md` to document the subproject relative path resolution under the Intent Gate specification, and updated its `sources` SHA-256 hash for `scripts/along_kb_sync.py`.
- Added hermetic unit test `test_23b_subproject_content_reduction_intent_gate` in `tests/test_skills_and_scripts.py` verifying that cascading and direct sync on subprojects with identically named docs does not trigger false positive Intent Gate aborts, while still catching genuine content reduction in subproject docs.
- Reconciled issue `.along/ISSUES/done/bug--kb-sync-subproject-intent-gate.md` and updated `.along/ISSUES.md`.

## Code Review & Blast Radius
- All 297 unit tests passed with zero failures via `python .along/scripts/test.py`.
- Typography check clean across 287 files.
- Zero drift on `scripts/along_kb_sync.py` in `docs/topic--llm-wiki-architecture.md`.
