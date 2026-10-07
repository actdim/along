---
protocol: along
protocol_version: "4.4.6"
date: 2026-10-06
slug: cli-entity-sync-defects
agent: claude-code
branch: main
commit: dec9a6e
summary: milestone sync keeps completed milestones and explicit lists; session create files issues by status with real evidence; issue cancel/delete; help-fix leftovers
milestone: v4.5.0-multi-user-merge-automation
issues_advanced: []
issues_completed: [bug--cli-entity-sync-defects]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Cli entity sync defects

## Summary
milestone sync keeps completed milestones and explicit lists; session create files issues by status with real evidence; issue cancel/delete; help-fix leftovers

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/bug--cli-entity-sync-defects.md` | state | 1 | 2026-10-06T20:15:14Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `docs/topic--cli-reference.md` | docs | 3 | 2026-10-06T20:15:03Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `scripts/along_exec.py` | source | 13 | 2026-10-06T20:05:52Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `scripts/alongkit/entities.py` | source | 2 | 2026-10-06T20:05:11Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `tests/test_cli_entity_sync.py` | source | 3 | 2026-10-06T20:10:44Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `tests/test_subcommand_help.py` | source | 2 | 2026-10-06T20:05:51Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |

### Plan

#### Living Plan: cli-entity-sync-defects

##### Revision 1 (2026-10-06T20:03:04Z, plan approve --plan-file)

#### Plan: fix field defects A-E (v4.5.0) - approved by the user via ExitPlanMode on 2026-10-06

Issues: E bug--runtime-plan-dir-containment, C bug--update-maintenance-friction,
A bug--subproject-model-overdetection, D bug--cli-entity-sync-defects,
B bug--lifecycle-test-false-pass. ADR-2026-10-06--subproject-boundary-is-git-or-explicit-init.

Order E -> C -> A -> D -> B, one issue at a time: bind, fix, hermetic tests, docs, wrap, done.

- E: containment write roots += ~/.claude/plans.
- C: maintenance subcommands pass the plan gate (uninstall excluded); doctor --fix not read-only;
  archived-issue schema findings are warnings (dangling issue refs stay errors); migration backup
  retention, skip machine-local state, shared .gitignore helper.
- A: protocol rule reworded; manifest discovery honours monorepo root markers; update hint;
  subproject-boundary package.json branch dropped; doctor nested-install warning + intentional flag;
  no fresh nested .along from history-sync / lifecycle synthesis; context-relative gate excludes;
  sibling entity keys; require-active-issue honours write_scope/allowed_roots; containment reads
  the bound subproject issue scope. No automatic migration of existing nested installs.
- D: sync_milestones freezes completed milestones and keeps explicit target_issues; session create
  status-based issue lists + test evidence from test runs; issue cancel / issue delete; help-fix leftovers.
- B: zero-tests is not a pass; dotnet detection needs sln/test project; parent hook fallback;
  is_source_edit ignores *.md and docs/**.

Execution Mode: Direct per issue (localized fixes; recorded with along scratch fallback).

### Execution Trace

#### Execution Trace: cli-entity-sync-defects
- 2026-10-06T20:03:04Z plan recorded: revision 1 (plan approve --plan-file)
- 2026-10-06T20:03:04Z plan approved (along plan approve)
- 2026-10-06T20:03:05Z Single-agent fallback: Localized CLI and entity fixes; user-approved plan declares Direct mode
- 2026-10-06T20:03:24Z edit scripts/alongkit/entities.py
- 2026-10-06T20:04:36Z edit scripts/along_exec.py (x8)
- 2026-10-06T20:05:11Z edit scripts/alongkit/entities.py
- 2026-10-06T20:05:30Z edit scripts/along_exec.py (x4)
- 2026-10-06T20:05:51Z edit tests/test_subcommand_help.py (x2)
- 2026-10-06T20:05:52Z edit scripts/along_exec.py
- 2026-10-06T20:10:44Z edit tests/test_cli_entity_sync.py (x3)
- 2026-10-06T20:15:03Z edit docs/topic--cli-reference.md (x3)
- 2026-10-06T20:15:14Z edit .along/ISSUES/bug--cli-entity-sync-defects.md
- 2026-10-06T20:19:11Z test pass (Wrap Quality Gate)
