---
protocol: along
protocol_version: "4.4.6"
date: 2026-10-06
slug: runtime-plan-dir-containment
agent: claude-code
branch: main
commit: dec9a6e
summary: Containment allows the Claude Code plan dir ~/.claude/plans
milestone: v4.5.0-multi-user-merge-automation
issues_advanced: []
issues_completed: [bug--runtime-plan-dir-containment]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Runtime plan dir containment

## Summary
Containment allows the Claude Code plan dir ~/.claude/plans

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `docs/topic--declarative-gates-and-traceability.md` | docs | 1 | 2026-10-06T19:30:02Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `scripts/alongkit/hooks/containment.py` | source | 3 | 2026-10-06T19:29:35Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `tests/test_workspace_containment.py` | source | 1 | 2026-10-06T19:29:44Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |

### Plan

#### Living Plan: runtime-plan-dir-containment

##### Revision 1 (2026-10-06T19:29:20Z, plan approve --plan-file)

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

#### Execution Trace: runtime-plan-dir-containment
- 2026-10-06T19:29:20Z plan recorded: revision 1 (plan approve --plan-file)
- 2026-10-06T19:29:20Z plan approved (along plan approve)
- 2026-10-06T19:29:21Z Single-agent fallback: Localized one-module fix; user-approved plan declares Direct mode
- 2026-10-06T19:29:26Z denied [cli_safety] run_command: CLI Safety Gate Violation: Heredoc syntax (<<EOF) detected in command: cd /d/Src/my/actdim/public/along; python - <<'EOF'
- 2026-10-06T19:29:35Z edit scripts/alongkit/hooks/containment.py (x3)
- 2026-10-06T19:29:44Z edit tests/test_workspace_containment.py
- 2026-10-06T19:30:02Z edit docs/topic--declarative-gates-and-traceability.md
- 2026-10-06T19:30:31Z denied [test_before_stop] : Turn Completion Rejected [gate: test-before-stop]: Source files were modified in this session, but automated tests have not been executed afterward. Run test...
