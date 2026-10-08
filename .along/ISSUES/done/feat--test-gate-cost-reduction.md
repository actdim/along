---
protocol: along
protocol_version: "4.4.6"
slug: test-gate-cost-reduction
type: feat
status: done
completed: 2026-10-08
priority: high
created: 2026-10-07
updated: 2026-10-08
agent: claude
tags: [gates, tests, performance]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [feat--parallel-session-closeout, bug--lifecycle-test-false-pass, feat--gate-strictness-profiles, bug--inquiry-readonly-commands-blocked]
---

# Test gate cost reduction

## Problem

The full suite (58 files, about 967 tests, one sequential `unittest discover`) takes about
127 s on Windows (measured 2026-10-06). The protocol asks for it far more often than the
tree changes:

| Trigger | Where | When |
| :--- | :--- | :--- |
| Stop gate `test_before_stop` | `alongkit/hooks/predicates.py` `check_test_before_stop` | end of EVERY agent turn after any counted edit |
| `along commit` | `along_commit.py` -> `gates.run_repository_tests` | every commit |
| `along wrap` | `lifecycle.py` -> `gates.run_repository_tests` | every wrap |
| `along version bump` | `along_version_bump.py` | release (justified) |
| Checklist step 1 in `AGENTS.md` | prose | agents also run it by hand |

`feat--parallel-session-closeout` REQ-8 added `alongkit.testruns` (working-tree hash,
green run reuse), but only `gates.run_repository_tests` (commit, wrap, closeout) consults
it. `check_test_before_stop` still compares `last_edit_time` with `last_test_time` only,
so a one-line edit blocks the turn end until the whole suite runs again, even when the
tree hash matches a green run.

`bug--lifecycle-test-false-pass` REQ-4 split doc edits out (`is_doc_edit`), but this
repository sets `count_docs: true` in `.along/rules/gates.yaml` (its suite tests Markdown
budgets and manifests), so a typo in `docs/` still costs a full run here.
`enforce_unbound: true` holds unbound sessions to the same gate.

Long runs on Windows also widen the window for file locks and collisions between parallel
sessions.

## Requirements

- REQ-1: `check_test_before_stop` passes when `testruns.green_run_for(repo_root, tree_hash)`
  finds a green run on the current working tree, whichever source recorded it (agent run,
  commit, wrap, closeout). Time comparison stays as the fallback when no tree hash is
  available.
- REQ-2: Doc-only edits under `count_docs: true` are satisfied by a scoped run of the
  Markdown-facing tests (declared set, e.g. a gate option `doc_tests: [...]`) instead of
  the full suite; the full suite still runs at commit / wrap / release.
- REQ-3: Suite speed: report the slowest tests (per-test timing in the lifecycle hook,
  quiet mode), and evaluate parallel execution (per-module processes) for the hermetic
  suite. Decide via a spike if the gain is unclear.
- REQ-4: Coordinate with `feat--gate-strictness-profiles` REQ-2: `test_before_stop` stays
  on in every profile, but its cost must not scale with turn count.
- REQ-6: Version-only and state-only changes keep a green run. After `along bump` (version
  strings only) `along wrap` ran the full suite again (218 s, 2026-10-07) because the tree
  hash changed. The release engine records its own green run for the post-bump tree (it ran
  the gate on the pre-bump tree inside the same transaction), and `.along/` state / projection
  changes stay out of the hash (as `feat--parallel-session-closeout` REQ-8 intends for closeout).
- REQ-5: Docs: `docs/topic--runtime-hooks-and-gates.md` describes tree-hash reuse for the
  Stop gate and the doc test scope.

## Acceptance Criteria
- [ ] Stop gate accepts a green run on the same tree hash (hermetic tests: edit, run, edit back, stop passes; edit after run, stop blocks)
- [ ] Doc-only edits with `count_docs: true` need only the declared doc tests
- [ ] Slowest-test report available; parallel execution evaluated
- [ ] Docs updated
- [ ] Automated tests passing
