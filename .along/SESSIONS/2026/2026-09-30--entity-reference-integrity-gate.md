---
protocol: along
protocol_version: "4.4.1"
date: 2026-09-30
slug: entity-reference-integrity-gate
agent: claude-code
branch: main
commit: 27c6642
summary: entity_reference_integrity gate (runtime Stop, wrap, issue sync, pre-commit/CI blocking only new problems); along issue rename/supersede with inbound reference rewriting; milestone target_issues sync on create; along bump refuses open milestones (--carry-over); migration graph reuses validate_entities (uncommitted, per user)
issues_advanced: []
issues_completed: [feat--entity-reference-integrity-gate]
decisions: []
risks_logged: []
spikes_conducted: []
milestone: v4.5.0-multi-user-merge-automation
---

# Session: Entity reference integrity gate

## Summary

Sixth v4.5.0 task by priority, single-agent sequential, workspace: inherit, no commits per user.

## Initial Implementation Plan (Baseline)

1. `entities`: ancestor-context keys in `validate_entities`, reference rewriting, `rename_issue`,
   `supersede_issue`, `milestone_open_issues` (REQ-3, REQ-4, REQ-8).
2. Gate `entity_reference_integrity` (`enforcement: [runtime, git, ci]`): Stop predicate,
   `gates.entity_integrity_gate` in `along wrap` and `along issue sync` (REQ-1).
3. `gitgates.check_entity_references`: staged / checked-out snapshot vs HEAD / range base,
   only new problems block; wired into pre-commit, `--ci` and `along commit` (REQ-2).
4. CLI `issue rename` / `issue supersede`; `issue create --milestone` syncs the milestone (REQ-3, REQ-7).
5. `along bump` aborts on open milestone issues, `--carry-over <milestone>` (REQ-8).
6. Protocol line with the gate tag; tests; docs (REQ-5, REQ-6).

## Execution & Loop Trace (Fixes & Re-plans)

- First full run: 8 failures. The gate blocked on every `validate_entities` finding, and old
  fixtures carry slug/filename drift and missing `completed` dates. Narrowed the gate to what
  the issue asks for: dangling references and enum violations (`entities.is_integrity_error`);
  the rest stays with `along doctor --entities`.
- The migration graph now calls `validate_entities`, which raised on a non-UTF-8 fixture; the
  call degrades to a warning there.
- The release fixture's milestone listed an open issue, which REQ-8 now correctly refuses; the
  fixture closes that issue in `setUp`.
- Listed `target_issues` with no issue file are dangling references (reported by the gate), not
  open issues, for the bump check.
- Git snapshots carry a `.git` marker so the ancestor walk never leaves the snapshot.

## Verification Walkthrough & Gate Manifest

- `along test -q`: 820 tests OK (16 new in `tests/test_entity_reference_integrity.py`).
- `along hook verify --strict`: PASSED. `along doctor --entities`: 0 errors, 0 warnings.
- `along gates check --ci --no-links`: all checks passed. Typography: 676 files clean.

```text
Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [along test -q, 820 OK]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-1..REQ-8]
- Blast Radius: DEGRADED (PASS) [static search, code-review-graph offline: validate_entities, update_along_milestones, check_pre_commit, check_ci, execute_wrap callers]
- Documentation Parity: EXECUTED (PASS) [cli-reference, declarative-gates, runtime-hooks audit table, skills-reference, domain-model, AGENTS.md/protocol.md]
- Clean Typography: EXECUTED (PASS)
```
