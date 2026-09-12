---
protocol: along
slug: runtime-hooks-cursor-opencode
type: feat
status: open
priority: medium
created: 2026-09-11
updated: 2026-09-11
agent: antigravity
tags: [hooks, cursor, opencode, runtime, adapters, mechanical-enforcement]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: [feat--runtime-enforcement-of-prose-rules]
related: [feat--runtime-enforcement-of-prose-rules]
---

# Cursor and OpenCode Runtime Hook Adapters and Interceptors

## 1. Objective

Implement runtime adapters, interceptors, and configuration generators for Cursor and OpenCode agent harnesses.

## 2. Requirements

1. **Protocol Contract**:
   - Inspect supported hook mechanisms, file save hooks, and terminal proxy wrappers in OpenCode / Cursor.
   - For environments lacking native `PreToolUse` lifecycle hooks, provide CLI proxy wrapper integration (`along run <cmd>`) or terminal interception.

2. **Adapter Implementation**:
   - Implement `alongkit.hooks.adapters.GenericCliAdapter`.
   - Ensure clean mapping to canonical `HookEvent`.

3. **Verification**:
   - Hermetic unit tests in `tests/test_hooks_generic.py`.
