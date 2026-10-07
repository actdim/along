---
protocol: along
protocol_version: "4.4.6"
date: 2026-10-06
slug: subproject-model-overdetection
agent: claude-code
branch: main
commit: dec9a6e
summary: 'Subproject boundary is a nested .git or explicit init: no manifest-driven installs, doctor reports nested ones, context-relative gate excludes, sibling refs, bound issue scope honoured'
milestone: v4.5.0-multi-user-merge-automation
issues_advanced: []
issues_completed: [bug--subproject-model-overdetection]
decisions: [ADR-2026-10-06--subproject-boundary-is-git-or-explicit-init]
risks_logged: []
spikes_conducted: []
---

# Session: Subproject model overdetection

## Summary
Subproject boundary is a nested .git or explicit init: no manifest-driven installs, doctor reports nested ones, context-relative gate excludes, sibling refs, bound issue scope honoured

## Decisions
- [ADR-2026-10-06--subproject-boundary-is-git-or-explicit-init]

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/bug--subproject-model-overdetection.md` | state | 1 | 2026-10-06T19:58:59Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `AGENTS.md` | docs | 4 | 2026-10-06T19:53:52Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `docs/topic--cli-reference.md` | docs | 3 | 2026-10-06T19:58:38Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `docs/topic--declarative-gates-and-traceability.md` | docs | 3 | 2026-10-06T19:58:40Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `docs/topic--runtime-hooks-and-gates.md` | docs | 2 | 2026-10-06T19:58:46Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `scripts/along_exec.py` | source | 1 | 2026-10-06T19:47:22Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `scripts/along_history_sync.py` | source | 1 | 2026-10-06T19:48:00Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `scripts/along_update.py` | source | 2 | 2026-10-06T19:45:29Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `scripts/alongkit/entities.py` | source | 4 | 2026-10-06T19:46:57Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `scripts/alongkit/hooks/containment.py` | source | 2 | 2026-10-06T19:46:14Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `scripts/alongkit/hooks/predicates.py` | source | 6 | 2026-10-06T19:46:39Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `scripts/alongkit/repo.py` | source | 3 | 2026-10-06T19:47:54Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `skills/along-init/protocol.md` | source | 4 | 2026-10-06T19:53:51Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `tests/test_skills_and_scripts.py` | source | 2 | 2026-10-06T19:53:58Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `tests/test_subproject_model.py` | source | 2 | 2026-10-06T19:49:36Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `tests/test_workspace_containment.py` | source | 2 | 2026-10-06T19:54:06Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |

### Plan

#### Living Plan: subproject-model-overdetection

##### Revision 1 (2026-10-06T19:44:25Z, plan approve --plan-file)

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

#### Execution Trace: subproject-model-overdetection
- 2026-10-06T19:44:25Z plan recorded: revision 1 (plan approve --plan-file)
- 2026-10-06T19:44:25Z plan approved (along plan approve)
- 2026-10-06T19:44:25Z Single-agent fallback: Bounded changes per module with hermetic tests; user-approved plan declares Direct mode
- 2026-10-06T19:44:49Z edit skills/along-init/protocol.md (x2)
- 2026-10-06T19:44:51Z edit AGENTS.md (x2)
- 2026-10-06T19:45:18Z edit scripts/alongkit/repo.py
- 2026-10-06T19:45:29Z edit scripts/along_update.py (x2)
- 2026-10-06T19:45:45Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-06T19:46:14Z edit scripts/alongkit/hooks/containment.py (x2)
- 2026-10-06T19:46:39Z edit scripts/alongkit/hooks/predicates.py (x5)
- 2026-10-06T19:46:57Z edit scripts/alongkit/entities.py (x4)
- 2026-10-06T19:47:21Z edit scripts/alongkit/repo.py
- 2026-10-06T19:47:22Z edit scripts/along_exec.py
- 2026-10-06T19:47:54Z edit scripts/alongkit/repo.py
- 2026-10-06T19:48:00Z edit scripts/along_history_sync.py
- 2026-10-06T19:48:34Z edit tests/test_skills_and_scripts.py
- 2026-10-06T19:49:36Z edit tests/test_subproject_model.py (x2)
- 2026-10-06T19:53:51Z edit skills/along-init/protocol.md (x2)
- 2026-10-06T19:53:52Z edit AGENTS.md (x2)
- 2026-10-06T19:53:58Z edit tests/test_skills_and_scripts.py
- 2026-10-06T19:54:06Z edit tests/test_workspace_containment.py (x2)
- 2026-10-06T19:58:38Z edit docs/topic--cli-reference.md (x3)
- 2026-10-06T19:58:40Z edit docs/topic--declarative-gates-and-traceability.md (x3)
- 2026-10-06T19:58:46Z edit docs/topic--runtime-hooks-and-gates.md (x2)
- 2026-10-06T19:58:59Z edit .along/ISSUES/bug--subproject-model-overdetection.md
- 2026-10-06T20:02:55Z test pass (Wrap Quality Gate)
