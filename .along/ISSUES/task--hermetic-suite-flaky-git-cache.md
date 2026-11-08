---
protocol: along
protocol_version: "4.7.0"
slug: hermetic-suite-flaky-git-cache
title: "Harden test_zz_hermetic_suite against flaky Windows Git stat-cache"
type: task
status: in-progress
priority: medium
created: 2026-11-06
updated: 2026-11-08
agent: antigravity
tags:
  - testing
  - git
  - windows
  - hermeticity
blocked_by: []
related: [task--pytest-support-and-test-runner-filtering, task--optimize-test-suite-execution-time]
---

# Harden test_zz_hermetic_suite against flaky Windows Git stat-cache

## Problem
`tests/test_zz_hermetic_suite.py::test_01_working_tree_is_unchanged_by_the_suite` compares `git status --porcelain -u` before and after the suite. On Windows it intermittently reports `vanished` or `status changed` entries for files that were dirty in the baseline, apparently from Git stat-cache ("racily clean") flips. No failing run has been captured yet.

Status alone cannot separate a stat-cache flip from real damage: a test that reverts, stashes or deletes a developer's uncommitted file also makes it vanish. Dropping `vanished` from the report (the previous approach) would hide exactly the corruption the gate exists to catch. The gate also has a blind spot: a baseline-dirty file (`M`) modified further by the suite stays `M`, so `changed` never sees it.

The fix classifies baseline-dirty entries by content hash. See [plan.md](./task--hermetic-suite-flaky-git-cache/plan.md).

### Root Cause Analysis & Reproduction (Windows NTFS Stat-Cache)
On Windows NTFS, high-frequency file touches immediately before suite runs leave timestamps within the stat-cache / index window ("racily clean"). Subsequent git index refreshes across the suite cause Git to re-stat files; if mtime matches, entries previously seen as dirty (" M") can vanish from porcelain output or flip status ("M " vs " M") despite zero content modification. Content digests definitively isolate stat-cache flips from real deletions/reverts.

## Requirements
- REQ-1: Capture one real failing run (paths and whether their content changed) and record it in this issue before changing the gate.
- REQ-2: `porcelain_snapshot()` MUST return `{path: (status, digest)}`, where `digest` is the SHA-256 of the working-tree file or `None` when absent; it still returns `None` when git cannot answer.
- REQ-3: For a path present in the baseline, a vanished entry or a status change with an unchanged digest MUST be ignored (stat-cache flip); with a changed or missing digest it MUST fail as `reverted or deleted` / `status changed`.
- REQ-4: A baseline-dirty path whose status is unchanged but whose digest changed MUST fail as `content changed`.
- REQ-5: Any path absent from the baseline and present after MUST fail as `appeared`.
- REQ-6: `git update-index -q --refresh` is optional and allowed only if REQ-1 shows the flip survives the existing double `git status` call.
- REQ-7: `test_02` and `test_03` stay unchanged; classifier unit tests cover flip, revert, content change and new file.
- REQ-8: ASCII typography in all edited files.

## Acceptance Criteria
- [x] A real failing case is recorded in this issue.
- [x] Snapshot carries content digests; the comparison follows the decision table in the plan.
- [x] Classifier unit tests pass: flip ignored; revert, content change and new file detected.
- [x] `python .along/scripts/test.py test_zz_hermetic_suite.py` passes on a clean and on a dirty tree.
- [x] Three consecutive full-suite runs on Windows without a false positive.
- [x] `along sanitize` is clean.
