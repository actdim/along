---
protocol: along
protocol_version: "4.6.0"
slug: lint-worktree-and-doctor-subprojects
type: feat
status: done
completed: 2026-11-06
priority: medium
created: 2026-11-05
updated: 2026-11-06
agent: antigravity
tags: [lint, doctor, migration, subprojects]
blocked_by: []
related: []
plan_status: needs-approval
---

# Unstaged linting and subproject protocol version drift detection

Enable `along lint` to check unstaged working-tree files (`along lint <paths...>` and `along lint --worktree`) and extend `along doctor` to detect and align `.protocol-version` drift across nested subprojects. Currently, `along lint` only inspects staged git changes (`git diff --cached`), blocking agents from linting draft plans or untracked code before staging, and doctor does not audit protocol versions of nested subprojects.

## Requirements
- REQ-1: `along lint <path...>` MUST run content-level quality gates (clean ASCII typography, code fence languages, relative links, secret detection, stub detection) directly against the specified files without requiring `git add`.
- REQ-2: `along lint --worktree` MUST run content checks against all modified and untracked files in the current repository working tree.
- REQ-3: When linting specific files or unstaged changes, commit-level gates (`commit_issue_binding`, `commit-msg`) MUST be bypassed.
- REQ-4: `along doctor` MUST recursively scan all nested subdirectories containing `.along/`, report each context's `.protocol-version`, and warn if any subproject differs from the root protocol version.
- REQ-5: `along update --recursive` MUST traverse all discovered nested subprojects and run protocol migration/reconciliation on each.
- REQ-6: Hermetic unit tests in `tests/test_lint_unstaged.py` testing file-targeted linting, worktree linting, and recursive protocol version doctor audits.

## Acceptance Criteria
- [x] `along lint <path...>` checks specified files on disk without staging.
- [x] `along lint --worktree` audits all uncommitted working-tree modifications.
- [x] `along doctor` warns on subproject `.protocol-version` mismatch.
- [x] `along update --recursive` aligns subprojects.
