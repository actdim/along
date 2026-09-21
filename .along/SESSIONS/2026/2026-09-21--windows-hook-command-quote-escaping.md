---
protocol: along
date: 2026-09-21
slug: windows-hook-command-quote-escaping
agent: antigravity
branch: main
commit: pending
summary: Fixed Windows hook command quote escaping in alongkit.hooks.config to prevent cmd.exe /c literal quote injection and agent tool deadlocks.
milestone: v4.0.0-runtime-gates-and-worktree-isolation
issues_advanced: []
issues_completed: [windows-hook-command-quote-escaping]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Fix Windows Hook Command Quote Escaping in Global Manifests

## Summary
Resolved a critical runtime deadlock on Windows where `get_hook_command()` in `alongkit.hooks.config` wrapped global hook script paths in quotes. When Antigravity executed hook commands via `cmd.exe /c`, Go `os/exec` escaped quotes as `\"`. Because `cmd.exe` does not unescape `\"`, Python received literal quotes in `sys.argv[1]`, causing path resolution failure (`[Errno 22] Invalid argument`) and deadlocking all agent file writing and shell execution tools.

## Work Completed
- Implemented `_format_hook_script_path()` in `scripts/alongkit/hooks/config.py`:
  - On Windows (`sys.platform == "win32"`):
    - Omit quotes when the script path contains no whitespace.
    - If whitespace is present, resolve via 8.3 short path (`GetShortPathNameW`) so quotes are never needed.
    - Fall back to quotes only if short path resolution is unavailable.
  - On POSIX: preserve standard quoting for paths with whitespace.
- Updated `get_hook_command()` to use `_format_hook_script_path()`.
- Synchronized the fix to the global installation at `~/.along/bin/alongkit/hooks/config.py`.
- Narrowed exception handling in `_format_hook_script_path()` to `(AttributeError, OSError, ValueError, RuntimeError)` to satisfy Along's exception handling quality gate.
- Added automated unit test `test_format_hook_script_path_windows_safety` in `tests/test_update_and_hooks_hardening.py`.
- Closed issue `bug--windows-hook-command-quote-escaping` and synchronized `.along/ISSUES.md`.

## Code Review & Blast Radius
- All 509 tests pass cleanly via `.along/scripts/test.py`.
- `along sanitize` confirms 489 files scanned with zero forbidden non-ASCII typography.
- Verified that global hooks manifest generates unquoted command strings on Windows.
