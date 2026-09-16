---
protocol: along
date: 2026-09-15
slug: runtime-hooks-cursor-opencode
agent: antigravity
branch: main
commit: pending
summary: Implemented Cursor and OpenCode runtime hook adapters, GenericCliAdapter, along run CLI proxy wrapper, and hermetic verification test suite.
milestone: v4.0.0-runtime-gates-and-worktree-isolation
issues_advanced: []
issues_completed: [runtime-hooks-cursor-opencode]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Cursor and OpenCode Runtime Hook Adapters & Generic CLI Proxy

## Summary
Implemented GenericCliAdapter, command proxy wrapper (along run <cmd>), Cursor hook configuration generator (.cursor/hooks.json), and hermetic test suite for Cursor and OpenCode agent harnesses.

## Initial Implementation Plan (Baseline)
- Step 1 (REQ-2): Implement alongkit.hooks.adapters.GenericCliAdapter in scripts/alongkit/hooks/adapters/generic.py and register under generic, cursor, opencode.
- Step 2 (REQ-1): Implement along run <cmd> command proxy wrapper in scripts/along_exec.py and scripts/along_hook.py.
- Step 3 (REQ-3): Implement get_cursor_hook_manifest() and install_cursor_hooks() in scripts/alongkit/hooks/config.py.
- Step 4 (REQ-4, REQ-5): Verification, hermetic unit tests in tests/test_hooks_generic.py, and documentation parity.

## Execution & Loop Trace (Fixes & Re-plans)
- Step 1 implemented and verified cleanly against AST compilation and typography sanitizer.
- Step 2 implemented: Added handle_run_command in along_exec.py and along_hook.py. Observed live hook interception during development that detected a Python variable scoping issue in along_hook.py, immediately resolved via top-level imports. Verified along run against benign and gate-violating commands in enforce mode.
- Step 3 implemented: Scaffolding engine for .cursor/hooks.json schema v1, idempotent updates, third-party hook preservation.
- Step 4 implemented: Added 10 hermetic tests in tests/test_hooks_generic.py covering adapter resolution, argument normalization, plain string fallback, proxy execution, and installer idempotency.

## Verification Walkthrough & Gate Manifest
- Automated tests: Ran 475 tests in 38.9s via python .along/scripts/test.py. 100% passed (zero failures).
- Traceability: along hook verify verified clean bi-directional contract (13/13 gates anchored).
- Knowledge Base: docs/topic--runtime-hooks-and-gates.md updated and synchronized via along kb sync (296/296 relative links verified).
- Typography: along sanitize scanned 457 files, zero non-ASCII banned characters found.

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [475 tests passed]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-1, REQ-2, REQ-3, REQ-4, REQ-5]
- Blast Radius: EXECUTED (PASS)
- Documentation Parity: EXECUTED (PASS)
- Clean Typography: EXECUTED (PASS)
