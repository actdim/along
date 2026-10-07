---
protocol: along
protocol_version: "4.4.6"
slug: cli-entity-sync-defects
type: bug
status: done
completed: 2026-10-06
priority: medium
created: 2026-10-06
updated: 2026-10-06
agent: claude-code
tags: [cli, entities, milestones, sessions]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--subcommand-help-as-argument]
---

# milestone sync rewrites completed milestones; session create scaffold misfiles issues and misses test runs; no issue cancel/delete; help-fix leftovers

Field report (2026-10-06), verified against the code:

1. `entities.sync_milestones` recomputes `target_issues` from the issues' `milestone:` field
   only and rewrites every milestone, completed ones included: explicit entries without a
   matching field are dropped and a `completed` status can flip back. `issue rename` and
   `issue supersede` call it for all milestones too.
2. `along session create <slug> --issues ...` writes every issue into `issues_completed` whatever
   its status, keeps the "Document key tasks and achievements." placeholder, and its Tests line
   reads only the hook activity trace of the current scope: an `along test` run
   (`diagnostics/test_runs.json`, session ledger) is not seen.
3. No `along issue cancel` / `along issue delete`: removing a mistaken issue file leaves a
   dangling `target_issues` reference until `milestone sync` (the cancel path exists only as
   `issue done --status cancelled`).
4. Leftovers of [bug--subcommand-help-as-argument]: `session create -x` still creates an empty
   `SESSIONS/<year>/` before validating the name; `session wrap` does not validate its slug;
   `issue create -x` exits 1 instead of 2.

## Requirements
- REQ-1: `sync_milestones` leaves `completed` milestones alone unless named explicitly, and
  never drops an explicit `target_issues` entry that still resolves to an issue.
- REQ-2: `session create` files closed issues under `issues_completed` and the rest under
  `issues_advanced` (canonical keys), and takes test evidence from the recorded test runs too.
- REQ-3: `along issue cancel <slug>` closes as `cancelled`. `along issue delete <slug>` removes an
  issue no session log references, strips it from milestone `target_issues` and issue
  reference fields, and recompiles the board.
- REQ-4: Help-fix leftovers fixed (no directory before validation, `session wrap` validates,
  `issue create` exits 2 on a flag-like slug).

## Acceptance Criteria
- [x] REQ-1..REQ-4 covered by hermetic tests
- [x] Automated tests passing

## Resolution
- REQ-1: `entities.sync_milestones` skips `completed` milestones unless named, and keeps an
  explicit `target_issues` entry while its issue exists and names no other milestone (so
  `issue update` moving an issue still removes it from the old milestone; a deleted issue drops out).
- REQ-2: `_render_session_log` files issues by status (canonical keys), `_work_completed_lines`
  replaces the placeholder, `_tests_evidence_line` accepts a green `along test` run of the
  current tree (`testruns.green_run_for`) in this or an enclosing context.
- REQ-3: `along issue cancel`; `along issue delete` (`entities.delete_issue`): strips list
  references, refuses on session logs, `parent` / `superseded_by` / `duplicate_of` and commits.
- REQ-4: `session create` creates `SESSIONS/<year>/` after validation; `session wrap`,
  `issue create`, `issue done|cancel|delete` exit 2 on a flag-like name.
- Tests: `tests/test_cli_entity_sync.py`, `tests/test_subcommand_help.py`. Docs:
  `topic--cli-reference`.
