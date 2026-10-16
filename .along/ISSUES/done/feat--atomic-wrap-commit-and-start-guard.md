---
protocol: along
protocol_version: "4.4.15"
slug: atomic-wrap-commit-and-start-guard
type: feat
status: done
completed: 2026-10-16
priority: high
created: 2026-10-16
updated: 2026-10-16
agent: antigravity
tags: [lifecycle, wrap, commit, start, gates, cli-invariance]
blocked_by: []
related: [bug--wrapped-work-left-uncommitted, feat--parallel-session-closeout]
---

# Atomic wrap commit, clean start guard, and CLI black-box invariance

## Problem

When users and agents finish tasks using `along wrap`, uncommitted files remain in the working tree without being committed to Git. Successive tasks started via `along start` accumulate uncommitted changes across different tasks in a single working tree. When users subsequently attempt to commit, bump versions, and push, attribution is entangled, causing merge noise, broken submodules, or failure. Furthermore, when CLI errors occur, agents inappropriately read and reverse-engineer internal Along engine Python scripts (`.along/bin/*.py`, `alongkit/**`) instead of treating the CLI as a black box.

## Requirements

- REQ-1: `along wrap` must automatically commit attributed files and generated metadata by default using Conventional Commits (`<type>(<slug>): <title> (refs #<slug>)`). An explicit `--no-commit` flag must allow opting out when manual inspection is desired.
- REQ-2: `along start <slug>` must validate the working tree:
  - Hard block if uncommitted files from previously completed (wrapped) issues exist in the working tree.
  - Block with guidance (or require `--allow-dirty` / recommend `--worktree`) if uncommitted changes from another active issue exist in the same working tree.
- REQ-3: Codify `CLI Black-Box Invariance` rule into `skills/along-init/protocol.md` and `AGENTS.md` forbidding agents from inspecting, reading, or editing internal Along engine code (`.along/bin/*.py`, `~/.along/bin/`, `alongkit/**`).

## Acceptance Criteria

- [x] `along wrap` automatically executes Git commit for attributed and metadata files by default
- [x] `along wrap --no-commit` skips automatic commit
- [x] `along start` blocks when wrapped uncommitted changes exist in working tree
- [x] `along start` blocks or prompts for `--worktree` / `--allow-dirty` when dirty uncommitted changes exist
- [x] `skills/along-init/protocol.md` and `AGENTS.md` specify `CLI Black-Box Invariance`
- [x] Automated tests pass
