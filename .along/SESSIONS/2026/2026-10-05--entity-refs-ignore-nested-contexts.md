---
protocol: along
protocol_version: "4.4.5"
date: 2026-10-05
slug: entity-refs-ignore-nested-contexts
agent: claude-code
branch: main
commit: 26aad03
summary: 'Entity graph in monorepos: downward references to nested .along contexts resolve, gates block only problems absent at HEAD, migration stops inventing milestones (doctor --entities --fix drops dangling ones), unconfigured test hook warns instead of passing, wrap empty-file audit scoped to truncations and session edits'
issues_advanced: []
issues_completed: [bug--entity-refs-ignore-nested-contexts, bug--entity-gate-blocks-preexisting-problems, bug--migration-dangling-template-milestones, bug--unconfigured-test-hook-reports-pass, bug--wrap-zero-byte-audit-unscoped]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Entity graph integrity in monorepos

## Summary
- `bug--entity-refs-ignore-nested-contexts`: `entities.descendant_entity_keys` collects keys of
  every nested `.along/` (skipping `repo.IGNORED_DIRS`, hidden dirs and nested git
  repositories); `validate_entities(..., descendants=True)` merges them, so root epics and root
  session logs may reference subproject issues. This also unblocks migration Step 6, whose
  failure kept the migration state marker unwritten and re-ran the chain on every update.
- `bug--entity-gate-blocks-preexisting-problems`: `gitgates.baseline_entity_problems` validates a
  `git archive` snapshot of every `.along/` entity dir at `HEAD`;
  `gates.split_entity_integrity_errors` splits problems into new / pre-existing. The Stop
  predicate, `along wrap` and `along issue sync` block only new problems and print the rest as
  a warning.
- `bug--migration-dangling-template-milestones`: migration no longer synthesizes milestones from
  Along's own history nor assigns `milestone` to issues and session logs;
  `_v1_5_drop_unresolved_template_milestones` removes the two template references when their
  milestone file is missing (idempotent). `along doctor --entities --fix`
  (`entities.drop_dangling_milestones`) removes any dangling `milestone` field.
- `bug--unconfigured-test-hook-reports-pass`: the unconfigured lifecycle template warns on stderr
  that nothing was verified; `gates.run_repository_tests` reports "tests are not configured"
  instead of a pass; `along test` prints the state as `[Warning]`.
- `bug--wrap-zero-byte-audit-unscoped`: the wrap audit blocks only on a tracked file truncated to
  0 bytes or an empty file recorded in the activity traces; other empty files warn. Porcelain
  paths now resolve against the git top (the old parser also lost the first character of the
  first status line through `Result.out` stripping).
- Earlier session artifacts were reworded to drop a real project name and paths.
- Docs: `docs/topic--cli-reference.md`, `docs/topic--runtime-hooks-and-gates.md`,
  `docs/topic--declarative-gates-and-traceability.md`, `skills/along-wrap/SKILL.md`.
- Tests: 922 pass under the repo `.venv`. With the global `along` interpreter 5 tests fail for
  environment reasons only (missing `pydantic`, installer manifest tests), as on clean HEAD.

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.
