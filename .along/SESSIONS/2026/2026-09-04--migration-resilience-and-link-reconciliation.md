---
protocol: along
date: 2026-09-04
slug: migration-resilience-and-link-reconciliation
agent: antigravity
branch: main
commit: pending
summary: Hardened migration repair with version gates, added advisory scan for shell-escaping artifacts, made issue sync links portable relative, and reconciled subproject LICENSE links.
milestone: v3.0.0-global-quality-revision
issues_advanced: []
issues_completed: [feat--migration-resilience-and-link-reconciliation]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Migration Resilience and Link Reconciliation

## Summary
Hardened migration repair with version gates, added advisory scan for shell-escaping artifacts, made issue sync links portable relative, and reconciled subproject LICENSE links.

## Work Completed
- Added gated YAML front-matter repair (`repair_unquoted_frontmatter_scalars`) in `scripts/migrate_protocol.py` for `detected_version < 2.2.9`, wrapping unquoted scalar fields (`title:`, `summary:`, `description:`) in double quotes and validating with `frontmatter.parse()`.
- Added gated non-mutating advisory scan (`scan_shell_escape_artifacts_in_docs`) in `scripts/migrate_protocol.py` for `v2.0.0 <= detected_version < v2.2.9`, reporting possible shell-escaping artifacts in `docs/*.md` without modifying files.
- Replaced `file://.along/ISSUES/...` pseudo-URIs with portable relative Markdown links (`ISSUES/...` and `ISSUES/done/...`) in `scripts/along_exec.py`.
- Added sibling link adjustment in `scripts/along_exec.py` when an issue moves to `done/`, rewriting `[Text](./feat--foo.md)` or `[Text](feat--foo.md)` to `[Text](../feat--foo.md)` using negative lookbehind to ensure idempotence.
- Added automatic `issue sync` execution in `scripts/along_update.py` after updating each target context.
- Added missing subproject `[License](LICENSE)` link resolution in `scripts/along_kb_sync.py` to point to repository root `LICENSE`.
- Added comprehensive hermetic unit tests in `tests/test_migration.py`, `tests/test_issue_lifecycle.py`, and `tests/test_skills_and_scripts.py`.
- Completed issue `feat--migration-resilience-and-link-reconciliation` and moved it to `done/`.

## Code Review & Blast Radius
- All 243 unit tests pass cleanly in 17.4s (increased from 238).
- Hermetic invariant `TestSuiteLeavesTheRepositoryAlone` passes cleanly.
- Clean typography check passes across all files with zero banned characters.

