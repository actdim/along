# Plan: debt--gate-config-layers

Execution Mode: Role-Based (spans hook engine config, default gates catalogue, CLI commands, and test suites)

## Context
`alongkit/hooks/config.py` resolves gate modes from five complex, overlapping layers:
1. `GATE_TIERS` (invariant vs advisory)
2. `STATE_LAYER_GATES`
3. Profile matrix (`strict`/`standard`/`light`/`autonomous`)
4. `DEFAULT_GATE_MODES`
5. Global mode `ALONG_HOOK_MODE` and `.along/config.json` `hooks.gates`

Currently, 35 gates exist in `default_gates.yaml`, many of which belong at commit time (in git hooks and CI) rather than agent PreToolUse interception.

## Target Architecture (3 Layers)
1. **Layer 1: Catalogue Default**: Base mode declared per gate in `default_gates.yaml` (`block`, `warn`, `ask`).
2. **Layer 2: Repository Override**: Configured in `.along/rules/gates.yaml` or `.along/config.json`.
3. **Layer 3: Runtime Execution Profile**: `interactive` vs `autonomous` (autonomous mode automatically adapts `ask` into `block` and prohibits unconfirmed actions).

## Phased Implementation

### Phase 1: Mode Resolution Refactoring
- Simplify `get_gate_mode(gate_name)` in `scripts/alongkit/hooks/config.py`:
  - Evaluate repository override first.
  - Fall back to catalogue default.
  - Apply autonomous mode transformation if runtime is autonomous.
- Remove redundant `GATE_TIERS` and hardcoded `STATE_LAYER_GATES` dictionaries.

### Phase 2: Runtime Gate Budget Reduction (~12 Gates)
- Audit all 35 gates in `scripts/alongkit/hooks/default_gates.yaml`.
- Segregate commit-time gates (git hooks + CI only):
  - `commit_issue_binding`, `commit_no_conflict_markers`, `commit_no_ai_coauthor`
  - `anti_stub_injection`, `typography`, `code_fence_language`, `windows_safe_filenames`
  - `portable_links`, `no_tracked_secrets`, `session_record_append_only`, `provenance_drift`, `doc_routing_compliance`
- Retain only the ~12 core runtime interception gates:
  - `destructive_command`, `workspace_containment`, `subproject_boundary`
  - `require_active_issue`, `require_plan_approval`, `projection_protection`, `rule_pack_protection`, `doc_manual_lock`
  - `test_before_stop`, `wrap_before_stop`, `unresolved_gate_denial`, `team_step_active`

### Phase 3: CLI Introspection and Observability
- Add/update `along gates explain <gate_name>` to print the effective mode and the layer that determined it (`catalogue`, `repo_override`, `runtime_profile`).
- Update `along doctor` and `along hook verify` to report runtime vs commit-time gate boundaries cleanly.

### Phase 4: Test Suite Updates and Verification
- Update `tests/test_runtime_hooks.py`, `tests/test_autonomous_gate_profile.py`, and `tests/test_hook_config.py` to match the 3-layer resolution contract.
- Run `along hook verify` and verify clean bi-directional traceability.
- Run `python .along/scripts/test.py` to confirm zero test regressions.
