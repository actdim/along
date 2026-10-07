---
protocol: along
protocol_version: "4.4.6"
date: 2026-10-06
slug: update-maintenance-friction
agent: claude-code
branch: main
commit: dec9a6e
summary: Maintenance commands pass the plan gate, doctor --fix not read-only, archived issues warn, migration backups pruned and slimmer
milestone: v4.5.0-multi-user-merge-automation
issues_advanced: []
issues_completed: [bug--update-maintenance-friction]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Update maintenance friction

## Summary
Maintenance commands pass the plan gate, doctor --fix not read-only, archived issues warn, migration backups pruned and slimmer

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/bug--runtime-plan-dir-containment.md` | state | 1 | 2026-10-06T19:40:02Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `.along/ISSUES/bug--update-maintenance-friction.md` | state | 1 | 2026-10-06T19:40:02Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `docs/topic--architecture.md` | docs | 1 | 2026-10-06T19:39:46Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `docs/topic--migrations.md` | docs | 1 | 2026-10-06T19:39:45Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `docs/topic--runtime-hooks-and-gates.md` | docs | 2 | 2026-10-06T19:39:47Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `scripts/alongkit/entities.py` | source | 3 | 2026-10-06T19:34:31Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `scripts/alongkit/hooks/shellparse.py` | source | 5 | 2026-10-06T19:34:08Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `scripts/alongkit/migration.py` | source | 3 | 2026-10-06T19:35:09Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `scripts/alongkit/rules.py` | source | 2 | 2026-10-06T19:35:10Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `tests/test_update_maintenance_friction.py` | source | 1 | 2026-10-06T19:35:44Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |

### Plan

#### Living Plan: update-maintenance-friction

##### Revision 1 (2026-10-06T19:33:49Z, plan approve --plan-file)

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

#### Execution Trace: update-maintenance-friction
- 2026-10-06T19:33:49Z plan recorded: revision 1 (plan approve --plan-file)
- 2026-10-06T19:33:49Z plan approved (along plan approve)
- 2026-10-06T19:33:50Z Single-agent fallback: Localized fixes in shellparse, entities, migration; user-approved plan declares Direct mode
- 2026-10-06T19:34:08Z edit scripts/alongkit/hooks/shellparse.py (x5)
- 2026-10-06T19:34:31Z edit scripts/alongkit/entities.py (x3)
- 2026-10-06T19:35:09Z edit scripts/alongkit/migration.py (x3)
- 2026-10-06T19:35:10Z edit scripts/alongkit/rules.py (x2)
- 2026-10-06T19:35:44Z edit tests/test_update_maintenance_friction.py
- 2026-10-06T19:39:45Z edit docs/topic--migrations.md
- 2026-10-06T19:39:46Z edit docs/topic--architecture.md
- 2026-10-06T19:39:47Z edit docs/topic--runtime-hooks-and-gates.md (x2)
- 2026-10-06T19:40:02Z edit .along/ISSUES/bug--runtime-plan-dir-containment.md
- 2026-10-06T19:40:02Z edit .along/ISSUES/bug--update-maintenance-friction.md
- 2026-10-06T19:44:01Z test pass (Wrap Quality Gate)
