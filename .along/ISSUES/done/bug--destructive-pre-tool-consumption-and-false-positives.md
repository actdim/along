---
protocol: along
protocol_version: "4.4.11"
slug: destructive-pre-tool-consumption-and-false-positives
type: bug
status: done
completed: 2026-10-12
priority: critical
created: 2026-10-12
updated: 2026-10-12
agent: antigravity
tags: [security, gates, toolnature, predicates, destructive, claude-code]
blocked_by: []
related: [bug--destructive-authorization-and-lock-hardening]
affects: [scripts/alongkit/hooks/predicates.py, scripts/alongkit/hooks/toolnature.py, scripts/alongkit/hooks/shellparse.py, scripts/alongkit/hooks/config.py]
---

# Fix PreToolUse Destructive Consumption, Eliminate Env Var and Git Classifier False Positives

## Problem

Audit review of commit c261135 identified:
1. Destructive authorization consumption failed in Claude Code: `consume_destructive_confirmation` ran only on `POST_TOOL_USE`, but Claude Code hook registration lacks `Bash|PowerShell` in `CLAUDE_POST_TOOL_MATCHER`. Furthermore, batch calls passed PreToolUse concurrently before the first PostToolUse fired.
2. `_DANGEROUS_ENV_VARS` omitted `PATH` and various `GIT_*` execution-hijacking variables (e.g. `GIT_PAGER`, `GIT_EDITOR`, `GIT_EXEC_PATH`, `GIT_DIR`). In `toolnature.py`, `extract_dangerous_env_overrides` searched tokens anywhere in the command, falsely classifying read commands like `echo $env:EDITOR`, `grep EDITOR= file`, and `echo "export PAGER=less"` as DESTRUCTIVE.
3. `git -c` was searched globally across all tokens instead of strictly before the subcommand, and `-c` was in global `val_options`. Consequently, `git grep -c foo`, `git commit -c HEAD`, and `git diff -c` became false positive DESTRUCTIVE. Global `val_options` also contained tool-specific PowerShell flags (`-name`, `-filter`, `-path`), breaking tools like `find . -name x` and `mkdir -p`.
4. Writing or deleting in system temporary directories (`$env:TEMP`, `%TEMP%`, `/tmp`) was misclassified as DESTRUCTIVE instead of permitted scratchpad/temp operations under workspace containment. `$env:TEMP` syntax was unexpanded by `os.path.expandvars`.

## Requirements

- REQ-1: Destructive confirmations are consumed directly during PreToolUse evaluation (`check_require_plan_approval`) upon authorization grant, guaranteeing single-use semantics across all runtimes without relying on PostToolUse.
- REQ-2: Add `Bash|PowerShell` to `CLAUDE_POST_TOOL_MATCHER` in `hooks/config.py`.
- REQ-3: Treat `PATH` and all `GIT_*` variables as dangerous in `shellparse.py`. In `toolnature.py`, check dangerous environment variable overrides strictly in leading assignment positions before the command (or inside `env`/`export`/`set`/PowerShell `$env:VAR =`).
- REQ-4: Inspect `git -c` allowlist strictly on global options before the git subcommand. Remove `-c` and `-p` from global `val_options`. Restrict PowerShell-specific parameter names in `val_options` to PowerShell cmdlets.
- REQ-5: Expand `$env:VAR` in path classifiers and permit writes/deletions within system temporary directories (`tempfile.gettempdir()`, `$env:TEMP`, `/tmp`) in `_classify_out_file` and `_classify_deletion`.

## Acceptance Criteria

- [x] Destructive confirmation consumed atomically on PreToolUse
- [x] Claude Code PostToolUse matcher includes Bash and PowerShell
- [x] PATH and all GIT_* treated as dangerous; env var overrides checked only at command assignment position
- [x] echo $env:EDITOR, grep EDITOR= file, and echo "export PAGER=less" classify as READ_ONLY
- [x] git grep -c foo, git commit -c HEAD, and git diff -c do not trigger destructive git -c checks
- [x] mkdir -p and find . -name x parse options and arguments correctly
- [x] Out-File and Remove-Item targeting $env:TEMP / /tmp classify as WORKSPACE_WRITE
- [x] Automated tests passing with zero regressions
