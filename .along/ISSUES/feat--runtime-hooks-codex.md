---
protocol: along
slug: runtime-hooks-codex
type: feat
status: open
priority: high
created: 2026-09-11
updated: 2026-09-11
agent: antigravity
tags: [hooks, codex, runtime, adapters, mechanical-enforcement]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: [feat--runtime-enforcement-of-prose-rules]
related: [feat--runtime-enforcement-of-prose-rules]
---

# OpenAI Codex Runtime Hook Adapter and Configuration

## 1. Objective

Implement the runtime adapter and configuration generator for OpenAI Codex CLI and headless harness, integrating with the core `alongkit.hooks` engine.

## 2. Requirements

1. **Protocol Contract**:
   - OpenAI Codex hooks execute shell commands with context payloads.
   - Intercept `PreToolUse` (file writes, shell execution) and `Stop` events.
   - Process exit code 2 blocks the action and injects stderr to the model.

2. **Adapter Implementation**:
   - Implement `alongkit.hooks.adapters.CodexAdapter`.
   - Parse Codex event payload from stdin.
   - Map Codex tool operations to canonical `HookEvent`.
   - Format remediation output on stderr and set appropriate process returncode.

3. **Configuration Generation**:
   - Generate `.codex/hooks.json` (or `config.toml` hook section) with command paths targeting `along_hook.py`.

4. **Verification**:
   - Hermetic unit tests in `tests/test_hooks_codex.py`.
