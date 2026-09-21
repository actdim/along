---
protocol: along
protocol_version: "3.8.0"
slug: updater-explicit-global-sync
type: feat
status: done
priority: high
created: 2026-09-20
updated: 2026-09-21
completed: 2026-09-21
agent: antigravity
tags: [along-update, cli, isolation, skills]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: []
related: []
---

# Decouple Repository Context Updates from Global Machine Skill Installation

## Context & Problem Statement

Currently, running `along update` (or `python scripts/along_update.py`) has an unintended side effect that breaks environment isolation:
1. In the development repository (`actdim/along`), it unconditionally runs `install.ps1 -Target all`, overwriting global user skills (`~/.gemini/config/skills/`, etc.) with in-development files even when the developer only intended to update the repository's context.
2. In consumer repositories, it attempts to fetch updates from remote GitHub and install them into the user's global directories, conflating updating the repository with modifying the host machine.
3. This violates the Single Responsibility Principle and Least Surprise: updating an agent context inside a workspace should be completely isolated to that repository by default.

## Acceptance Criteria

- [x] `along_update.py` supports an explicit `--global` (or `--sync-global`) CLI flag.
- [x] By default (`--global` not specified):
  - Repository contexts (managed `AGENTS.md` block, `.along/` projections, lifecycle hooks) are updated cleanly.
  - Global user skills in `~/.gemini/`, `~/.claude/`, etc. are NEVER modified or installed.
- [x] When `--global` is explicitly specified:
  - In dev repository (`is_dev_repo`): installs local skills to global paths via `install.ps1` / `install.sh`.
  - In consumer repository: updates global skills from remote Git if newer or `--force` is set.
- [x] Help text and docstrings in `scripts/along_update.py` and `skills/along-update/SKILL.md` document `--global`.
- [x] Automated tests verify that default runs do not trigger global installation, and that `--global` is accepted and handled.
