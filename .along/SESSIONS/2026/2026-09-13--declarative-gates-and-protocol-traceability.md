---
protocol: along
slug: declarative-gates-and-protocol-traceability
date: 2026-09-13
agent: antigravity
summary: "Implemented Declarative Gate Engine, 11 canonical protocol gates, stateful predicates, bi-directional traceability scanner, CLI verify command, hermetic test suite, and KB documentation"
milestone: v4.0.0-runtime-gates-and-worktree-isolation
issues_advanced: []
issues_completed: [feat--declarative-gates-and-protocol-traceability]
decisions: [ADR-2026-09-13--declarative-gate-engine-and-traceability]
risks_logged: []
spikes_conducted: []
branch: main
commit: unknown
---

# Session Log: 2026-09-13 - Declarative Gate Engine & Bi-Directional Protocol Traceability

## 1. Objectives & Context

Implementation of `[feat--declarative-gates-and-protocol-traceability]` under milestone `v4.0.0-runtime-gates-and-worktree-isolation`:
- Transition from hardcoded Python gates to an extensible, metadata-driven Declarative Gate Engine.
- Implement the catalogue of 11 core protocol invariant gates in `scripts/alongkit/hooks/default_gates.yaml` and support repo overrides in `.along/rules/gates.yaml`.
- Implement stateful predicate handlers in `scripts/alongkit/hooks/predicates.py` with session activity tracking (`load_activity_trace`, `record_tool_activity`).
- Establish bi-directional machine-checked traceability (`traceability.py`) between prose documentation (`AGENTS.md`, `skills/*/SKILL.md`) via visible `[gate: <id>]` badges and machine-executable YAML rules.
- Add `along hook verify` CLI command.
- Ensure all 17 CLI scripts in `scripts/*.py` reliably call `bootstrap.ensure_deps()`.
- Author architectural documentation in `docs/topic--declarative-gates-and-traceability.md` and hermetic test suites.

## 2. Key Architecture & Changes

1. **Declarative Gate Catalogue (`scripts/alongkit/hooks/default_gates.yaml`)**:
   - Declares 11 canonical protocol gates:
     1. `commit_issue_binding`: Intercepts `git commit` to require active issue slug.
     2. `commit_no_conflict_markers`: Blocks commits containing unresolved conflict markers.
     3. `anti_stub_injection`: Blocks lazy truncation placeholders and comment stubs.
     4. `cli_safety`: Blocks dangerous shell patterns (`<<EOF`, inline writers, destructive git wipes).
     5. `projection_protection`: Blocks manual writes to compiled views (`ISSUES.md`, `INDEX.md`).
     6. `typography`: Enforces clean ASCII characters and rejects typographic symbols.
     7. `require_active_issue`: Blocks modifying code without an active in-progress issue.
     8. `test_before_stop`: Enforces automated test execution before ending turn.
     9. `wrap_before_stop`: Enforces session log generation when closing an issue.
     10. `projection_sync_before_stop`: Enforces projection sync if issue files changed.
     11. `subproject_boundary`: Blocks root workspace entity pollution in subprojects.

2. **Declarative Engine & Predicates (`scripts/alongkit/hooks/declarative.py`, `predicates.py`)**:
   - `declarative.py`: YAML parser loading default and local gate definitions into `DeclarativeGate` instances.
   - `predicates.py`: Implements stateful check functions and records tool invocations into `.along/diagnostics/activity_trace.jsonl` with narrow exception handling.

3. **Traceability Scanner (`scripts/alongkit/hooks/traceability.py`)**:
   - Scans `AGENTS.md` and `skills/*/SKILL.md` for `[gate: <id>]` anchors.
   - Correlates anchors with active gates to ensure zero documentation drift.

4. **CLI Dispatcher & Verification (`scripts/along_hook.py`)**:
   - Added `along hook verify` (or `python scripts/along_hook.py verify`) command.
   - Integrated `bootstrap.ensure_deps()` across all engines to prevent dependency deadlocks.
   - Added `test_all_cli_scripts_call_ensure_deps` in `tests/test_alongkit.py`.

5. **Automated Tests & Documentation**:
   - `tests/test_declarative_gates.py`: Hermetic tests for YAML loading, regex matching, and predicates.
   - `tests/test_gates_traceability.py`: Integration tests for bi-directional traceability auditing.
   - `docs/topic--declarative-gates-and-traceability.md`: Architecture specification.
   - `docs/topic--runtime-hooks-and-gates.md`, `README.md`, and `docs/INDEX.md` updated.
   - Recorded ADR `ADR-2026-09-13--declarative-gate-engine-and-traceability`.

## 3. Quality & Verification Manifest

- Automated Tests: `python .along/scripts/test.py` -> 404 passed, 0 failed, 1 skipped.
- Traceability Verification: `python scripts/along_hook.py verify` -> 11/11 gates verified, PASSED.
- Typography: `python scripts/along_exec.py sanitize` -> 428 files scanned, no banned characters.
- Link Integrity: `python scripts/along_kb_sync.py` -> All 283 relative links verified on disk.
