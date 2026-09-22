---
protocol: along
slug: installer-path-configuration-and-cli-resolution
type: bug
status: done
completed: 2026-09-21
priority: high
created: 2026-09-21
updated: 2026-09-21
agent: antigravity
tags: [installer, cli, path, windows, skills]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: []
related: []
---

# Installer PATH Configuration and Robust CLI Resolution

## Summary
When Along is installed via `install.ps1`, `install.bat`, or `install.sh`, the CLI engines are placed in `~/.along/bin/`, but this directory was never added to the User `PATH`. In addition, skills instructed agents to invoke bare `along <cmd>`, causing repetitive `'along' is not recognized` failures in external repositories.

## Scope
1. Update `install.ps1` to configure User `PATH` on Windows and remove on `-Uninstall`.
2. Update `install.sh` to check `$PATH` and display export instructions for user shell profiles.
3. Update `scripts/along_exec.py` `doctor` command to diagnose `along` availability on `PATH`.
4. Update skills (`skills/along-team/SKILL.md`) with explicit CLI fallback guidance.
