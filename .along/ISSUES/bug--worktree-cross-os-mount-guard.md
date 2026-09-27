---
protocol: along
protocol_version: "4.2.0"
slug: worktree-cross-os-mount-guard
type: bug
status: open
priority: medium
created: 2026-09-27
updated: 2026-09-27
agent: cowork
tags: [worktree, cross-platform, cowork]
milestone: v4.4.0-multi-user-merge-automation
blocked_by: []
related: [feat--cowork-runtime-support]
---

# along worktree must refuse cross-OS mounted repositories

## Problem

`alongkit.worktree` creates git worktrees and links dependencies (`node_modules`, `.venv`) with NTFS junctions or symlinks. When the engine runs in a Linux environment on a repository that lives on a Windows filesystem (Cowork VM mount, WSL `/mnt/c`, Docker bind mount), `git worktree add` records Linux absolute paths in `.git/worktrees/*/gitdir`, and symlinks cannot be created (`core.symlinks=false`). The worktree is then broken for the Windows host, and teardown may leave orphaned metadata.

## Requirements

- REQ-1: Before `along worktree create`, detect a cross-OS mount: repo `core.symlinks=false` with a POSIX host, a 9p/drvfs/fuse filesystem type, or a Windows-style `core.worktree`/existing gitdir paths.
- REQ-2: In that case refuse with a clear message (or require `--force-cross-os`) and suggest running the command on the host OS.
- REQ-3: `/along-team --worktree` degrades to in-place mode with a warning instead of failing mid-plan.
- REQ-4: Tests simulate the detection inputs.

## Acceptance Criteria

- [ ] Running `along worktree create` from a Linux VM on a Windows-mounted repo does not modify `.git/worktrees`
- [ ] Automated tests passing
