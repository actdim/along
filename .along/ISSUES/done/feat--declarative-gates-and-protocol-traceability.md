---
protocol: along
protocol_version: "2.2.21"
slug: declarative-gates-and-protocol-traceability
type: feat
status: done
priority: critical
created: 2026-09-13
updated: 2026-09-13
completed: 2026-09-13
agent: antigravity
tags: [architecture, runtimes, hooks, gates, declarative, traceability, verification]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: []
related: [feat--runtime-enforcement-of-prose-rules]
---

# Declarative Gate Engine and Bi-Directional Protocol Traceability

## 1. Problem Statement & Failure Analysis

In `feat--runtime-enforcement-of-prose-rules`, Along established the foundational runtime hook architecture (`HookEngine`, `AntigravityAdapter`, `TypographyGate`, `ProjectionProtectionGate`, `CliSafetyGate`). However, three critical structural gaps remain:

1. **Hardcoded Engine Coupling**: All gate logic currently requires custom Python classes in `scripts/alongkit/hooks/gates.py`. Authors of skills, protocols, and subprojects cannot declare or customize enforcement rules without modifying Python code in the core engine.
2. **Missing Protocol Invariants (10+ Gate Gaps)**: Crucial protocol rules from `AGENTS.md` and `skills/` remain purely advisory prose:
   - Modifying code without an active issue (`Mandatory Issue Anchoring`).
   - Git commits with missing issue slugs (`[type--slug]`) or unresolved merge conflict markers.
   - Code truncation placeholders / lazy stubs (`// ... rest of code`, `# ...`).
   - Terminating turns (`Stop`) without executing test runners after modifying code.
   - Closing issues (`status: done`) without generating a session log in `.along/SESSIONS/`.
   - Modifying atomic entities without recompiling projections (`ISSUES.md`, `docs/INDEX.md`).
   - Subproject boundary violations (writing `.along/` entities at workspace root).
3. **Traceability Void**: There is no machine-verifiable connection between human-readable rules in prose (`AGENTS.md`, `skills/*/SKILL.md`) and runtime gates. An agent reading a skill does not know which sentences are mechanically enforced, and a test suite cannot verify if documented rules have active enforcement.

## 2. Requirements & Acceptance Criteria

- **REQ-1 (Declarative Gate Engine)**:
  - Implement dynamic gate loader in `scripts/alongkit/hooks/declarative.py`.
  - Parse YAML gate specifications from `scripts/alongkit/hooks/default_gates.yaml` and optional repo overrides in `.along/rules/gates.yaml`.
  - Support declarative validation rules: `regex_match`, `regex_forbidden`, `path_allowlist`, `path_denylist`, and `predicate`.
- **REQ-2 (10+ Core Protocol Invariant Gates)**:
  - Implement full catalogue of core gates in `default_gates.yaml`:
    1. `commit-issue-binding`: Intercepts `git commit`, enforces `[<type>--<slug>]` format.
    2. `commit-no-conflict-markers`: Blocks commits containing `<<<<<<<` conflict markers.
    3. `anti-stub-injection`: Blocks lazy truncation skeletons (`// ... rest of code`, `# ... todo`).
    4. `cli-safety`: Blocks destructive shell operations (`git reset --hard`, `git clean -f`, global installs).
    5. `projection-protection`: Blocks manual edits to `.along/ISSUES.md` and `docs/INDEX.md`.
    6. `clean-ascii-typography`: Blocks forbidden non-ASCII typography.
    7. `require-active-issue`: Blocks editing project code unless an issue has `status: in-progress`.
    8. `test-before-stop`: Blocks `Stop` event if code was edited but tests were not executed afterward.
    9. `wrap-before-stop`: Blocks `Stop` event if an issue was marked done without recording a session log.
    10. `projection-sync-before-stop`: Blocks `Stop` event if atomic issues or docs changed without projection sync.
    11. `subproject-boundary`: Blocks writing `.along/` at workspace root when inside a subproject.
- **REQ-3 (Stateful Predicates)**:
  - Implement Python predicate handlers in `scripts/alongkit/hooks/predicates.py` for stateful checks: `check_active_issue`, `check_typography`, `check_session_test_status`, `check_session_wrap_status`, `check_projection_sync_status`.
- **REQ-4 (Traceability Scanner & Linter)**:
  - Implement `scripts/alongkit/hooks/traceability.py`.
  - Scan markdown files (`AGENTS.md`, `skills/**/SKILL.md`, `.along/rules/**.md`, `docs/**/*.md`) for `[gate: <id>]` anchors.
  - Enforce bi-directional consistency: every prose badge maps to a valid gate in YAML; every active gate has prose documentation; gate schemas and handlers are valid.
- **REQ-5 (CLI Command)**:
  - Integrate `along hook verify` (or `python scripts/along_hook.py verify`) to generate a clean ASCII status and audit report.
- **REQ-6 (Documentation & Promotion)**:
  - Author `docs/topic--declarative-gates-and-traceability.md`.
  - Update `docs/topic--runtime-hooks-and-gates.md`, `docs/INDEX.md`, and `README.md`.
- **REQ-7 (Hermetic Automated Tests)**:
  - Comprehensive unit and integration tests in `tests/test_declarative_gates.py` and `tests/test_gates_traceability.py`.
  - All existing and new tests pass (zero regressions).
