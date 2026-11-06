---
protocol: along
protocol_version: "4.6.1"
slug: verify-worktree-env-readiness-hardening
type: task
status: done
completed: 2026-11-06
priority: medium
created: 2026-11-06
updated: 2026-11-06
agent: antigravity
tags: []
blocked_by: []
related: []
plan_status: approved
---

# Verify and harden worktree environment readiness against edge cases

Verify the recent submodule and worktree readiness implementation in a separate verification session, identifying and resolving latent edge cases including POSIX path preservation in inspect_git_dir, immediate-child workspace root detection, and Python flag handling in recovery command classification.

## Requirements
- REQ-1: `inspect_git_dir` MUST preserve absolute path prefixes (including leading slashes on POSIX systems) when resolving `primary_repo` from `norm_gitdir`.
- REQ-2: `_has_workspace_node_modules` MUST correctly resolve workspace roots when `primary_repo` is an immediate child directory of the workspace root (`pnpm-workspace.yaml`, `package.json` workspaces, `lerna.json`).
- REQ-3: `_is_recovery_command` MUST robustly skip Python command-line flags (e.g., `-u`, `-B`) and recognize full Along governance and lifecycle subcommands.
- REQ-4: Hermetic tests in `tests/test_worktree.py` MUST verify POSIX gitdir normalization, Python interpreter flag tolerance, and immediate-child workspace detection.

## Acceptance Criteria
- [x] `inspect_git_dir` resolves POSIX paths with leading slash intact.
- [x] Immediate-child subprojects of a workspace root correctly resolve hoisted `node_modules`.
- [x] Recovery commands prefixed with `python -u scripts/along_exec.py ...` are recognized.
- [x] All new edge-case tests pass hermetically.
- [x] Full repository test suite passes.
