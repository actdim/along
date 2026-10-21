---
protocol: along
protocol_version: "4.4.14"
slug: anti-silent-fallback-gate
type: feat
status: open
priority: high
created: 2026-10-15
updated: 2026-10-15
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

## Acceptance Criteria

- [ ] Gate denials (`decision: deny`) during an active session are appended to `.along/.session/<slug>/gate_denials.jsonl`.
- [ ] `along issue done` and `along wrap` verify `.along/.session/<slug>/gate_denials.jsonl` and block execution if unresolved denials exist.
- [ ] Added `--bypass-denial "<reason>"` flag to `along issue done` and `along wrap` to record explicit human acknowledgement.
- [ ] Added declarative `unresolved_gate_denial` gate on `Stop` event in `default_gates.yaml`.
- [ ] Hermetic tests verify denial logging, closeout blocking, stop-gate triggering, and resolution via retry or explicit bypass.
- [ ] Clean ASCII check (`along sanitize`) passes and tests pass with zero failures.

