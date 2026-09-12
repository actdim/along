---
protocol: along
slug: runtime-hooks-claude-code
type: feat
status: open
priority: high
created: 2026-09-11
updated: 2026-09-11
agent: antigravity
tags: [hooks, claude-code, runtime, adapters, mechanical-enforcement]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: [feat--runtime-enforcement-of-prose-rules]
related: [feat--runtime-enforcement-of-prose-rules]
---

# Claude Code Runtime Hook Adapter and Configuration

## 1. Objective

Implement the runtime adapter and configuration generator for Anthropic Claude Code CLI, integrating with the core `alongkit.hooks` engine.

## 2. Requirements

1. **Protocol Contract**:
   - Claude Code hooks communicate via standard process exit codes:
     - `exit 0`: Tool invocation allowed.
     - `exit 2`: Tool invocation blocked, with standard error (`stderr`) fed back to the model as an error/remediation message.
   - Events to support:
     - `PreToolUse`: Intercept `WriteFile`, `EditFile`, and shell commands.
     - `PostToolUse`: Post-tool diagnostics and syntax compilation.
     - `Stop`: Quality gate and wrap verification.

2. **Adapter Implementation**:
   - Implement `alongkit.hooks.adapters.ClaudeCodeAdapter`.
   - Parse Claude Code JSON payload from stdin.
   - Map tool names (`WriteFile`, `EditFile`, `Bash`) to canonical `HookEvent`.
   - Emit exit code 2 and formatted stderr on gate denial.

3. **Configuration Generation**:
   - Generate or update `.claude/settings.json` configuring hook command invocations pointing to `python scripts/along_hook.py --runtime claude --event ...`.
   - Ensure paths are cross-platform compatible (Windows cmd/PowerShell and Unix POSIX).

4. **Verification**:
   - Hermetic unit tests in `tests/test_hooks_claude.py`.
