---
protocol: along
protocol_version: "4.9.1"
slug: engine-atomicity-and-gate-resilience
type: bug
status: done
completed: 2026-11-22
priority: high
created: 2026-11-22
updated: 2026-11-22
agent: antigravity
tags: [engine, wrap, gates, atomicity, submodules, verify]
milestone: v5.0.0-agent-run-protocol-and-observability
blocked_by: []
related: []
plan_status: approved
---

# Fix engine wrap atomicity, gate reference integrity, and multi-subproject session friction

## Problem
Operational sessions in multi-submodule and nested repositories (such as Mempart under Along v4.9.1) surfaced critical engine atomicity issues, false-positive gate denials, and multi-project session friction:
1. `along wrap` leaves a half-done state: disk mutations commit before the auto-commit step. When the commit fails (e.g., on unchecked acceptance criteria or gate violations), git index is left dirty and staged with no commit created.
2. `entity-reference-integrity` checks only git index snapshots, reporting existing on-disk entities as dangling references and erroneously advising renaming or superseding them.
3. Stub detection in lifecycle commands reports only partial findings per run instead of all staged/active stubs at once.
4. Nested subprojects without test suites fail commit gates with "Ran 0 tests" treated as failure.
5. Inability for users to settle gate denials across sessions when agent bypass commands are blocked by host oversight filters.
6. Submodule directory changes (`cd`) lock tools by corrupting repo root resolution.
7. `workspace-containment` blocks paths explicitly provided as working directories in the session.
8. `along test --help` (and lifecycle hooks in `along_exec.py`) executes the entire test suite rather than printing usage help.
9. Full test gate runs unconditionally on commits and wraps touching purely documentation, markdown, and `.along/` entities, without automatic path-based test skipping.

## Requirements
- REQ-1: Atomic Wrap: `along wrap` MUST validate acceptance criteria checkboxes and pre-commit checks BEFORE applying disk or git index mutations. If auto-commit fails, wrap MUST unstage files and output exact failure state without leaving an uncommittable staged index.
- REQ-2: Entity Reference Integrity: `check_entity_references` MUST check whether a referenced entity file exists on disk before classifying it as dangling. If the file exists on disk but is not staged/tracked, it MUST report that the file needs staging rather than suggesting rename/supersede.
- REQ-3: Complete Stub Reporting: Stub and scaffold detection audits MUST collect and report all offending files in a single pass rather than terminating early.
- REQ-4: Zero-Test Subprojects: When no test runner or tests are discovered in a subproject, the verify gate MUST treat it as `tests: none` (with a notice) rather than a hard failure.
- REQ-5: User Gate Approvals: Provide a dedicated user-facing command `along gates approve <id>|--issue <slug>|--all` to allow users to settle pending denials across sessions, and auto-settle denials when an action is superseded by a compliant operation.
- REQ-6: Submodule Root Resilience: Tool root resolution MUST resolve the workspace root reliably and not get permanently locked by a directory change (`cd`) into a submodule.
- REQ-7: Allowed Roots: `workspace-containment` MUST honor extra working directories registered in the host session.
- REQ-8: Lifecycle Hook CLI Help: `along_exec.py` MUST intercept `-h` and `--help` for lifecycle actions (`test`, `build`, `dev`, `debug`) and display command help without executing the underlying hook scripts.
- REQ-9: Docs-Only Test Policy: Commit and wrap test gates MUST automatically skip test suite execution when all staged changes match documentation and metadata globs (`.along/**`, `docs/**`, `*.md`, `AGENTS.md`, `llms*.txt`), emitting a clear `tests: skipped (docs-only change)` notice.

## Acceptance Criteria
- [x] `along wrap` fails fast if acceptance criteria checkboxes (- [ ]) are open, without mutating files or staging changes
- [x] `_auto_commit_wrapped_work` handles failures cleanly and outputs an unambiguous final status (committed sha or clear failure with next steps)
- [x] `check_entity_references` distinguishes untracked on-disk entity files from missing entities and suggests staging them
- [x] Stub detector reports all detected stubs in one pass
- [x] Commit gate does not fail when test discovery finds 0 tests in a subproject without test infrastructure
- [x] `along gates approve` command implemented for user resolution of pending gate denials
- [x] `along test --help` displays help text immediately without triggering test execution
- [x] Pure docs and markdown commits automatically skip test execution with an explicit notice
- [x] Automated tests in `tests/` covering wrap atomicity, entity reference on-disk check, stub reporting completeness, help interception, and docs-only test skipping
