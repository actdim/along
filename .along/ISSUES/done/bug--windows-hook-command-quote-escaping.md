---
protocol: along
protocol_version: "3.9.3"
slug: windows-hook-command-quote-escaping
type: bug
status: done
completed: 2026-09-21
priority: high
created: 2026-09-21
updated: 2026-09-21
agent: antigravity
tags: [hooks, antigravity, windows, cmd, quoting]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: []
related: [bug--update-hooks-and-monorepo-sync-hardening]
---

# Windows Hook Command Quote Escaping in Global Manifests

## Problem Description

During global runtime hook installation (`along update --global`), `get_hook_command()` formats:
`f'python "{script_path}" --runtime {runtime} --event {event}'` with double quotes around `script_path`.

On Windows:
1. Antigravity executes hook commands via `cmd.exe /c <command>`.
2. Antigravity is implemented in Go. When Go's `os/exec` constructs command lines on Windows, it escapes internal double quotes as `\"`.
3. `cmd.exe` does not unescape `\"` (its escape character is `^`), and passes `\"` verbatim to `python.exe`.
4. Python's `CommandLineToArgvW` parses `\"` as an escaped literal quote, yielding `sys.argv[1]` starting with a quote character `"`.
5. Python fails to detect the absolute drive root (e.g. `C:`), treats the path as relative, and prepends the current working directory (`C:\Users\Admin\.gemini\config\`), resulting in `python: can't open file 'C:\Users\Admin\.gemini\config\"C:\Users\Admin\.along\bin\along_hook.py"': [Errno 22] Invalid argument`.
6. Antigravity treats exit status 2 as a blocking failure on `PreToolUse`, completely disabling all agent file writing and shell execution tools (`write_to_file`, `replace_file_content`, `run_command`).

## Required Fix

1. Update `get_hook_command()` in `scripts/alongkit/hooks/config.py`:
   - On Windows, omit quotes when `script_path` contains no whitespace.
   - If `script_path` contains whitespace, resolve its 8.3 short path (`GetShortPathNameW`) so quotes are not needed.
2. Synchronize the fix to `~/.along/bin/alongkit/hooks/config.py`.
3. Update tests in `tests/test_update_and_hooks_hardening.py` to verify quote safety on Windows.
