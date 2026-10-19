---
protocol: along
protocol_version: "4.5.0"
date: 2026-10-19
slug: wrap-misses-engine-writes
agent: claude-code
branch: main
commit: d951ead
summary: Wrap and session close commit engine-refreshed files (docs/topic--along-protocol.md, AGENTS.md changed only inside managed blocks); migration Step 15 removes retired circuit-breaker and tool-classifier artifacts with backup
issues_advanced: []
issues_completed: [bug--wrap-misses-engine-writes]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Wrap misses engine writes

## Summary
Wrap and session close commit engine-refreshed files (docs/topic--along-protocol.md, AGENTS.md changed only inside managed blocks); migration Step 15 removes retired circuit-breaker and tool-classifier artifacts with backup

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/bug--wrap-misses-engine-writes.md` | state | 1 | 2026-10-19T15:26:52Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `docs/topic--cli-reference.md` | docs | 1 | 2026-10-19T15:15:30Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `docs/topic--migrations.md` | docs | 1 | 2026-10-19T15:15:29Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `docs/topic--session-lifecycle.md` | docs | 1 | 2026-10-19T15:15:29Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `scripts/alongkit/closeout.py` | source | 2 | 2026-10-19T15:14:03Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `scripts/alongkit/lifecycle.py` | source | 1 | 2026-10-19T15:14:04Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `scripts/migrate_protocol.py` | source | 3 | 2026-10-19T15:14:32Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |
| `tests/test_wrap_engine_writes.py` | source | 1 | 2026-10-19T15:15:11Z | claude--0e35f0d2-5afb-45a1-8219-c9d84f9259e2 |

### Plan

#### bug--wrap-misses-engine-writes

##### Context
Two problems came out of yesterday's work.

1. `along wrap` auto-commits only the files that have edit events (the hook records these for agent file tools) plus `closeout.PROJECTION_FILES`. Files the engine itself rewrites are left out: the `AGENTS.md` managed block and `docs/topic--along-protocol.md`, written by `along init` / `along update`. Because of this, commit 856249a broke its own tests.
2. `debt--gate-simplification` removed the circuit breaker and the tool-nature classifier, but no migration step deletes what they left on disk. Your repo still has `.along/diagnostics/circuit_breaker.json`. Other leftovers are possible: `syntax_churn.json`, `.along/tool_rules.yaml`, and a `tools:` section in `gates.yaml`, which the loader now silently ignores.

`activity_trace.json` and `activity/` stay: the per-session trace is still used, and the shared file is the fallback when there is no session key.

Execution Mode: Direct (3 code files plus tests and docs).

##### Changes
1. **`scripts/alongkit/closeout.py`**:
   - Add `"docs/topic--along-protocol.md"` to `PROJECTION_FILES`. The file is fully managed, and `closeout`'s session-close plan picks it up automatically.
   - New function `managed_only_agents_changes(repo_root, changes) -> List[str]`. It returns every dirty `AGENTS.md` (root or nested) that differs from `HEAD` only inside the managed blocks.
     - Comparison: strip `scaffold.MANAGED_BLOCK_RE` and the `<!-- BEGIN/END ALONG-RULES -->` block from both the `HEAD` copy (`git show HEAD:<path>`) and the working copy, then compare. Line endings are normalized.
     - A file that is new (not in `HEAD`) does not count.
2. **`scripts/alongkit/lifecycle.py` `_auto_commit_wrapped_work`**: add the result of `managed_only_agents_changes` to `commit_paths`. Also use it in the projections group of the `closeout` plan (`along session close`), so both commit paths behave the same.
3. **`scripts/migrate_protocol.py` Step 15 [v4.5.1]** `step_remove_retired_gate_artifacts`:
   - `mig.discard` (with backup) `.along/diagnostics/circuit_breaker.json`, `.along/diagnostics/syntax_churn.json` and `.along/tool_rules.yaml`.
   - If `.along/rules/gates.yaml` has a top-level `tools:` key, only a warning and a `mig.record`; the repo-owned file is not rewritten.
   - Runs on every migration (like Step 14); a repeat run is a no-op.
4. **Tests** (hermetic):
   - `tests/test_closeout*` or `test_wrap*` (next to the existing auto-commit tests): a managed-only `AGENTS.md` change plus `topic--along-protocol.md` go into the commit; an edit in Project specifics keeps `AGENTS.md` out.
   - `tests/test_migration.py`: Step 15 discards with backup, reports `tools:`, and a second run changes nothing.
5. **Docs**:
   - `docs/topic--migrations.md`: section `v4.5.1: Retired Gate Artifacts (Step 15)`.
   - The wrap/closeout doc (`docs/topic--session-lifecycle.md` or `parallel-sessions`): the rule for managed files.

##### Verification
- `python .along/scripts/test.py -q`: all green.
- Live: `python scripts/migrate_protocol.py . --dry-run` shows `circuit_breaker.json` would be removed; then `--apply` removes it and a backup appears.
- `along wrap` on this issue: the commit contains everything without manual follow-ups.

### Execution Trace

#### Execution Trace: wrap-misses-engine-writes
- 2026-10-19T15:13:37Z phase: planning -> execution
- 2026-10-19T15:13:37Z plan approved (ExitPlanMode) approved_via: exit-plan-mode
- 2026-10-19T15:14:03Z edit scripts/alongkit/closeout.py (x2)
- 2026-10-19T15:14:04Z edit scripts/alongkit/lifecycle.py
- 2026-10-19T15:14:32Z edit scripts/migrate_protocol.py (x3)
- 2026-10-19T15:15:11Z edit tests/test_wrap_engine_writes.py
- 2026-10-19T15:15:29Z edit docs/topic--migrations.md
- 2026-10-19T15:15:29Z edit docs/topic--session-lifecycle.md
- 2026-10-19T15:15:30Z edit docs/topic--cli-reference.md
- 2026-10-19T15:26:52Z edit .along/ISSUES/bug--wrap-misses-engine-writes.md
