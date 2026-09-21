---
protocol: along
protocol_version: "3.8.0"
slug: test-gated-code-merge-pipeline
type: feat
status: open
priority: medium
created: 2026-09-21
updated: 2026-09-21
agent: antigravity
tags: [git, merge, code, tests, quality-gates, rollback, ast]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: [feat--docs-semantic-conflict-resolution]
blocks: []
related: [feat--git-merge-drivers-and-setup, feat--docs-semantic-conflict-resolution]
---

# Test-Gated Source Code Conflict Resolution Pipeline & Rollback Engine

## Summary

Automatic code merging is hazardous: even when conflict markers are cleanly eliminated, merged source code may suffer from syntax errors, typography violations, or silent semantic regressions where one branch breaks assumptions made in another branch.

This issue implements a test-gated source code conflict resolution and rollback pipeline:
1. `along resolve --code`: Identifies conflicted source code files (`.py`, `.ts`, `.rs`, `.cs`, etc.) and performs structured AST/LLM code conflict reconciliation.
2. Mandatory Quality Gate Verification Pipeline:
   - Syntax validation (`compileall`, language parsers).
   - Clean typography gate (`along sanitize`).
   - Test execution via project lifecycle hook (`along test -q`).
3. Transactional Rollback: Employs `alongkit.transaction.FileTransaction`. If any gate or unit test fails after an auto-merge attempt, the entire merge operation is atomically rolled back to preserve the original Git conflict markers and diagnostic state.
4. Pre-Merge Conflict Predictor (`along conflict-check <branch>`): Scans target branch diffs before merging to warn developers about overlapping modified symbols and blast radius.

## Detailed Implementation Plan

### Stage 3.1: Code Conflict Resolution Engine (`scripts/along_resolve.py`)
- Locate unmerged source code files across the workspace.
- Parse conflict blocks (`<<<<<<<`, `=======`, `>>>>>>>`).
- Apply structural AST / Language-aware merge:
  - Non-overlapping function/class additions within the same module are placed sequentially.
  - Import statements are merged using set-union and sorted according to project conventions.
  - For overlapping function bodies: Invoke agentic resolution prompt with full function context and docstrings.

### Stage 3.2: Verification Pipeline & Quality Gates
- Execute verification steps in strict order:
  - Step 1: Syntax check (`python -m compileall -q` for Python, `tsc --noEmit` for TypeScript).
  - Step 2: Typography check via `alongkit.sanitizer` to ensure no forbidden non-ASCII typography or invisible characters were introduced.
  - Step 3: Run project test runner via `along test -q` (or `python .along/scripts/test.py`).

### Stage 3.3: Transactional Rollback & Error Diagnostics
- Wrap the entire code resolution process in `alongkit.transaction.FileTransaction`:
  - If syntax verification fails or tests return non-zero exit code:
    - Trigger `transaction.rollback()`.
    - Restore original Git conflict state.
    - Output clear diagnostic report identifying the failing test or syntax error and specific conflict hunks that caused it.
  - If and only if all tests pass with zero failures:
    - Stage resolved files (`git add <file>`).
    - Mark conflict as resolved.

### Stage 3.4: Pre-Merge Conflict Predictor (`along conflict-check <branch>`)
- Implement `along conflict-check <target-branch>`:
  - Compares `git merge-base HEAD <target-branch>` with both branches.
  - Analyzes overlapping file lists.
  - Uses `code-review-graph` or AST parser to detect whether both branches modified identical symbols, functions, or interfaces.
  - Outputs advisory risk level (Low, Medium, High) with recommendations for task isolation.

### Stage 3.5: Hermetic Test Suite (`tests/test_along_resolve_code.py`)
- Test successful auto-resolution of non-overlapping import and function additions.
- Test automatic rollback when merged code introduces a test failure.
- Test conflict check detection between synthetic divergent branches.

## Acceptance Criteria
- [ ] `along resolve --code` merges non-overlapping code hunks and imports cleanly.
- [ ] Auto-merge process is strictly blocked from completing if `along test` fails.
- [ ] `FileTransaction` reliably restores conflict markers upon test failure.
- [ ] `along conflict-check` accurately identifies overlapping symbols between divergent Git branches.
- [ ] Hermetic unit tests in `tests/test_along_resolve_code.py` pass cleanly.
