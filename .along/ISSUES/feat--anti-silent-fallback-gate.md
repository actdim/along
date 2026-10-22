---
protocol: along
protocol_version: "4.4.14"
slug: anti-silent-fallback-gate
type: feat
status: in-progress
priority: high
created: 2026-10-15
updated: 2026-10-23
agent: antigravity
tags: [gates, lifecycle, safety, blackboard]
milestone: v4.5.2-anti-silent-fallback-gate
blocked_by: []
related: []
---

# Block Turn Completion and Issue Closeout on Unresolved Gate Denials

## Problem Statement

Along enforces strict mechanical boundaries via pre-tool gates (`PreToolUse`), such as `subproject_boundary`, `require_active_issue`, and `doc_manual_lock`. When a gate triggers, the tool call is denied with `decision: deny`.

However, there is an architectural gap in lifecycle verification: Along does not verify whether denied operations were resolved or acknowledged before turn termination (`Stop`) or issue closeout (`along issue done` / `along wrap`).

As a result, LLM agents frequently exhibit silent fallback behavior: when a tool call is blocked by a gate, the model quietly abandons the blocked sub-task, pivots to an alternative file or partial workaround, runs `along issue done`, and reports 100% success to the user without disclosing the failure.

## Requirements

1. **Gate Denial Journaling in Session Blackboard**:
   - Whenever `along_hook.py` (or any gate adapter) produces `decision: deny` during an active session, append an incident entry to `.along/.session/<slug>/gate_denials.jsonl`.
   - Record timestamp, gate id, tool name, target file/command, error message, and `resolved: false`.

2. **Reconciliation Lifecycle**:
   - Transition denial entry to `resolved: true` when the blocked action is subsequently re-attempted and succeeds under valid gate conditions.
   - Support explicit human disclosure/acknowledgment via CLI:
     - `along issue done <slug> --bypass-denial "<reason>"`
     - Or structured entry in session state via `along scratch patch`.

3. **Mechanical Closeout Gate (`along issue done` / `along wrap`)**:
   - Before moving an issue to `.along/ISSUES/done/` or writing the final session log, scan `.along/.session/<slug>/gate_denials.jsonl`.
   - If any denial remains `resolved: false`, refuse command execution with a non-zero exit code.
   - Output an actionable error message explaining the denial and providing instructions on how to resolve or explicitly bypass.

4. **Turn-Termination Gate on `Stop` Event (`unresolved_gate_denial`)**:
   - Add a declarative gate in `default_gates.yaml` (profiles: `strict: block`, `standard: block`, `light: warn`).
   - Handler `alongkit.hooks.predicates.check_unresolved_denials` checks for unresolved denials incurred during the current turn.
   - Reject turn completion if unacknowledged pre-tool denials occurred during the turn.

## Design Change (approved plan, 2026-10-22)

Built on existing machinery instead of a new journal and flag ([ADR-2026-10-23--gate-denials-are-ledger-events]):
- Denials are `deny` events in the issue's event ledger (`.along/.session/<slug>/events.jsonl`), settled by `resolve` (retry on the same target, or a later `approve` for `denial: procedural` gates) or disclosed by `ack` (`along gates ack --note`), verified once the user replied after it.
- The explicit override is the existing `--force-reason` under `bypass.guard(wrap-checks)` (a reason, the refusal first, the user's reply after it), now also on `along issue done`, instead of a new `--bypass-denial` flag.

## Acceptance Criteria

- [x] Enforced gate denials of a bound session's tool calls are recorded as `deny` events in `.along/.session/<slug>/events.jsonl` (gate, tool, redacted target, reason, id).
- [x] `along issue done` and `along wrap` (delivered statuses) and closeout readiness refuse while denials are open or acknowledged without a user reply since.
- [x] Explicit human override: `--force-reason "<reason>"` on `along wrap` and `along issue done` under the bypass rules; disclosure via `along gates ack <id> --note "..."`; listing via `along gates denials`.
- [x] Added declarative `unresolved_gate_denial` gate on `Stop` event in `default_gates.yaml` (strict/standard block, light warn).
- [x] Hermetic tests (`tests/test_anti_silent_fallback.py`) verify denial logging, retry and approval resolution, stop-gate triggering and release by ack, closeout blocking, and the `--force-reason` path.
- [x] Clean ASCII check (`along sanitize`) passes and tests pass with zero failures.

