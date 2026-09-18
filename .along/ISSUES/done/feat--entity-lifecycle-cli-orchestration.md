---
protocol: along
protocol_version: "3.6.0"
slug: entity-lifecycle-cli-orchestration
type: feat
status: done
completed: 2026-09-17
priority: high
created: 2026-09-17
updated: 2026-09-17
agent: antigravity
tags: [cli, entities, orchestration, milestones]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: []
related: [debt--python-error-handling-and-io-consistency]
---

# Entity Lifecycle CLI and Milestone Synchronization Orchestrator

## Problem
Currently, Along CLI lacks commands to modify existing issues, synchronize milestones bidirectionally, or initiate task workflows:
1. No issue modification: `along issue` only supports `create`, `done`, `sync`, and `list`. Updating an issue's milestone, priority, tags, or status requires manual YAML editing.
2. Milestone fragmentation: There is no `along milestone` command family. Setting an issue's milestone leaves the milestone file (`target_issues`, `progress_pct`, and `status`) unsynchronized.
3. No fuzzy milestone matching: Humans and agents refer to milestones colloquially (e.g. `4.0` or `v4.0`), but the protocol requires the full canonical slug (`v4.0.0-runtime-gates-and-worktree-isolation`).
4. Fragmented workflow starter: Starting work on an issue requires 3 separate manual steps: editing issue status to `in-progress`, running `along scratch init <slug>`, and creating a worktree or branch.

## Requirements
- Implement `along issue update <slug> [--milestone <m>] [--priority <p>] [--status <s>] [--tags <t>] [--title <t>]`:
  - Supports fuzzy milestone resolution (`4.0` -> `v4.0.0-runtime-gates-and-worktree-isolation`).
  - Automatically updates `.along/MILESTONES/*.md` when an issue's milestone is changed.
  - Recompiles `.along/ISSUES.md`.
- Implement `along issue show <slug> [--json]`.
- Implement `along milestone [sync|list|show]`:
  - `along milestone sync [<slug>]`: automatically calculates `target_issues`, `progress_pct`, and updates milestone status.
  - `along milestone list [--status <s>] [--json]`: displays overview of all milestones and progress.
  - `along milestone show <slug> [--json]`: displays details and target issue statuses.
- Implement `along start <slug> [--worktree]`:
  - Sets issue `status: in-progress`.
  - Initializes session blackboard (`.along/.session/<slug>/state.json`).
  - Optionally creates an isolated worktree if `--worktree` is specified.
- Comprehensive hermetic tests in `tests/test_entity_lifecycle_cli.py`.

## Acceptance Criteria
- [ ] `along issue update` updates frontmatter cleanly using `ruamel.yaml` without dropping comments.
- [ ] Milestone fuzzy resolution correctly maps shorthand queries (`4.0`, `v4.0`) to canonical slugs.
- [ ] `along milestone sync` updates `target_issues`, `progress_pct`, and `status` accurately.
- [ ] `along start <slug>` marks issue in-progress and initializes session blackboard.
- [ ] All automated tests pass: `python .along/scripts/test.py`.
