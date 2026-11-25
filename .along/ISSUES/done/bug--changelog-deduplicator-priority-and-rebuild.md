---
protocol: along
protocol_version: "4.9.1"
slug: changelog-deduplicator-priority-and-rebuild
type: bug
status: done
completed: 2026-11-25
priority: medium
created: 2026-11-25
updated: 2026-11-25
agent: antigravity
tags: [changelog, version-bump, docs]
blocked_by: []
related: [docs--changelog-deduplication]
plan_status: approved
---

# Fix changelog deduplicator type priority and rebuild CHANGELOG.md

## Problem
`deduplicate_log_entries()` in `scripts/along_version_bump.py` currently compares duplicate commit subjects sharing the same `(refs #<slug>)` solely by whether the prefix has a `(scope)` and then by string length. Consequently, secondary commits such as `docs(adr): ...` or `chore(sync): ...` replace primary implementation commits (`feat: ...` or `fix: ...`) whenever the primary commit is unscoped. In addition, `CHANGELOG.md` was only partially cleaned in `docs--changelog-deduplication` and still contains duplicate `(refs #<slug>)` entries across `v4.9.1`, `v4.9.0`, `v4.8.1`, `v4.8.0`, `v4.7.0`, `v4.6.1`, `v4.6.0`, `v4.5.x`, and earlier sections.

## Requirements
- REQ-1: `deduplicate_log_entries()` in `scripts/along_version_bump.py` MUST retain double-prefix normalization (`fix: fix(scope): ...` -> `fix(scope): ...`) across conventional commit types.
- REQ-2: When multiple entries share the same `(refs #<slug>)`, `deduplicate_log_entries()` MUST rank winners by: (1) commit type tier (`feat`, `fix`, `perf`, `refactor`, `debt` > `docs` > `test`, `chore`, `style`, `ci`, `build` > non-conventional/other types), (2) scoped `type(scope):` over unscoped `type:` within the same tier, and (3) longer subject string within the same tier and scope presence.
- REQ-3: `tests/test_version_bump.py` MUST preserve existing deduplication checks, add regression tests verifying commit type tier priority (`feat:`/`fix:` beating `docs(adr):` and `chore(scope):`), and verify that `CHANGELOG.md` sections from `v4.6.0` through current have zero duplicate `(refs #<slug>)` entries.
- REQ-4: `CHANGELOG.md` MUST be rebuilt across all tagged sections from `v4.4.5` through `v4.9.2` from `git log <prev_tag>..<tag>` passed through `deduplicate_log_entries()`, preserving exact release dates (`## vX.Y.Z - YYYY-MM-DD`), deduplicating older historical sections via `deduplicate_log_entries()`, remaining pure ASCII (`along sanitize`), and containing zero duplicate primary `(refs #<slug>)` entries in any section.

## Acceptance Criteria
- [x] `deduplicate_log_entries()` in `scripts/along_version_bump.py` prioritizes commit type tier before scope presence and subject length while preserving double-prefix normalization.
- [x] `CHANGELOG.md` sections `v4.4.5`..`v4.9.2` are regenerated from git tag ranges through `deduplicate_log_entries()` with exact tag dates, older sections are deduplicated, and all sections have zero duplicate `(refs #<slug>)` entries.
- [x] `CHANGELOG.md` passes `along sanitize` with pure ASCII content.
- [x] `tests/test_version_bump.py` includes type-tier priority tests and a `CHANGELOG.md` duplicate-free check (`v4.6.0`..current), and `TestDeduplicateLogEntries.test_deduplicates_by_issue_reference_and_prefers_scope` passes.
- [x] Full test suite, `along sanitize`, `along hook verify --strict`, and `along kb-sync --check --strict` pass.
