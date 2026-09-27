---
protocol: along
protocol_version: "4.2.0"
slug: non-hermetic-global-skill-tests
type: bug
status: open
priority: high
created: 2026-09-27
updated: 2026-09-27
agent: cowork
tags: [tests, hermetic, cross-platform]
milestone: v4.3.0-developer-experience-and-runtime-resilience
blocked_by: []
related: [task--ci-test-matrix-workflow]
---

# Tests depend on globally installed skills and Windows-only APIs

## Problem

The protocol requires hermetic tests (throwaway fixtures, never live or global state), but on a clean Linux machine with Python 3.12 the suite reports 5 failures and 1 error out of 639 tests. They pass only on a developer machine where Along is already installed globally, or only on Windows.

## Evidence

- `test_skills_and_scripts`: `test_15_along_update_multi_context_and_uninit_subprojects`, `test_17g_illustrative_placeholders_narrowing`, `test_19_retroactive_link_rewriting_without_kb_dir`, `test_34_along_update_purges_local_runtime_hooks`, `test_35_along_update_explicit_global_isolation` fail with `[ERROR] Could not locate protocol.md in local repo or global skills.` - `along_update.py` resolves `protocol.md` from the user's global skill directories instead of the repository under test.
- `test_update_and_hooks_hardening.test_format_hook_script_path_windows_safety` errors with `AttributeError: module 'ctypes' has no attribute 'windll'` - patches a Windows-only API without `skipUnless(sys.platform == "win32")`.

## Requirements

- REQ-1: `along_update.py` resolves `protocol.md` from an explicit source root (the running checkout or an injected path) before falling back to global skills; tests pass the fixture path explicitly.
- REQ-2: Tests redirect `HOME` / `USERPROFILE` and all provider home variables to a temp directory, so global state is never read.
- REQ-3: Windows-only tests are guarded with `unittest.skipUnless(sys.platform == "win32", ...)`; POSIX-only tests likewise.
- REQ-4: Add a meta-test that fails if any test reads from the real user home (e.g. by poisoning `HOME` with a non-existent path in the runner).

## Acceptance Criteria

- [ ] Full suite green on clean Linux and Windows runners without a global Along install
- [ ] Automated tests passing
