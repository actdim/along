---
protocol: along
protocol_version: "4.8.1"
slug: stop-gate-false-positives
type: bug
status: open
priority: high
created: 2026-11-13
updated: 2026-11-13
agent: claude-code
tags: [gates, hooks, stop, parallel-sessions]
blocked_by: []
related: [debt--stale-protocol-path-comment, feat--trivial-fix-lifecycle]
---

# Stop gate blocks on engine-written projections and other sessions' edits; Stop denials have no ack path

## Problem

Observed 2026-11-13 while closing `debt--stale-protocol-path-comment`. After `along wrap` committed the closeout, the Stop hook refused to end the turn:

```text
PLAN_REQUIRED [gate: require-plan-approval]: this turn changed packages/dashboard-ui/docs/INDEX.md
with no approved plan for this session.
```

The change was a date-only bump (`updated: 2026-11-11` -> `2026-11-13`) that `along wrap`'s KB sync wrote itself. Four defects combine here:

1. **Package-level projection not whitelisted.** `MUTATION_WHITELIST_PATTERNS` (`scripts/alongkit/hooks/predicates.py`) lists `docs/INDEX.md`, matched via `_matches_in_context` against the repo root or the owning subproject context. `packages/dashboard-ui/` has its own `AGENTS.md` and `docs/INDEX.md` but no `.along/`, so it is not a subproject context and its compiled `docs/INDEX.md` counts as a plan-governed source change.
2. **Projection rewritten with no content change.** `along_kb_sync.py` sets `"updated": today` in `index_fm` on every run, so each sync dirties every index even when topics are unchanged; `closeout.PROJECTION_FILES` does not include package-level indexes, so `wrap` leaves them uncommitted.
3. **Turn baseline counts writes the session did not make.** The Stop branch of the plan gate uses `turnstate.changed_since(repo_root, trace["turn_baseline"])`, a whole-tree snapshot diff. Edits made by another session in the same checkout during the turn, or by Along engines invoked from the turn, are attributed to the turn.
4. **Stop denials cannot be acknowledged.** `record_gate_denial` writes a ledger `deny` event only for `PRE_TOOL_USE` ("Stop denials are not tool calls"). After `wrap` unbinds the session, `along gates denials` / `along gates ack` fail with `No gate denials to read: this session is not bound to an issue`, so the agent has no recorded path besides approve-or-revert.

Separately, the protocol says "1-line typo/comment edits are exempt" (`skills/along-init/protocol.md`, `.along/PROTOCOL.md`: "1-line micro-edits ... do not require issues"), but `check_active_issue` and the plan gate implement no such exemption: a one-line comment edit in `scripts/alongkit/budget.py` was denied by both gates.

## Requirements
- REQ-1: The plan gate MUST treat any compiled `docs/INDEX.md`, `llms.txt` and `llms-full.txt` that `along kb-sync` writes (root, subproject or package level) as a projection, not as a plan-governed change.
- REQ-2: `along kb-sync` MUST NOT rewrite an index whose body is unchanged (no date-only bumps).
- REQ-3: `along wrap` MUST commit every projection its own sync changed, including package-level indexes, or leave none dirty.
- REQ-4: The Stop branch of `require-plan-approval` MUST count only paths written by this session's tool calls (or engines it invoked), not changes made by other sessions during the turn.
- REQ-5: A Stop-time denial MUST be recorded so that `along gates denials` and `along gates ack --note` can read and acknowledge it, including after the session was unbound by `wrap`.
- REQ-6: The 1-line exemption MUST either be implemented in `check_active_issue` and the plan gate (single-hunk, <= 1 changed line, comment or typo only) or removed from `skills/along-init/protocol.md` and `.along/PROTOCOL.md`; protocol text and gate behavior MUST agree.

## Acceptance Criteria
- [ ] Regression test: a `wrap` that re-syncs a package-level `docs/INDEX.md` ends with a clean tree and no Stop denial.
- [ ] Regression test: running `along kb-sync` twice leaves the second run with no file changes.
- [ ] Regression test: a file changed by a second session key during the turn does not trigger the Stop plan gate for the first.
- [ ] Regression test: after a Stop denial, `along gates denials` lists it and `along gates ack <id> --note "..."` acknowledges it, bound or not.
- [ ] The 1-line exemption decision is reflected in both the gate and the protocol text, with a test for the chosen behavior.
- [ ] `python .along/scripts/test.py` passes.

## Plan

Execution Mode: Role-Based (core gate engine, kb-sync and closeout; more than 3 files across subsystems -> `along-team`).

1. **Projection recognition (REQ-1).** In `scripts/alongkit/hooks/predicates.py`, add a predicate `_is_compiled_projection(rel, repo_root)` that returns true for `**/docs/INDEX.md`, `**/llms.txt`, `**/llms-full.txt` when the file carries the kb-sync frontmatter (`protocol: along`, `type: index`) or lives next to a `docs/` tree kb-sync manages. Use it in `_is_plan_governed` and in the PreToolUse whitelist branch. Reuse `_matches_in_context` for the context-relative part; do not widen `docs/**` globally.
2. **No-op sync (REQ-2).** In `scripts/along_kb_sync.py`, build the index body first, compare it with the existing file body (ignoring the `updated` field), and keep the old `updated` and skip the write when equal. Same treatment for `llms.txt` / `llms-full.txt` writers.
3. **Wrap commits what it synced (REQ-3).** In `scripts/alongkit/closeout.py`, collect the paths the closeout sync actually wrote (return them from the kb-sync call rather than relying on the static `PROJECTION_FILES` tuple) and stage them in the wrap commit.
4. **Session-attributed Stop diff (REQ-4).** Record written paths per session key in the activity trace (the PostToolUse path already calls `record_tool_activity`; add Bash-produced writes via a pre/post snapshot of the command only). In the Stop branch, intersect `turnstate.changed_since(...)` with the session's recorded writes; paths outside the intersection are reported as a notice, not a denial.
5. **Ackable Stop denials (REQ-5).** In `record_gate_denial`, record Stop denials in the ledger as `deny` events with `kind: stop` (keyed by gate + sorted path list so repeats collapse). In `scripts/alongkit/commands/gates.py` `_denials_target`, fall back to the most recently wrapped issue's blackboard for this session key when unbound (closeout keeps the blackboard path in the activity trace). `check_unresolved_denials` then settles them on ack like tool-call denials.
6. **1-line exemption (REQ-6).** Decide with the user at plan review; default proposal: implement it for Edit tool calls whose `old_string`/`new_string` differ in one line that is a comment or whitespace-only, outside `.along/scripts/` and test files, recorded as an audit entry. Update protocol text only if the user prefers removal.
7. **Tests.** Extend `tests/test_parallel_closeout.py` (wrap + package index), `tests/test_kb_sync.py` (idempotent second run), `tests/test_gate_friction.py` (second session key, 1-line exemption), `tests/test_gates_traceability.py` (Stop denial ack). Keep them hermetic (temp repos).
8. **Docs.** Update the gate description in `docs/topic--*.md` that documents `require-plan-approval` (find via `/along-kb-search require-plan-approval`) and the PROTOCOL gate list if behavior text changes.

Verification: targeted test modules, then the full suite; manual repro in a scratch repo with a package-level `docs/INDEX.md`: `along start` -> one edit -> `along wrap` -> Stop must pass with a clean tree.
