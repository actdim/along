---
protocol: along
slug: runtime-hooks-claude-code
date: 2026-09-13
agent: antigravity
summary: "Implemented Anthropic Claude Code runtime hook adapter, exit code 2 stderr routing, configuration generator, hermetic test suite, and KB documentation"
milestone: v4.0.0-runtime-gates-and-worktree-isolation
issues_advanced: []
issues_completed: [feat--runtime-hooks-claude-code]
decisions: []
risks_logged: []
spikes_conducted: []
branch: main
commit: unknown
---

# Session Log: 2026-09-13 - Claude Code Runtime Hooks Adapter and Configuration

## 1. Objectives & Context

Implementation of `[feat--runtime-hooks-claude-code]` under milestone `v4.0.0-runtime-gates-and-worktree-isolation` via the `along-team` protocol:
- Implement `alongkit.hooks.adapters.ClaudeCodeAdapter` mapping Claude Code tool invocations (`Write`, `Edit`, `Bash`, `Stop`) to canonical `HookEvent` instances.
- Translate gate denial outcomes to Claude Code process conventions: exit code 2 with remediation messages written to `stderr`.
- Harden `scripts/along_hook.py` dispatcher and predicates to handle `new_string` in edit operations and route non-zero exit codes to `stderr`.
- Implement `install_claude_hooks()` in `scripts/alongkit/hooks/config.py` to generate or update `.claude/settings.json`, preserving existing user settings, permissions, and custom hooks.
- Create hermetic test suite in `tests/test_hooks_claude.py` and update documentation in `docs/topic--runtime-hooks-and-gates.md`.

## 2. Engineering Provenance

### 2.1 Initial Implementation Plan (Baseline)
- Evaluated task complexity as `M-Size` (4-5 files touched, isolated adapter module, clear interface).
- Living Plan Revision 1 formulated across 4 sequential steps:
  - Step 1: Implement `ClaudeCodeAdapter` and register in `adapters/__init__.py` [REQ-1].
  - Step 2: Harden dispatcher and predicates: stderr routing and `new_string` extraction [REQ-2].
  - Step 3: Implement `.claude/settings.json` hook manifest generator and installer in `config.py` and `along_hook.py` [REQ-3].
  - Step 4: Hermetic test suite `tests/test_hooks_claude.py`, documentation parity, and full suite verification [REQ-4, REQ-5].

### 2.2 Execution & Loop Trace (Fixes & Re-plans)
- **Step 1 (Implementer)**: Created `claude.py`, mapped tools and arguments, registered in `ADAPTERS`. Verdict: PASS.
- **Step 2 (Inline)**: Updated `along_hook.py` to route `exit_code != 0` to `sys.stderr`. Added `new_string` extraction in `predicates.py`. Verdict: PASS.
- **Step 3 (Inline)**: Implemented `get_claude_hook_manifest()` and `install_claude_hooks()`. Extended `along hook install` CLI to accept `--runtime {antigravity,claude,all}`. Verdict: PASS.
- **Step 4 (Inline & Fix Loop)**:
  - Created `tests/test_hooks_claude.py` with 14 tests.
  - Executed test suite: 1 test failed (`test_cli_invocation_cli_safety_heredoc_exits_two`) due to `cli_safety` default mode being `shadow` and `--mode enforce` CLI flag not propagating to individual gate mode overrides.
  - Executed Fix Loop: Updated `along_hook.py` so that an explicit `--mode` CLI flag overrides all registered gate modes.
  - Re-ran test suite: all 418 tests passed (0 failures).
  - Updated `docs/topic--runtime-hooks-and-gates.md` and synchronized Knowledge Base. Verdict: PASS.

### 2.3 Verification Walkthrough & Gate Manifest
- Automated Tests: `python .along/scripts/test.py` -> 418 passed, 0 failed, 1 skipped.
- Gate Traceability: `python scripts/along_hook.py verify` -> 11/11 gates verified, clean bi-directional contract.
- Typography: `python scripts/along_exec.py sanitize --check` -> 433 files scanned, no banned characters.
- Link Integrity: `python scripts/along_kb_sync.py` -> All 286 relative Markdown links verified on disk.

Gate Execution Manifest:
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [python .along/scripts/test.py]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-1, REQ-2, REQ-3, REQ-4, REQ-5]
- Blast Radius: EXECUTED (PASS)
- Documentation Parity: EXECUTED (PASS)
- Clean Typography: EXECUTED (PASS)
