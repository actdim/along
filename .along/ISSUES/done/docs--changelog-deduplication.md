---
protocol: along
protocol_version: "4.9.1"
slug: changelog-deduplication
type: docs
status: done
completed: 2026-11-24
priority: medium
created: 2026-11-24
updated: 2026-11-24
agent: antigravity
tags: [docs, changelog, release]
blocked_by: []
related: []
plan_status: approved
---

# Deduplicate commit entries in CHANGELOG.md and release engine

## Problem
In `CHANGELOG.md`, releases v4.9.1, v4.9.0, and v4.8.1 contain repeated duplicate lines for the same issues. This happens when both scoped commits (e.g. `feat(scope): ...`) and umbrella commits (e.g. `feat: ...`) reference the same issue key `(refs #slug)`. In some cases, identical commit subjects appear twice or prefixed with double prefixes like `fix: fix(opencode):`. Furthermore, the release engine `release_log_entries` in `scripts/along_version_bump.py` does not deduplicate log subjects by issue reference, guaranteeing duplicates in future releases.

## Requirements
- REQ-1: `CHANGELOG.md` MUST be cleaned of duplicate and redundant entries across recent release sections (v4.9.1, v4.9.0, v4.8.1).
- REQ-2: Malformed subjects with duplicate prefixes (e.g. `fix: fix(...)`) MUST be normalized in `CHANGELOG.md`.
- REQ-3: `release_log_entries` in `scripts/along_version_bump.py` MUST deduplicate commit subjects sharing the same `(refs #slug)`, preferring the more specific scoped commit subject when both umbrella and scoped subjects exist.
- REQ-4: All automated unit tests and link integrity gates MUST pass.

## Acceptance Criteria
- [x] `CHANGELOG.md` v4.9.1, v4.9.0, and v4.8.1 sections contain no duplicate entries sharing identical issue references.
- [x] Malformed prefix repetitions in `CHANGELOG.md` are resolved.
- [x] `release_log_entries` in `scripts/along_version_bump.py` deduplicates entries sharing the same issue reference.
- [x] Unit tests in `tests/test_version_bump.py` verify deduplication behavior in `release_log_entries`.
- [x] `python .along/scripts/test.py` passes.
