---
protocol: along
protocol_version: "3.6.0"
slug: entity-lifecycle-cli-documentation
type: docs
status: done
completed: 2026-09-22
priority: medium
created: 2026-09-18
updated: 2026-09-22
agent: antigravity
tags: [documentation, cli, milestones, workflow, kb]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: []
related: [feat--entity-lifecycle-cli-orchestration]
---

# Document Entity Lifecycle CLI and Milestone Synchronization Commands

## Problem
The core documentation suite (`docs/`, `README.md`) does not document the new CLI subcommands and automated synchronization mechanisms introduced in `feat--entity-lifecycle-cli-orchestration`:
1. `docs/topic--cli-reference.md`:
   - Missing `along start <slug> [--worktree]` command definition, options, and workflow behavior.
   - Missing `along issue update <slug> [--milestone <m>] [--priority <p>] [--status <s>] [--tags <t>] [--title <t>]` and its automatic fuzzy milestone matching and projection compilation.
   - Missing `along issue show <slug> [--json]`.
   - Missing entire `along milestone` command section (`along milestone sync [<slug>]`, `along milestone list [--status <s>] [--json]`, `along milestone show <slug> [--json]`).
2. `docs/topic--domain-model.md`:
   - Does not describe bidirectional milestone synchronization, automated `progress_pct` calculation, and dynamic `target_issues` discovery.
3. `docs/topic--setup-and-workflow.md`:
   - Prescribes obsolete manual steps (manually changing issue status to `in-progress` and running separate session init) instead of the atomic `along start <slug> [--worktree]` entry point.
4. `README.md`:
   - Omit `along start` and `along milestone` from the CLI summary tables and usage examples.

## Requirements
- Update `docs/topic--cli-reference.md`:
  - Add `along start` in Project Lifecycle / Entity Management section.
  - Add `update` and `show` subcommands under `### along issue`.
  - Add new section `### along milestone` covering `sync`, `list`, and `show`.
- Update `docs/topic--domain-model.md`:
  - Detail automated calculation of `progress_pct`, `target_issues`, and the role of `along milestone sync`.
- Update `docs/topic--setup-and-workflow.md`:
  - Document `along start <slug>` in the standard task execution workflow.
- Update `README.md`:
  - Add `along start` and `along milestone` to command reference tables.
- Run Knowledge Base synchronization:
  - Verify link integrity and update source hashes via `along kb-sync`.

## Acceptance Criteria
- [ ] `docs/topic--cli-reference.md` documents `along start`, `along issue update`, `along issue show`, and `along milestone [sync|list|show]`.
- [ ] `docs/topic--domain-model.md` and `docs/topic--setup-and-workflow.md` accurately reflect atomic task start and automated milestone synchronization.
- [ ] `README.md` includes new subcommands.
- [ ] `python scripts/along_kb_sync.py --check` passes cleanly.
