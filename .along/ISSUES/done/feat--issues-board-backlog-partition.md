---
protocol: along
protocol_version: "3.8.0"
slug: issues-board-backlog-partition
type: feat
status: done
completed: 2026-09-21
priority: high
created: 2026-09-20
updated: 2026-09-21
agent: antigravity
tags: [along-exec, entities, issues-board, backlog, milestone]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: []
related: [issue-create-stamps-wrong-agent-and-milestone, entity-lifecycle-cli-orchestration]
---

# Partition Active vs Backlog on ISSUES Board and Decouple Milestone Stamping

## Context & Problem Statement

Currently, the distinction between active work (`status: in-progress`) and backlog items (`status: open` / `blocked`) is corrupted in two key places:

1. **`compile_issues_board` in `scripts/alongkit/entities.py`**:
   The projection compiler indiscriminately places every non-completed issue file from `.along/ISSUES/*.md` into the `## Active` section, leaving `## Backlog` as an empty static comment `<!-- Planned or deferred issues -->`.
2. **`along issue create` in `scripts/along_exec.py`**:
   When a new issue is created, it is created with `status: open`, but immediately injected into `## Active` via string replacement instead of recompiling or placing it under `## Backlog`.
3. **Milestone Auto-Stamping**:
   `along issue create` automatically stamps the active milestone if exactly one in-progress milestone exists, with no ability to opt out or specify that a task belongs to the general/unplanned backlog (`--no-milestone` / `--milestone none`).

## Acceptance Criteria

- [x] `compile_issues_board` inspects front-matter `status` of issues:
  - `in-progress` issues are placed under `## Active`.
  - `open` and `blocked` issues are placed under `## Backlog`.
  - When either section is empty, clean placeholder comments are rendered (`<!-- No active issues -->` or `<!-- No backlog issues -->`).
- [x] `along issue create` no longer hacks the board with string replacements on `## Active`, but uses `compile_issues_board` / `sync_issues_board`.
- [x] `along issue create` supports `--no-milestone` and `--milestone none|null|~` to deliberately create issues in the general backlog without auto-stamping the active milestone.
- [x] Existing tests in `tests/test_issue_lifecycle.py` and other test files pass cleanly, and new unit tests verify the Active vs Backlog board partitioning and milestone opt-out.
