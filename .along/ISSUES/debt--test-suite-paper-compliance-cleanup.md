---
protocol: along
protocol_version: "4.9.1"
slug: test-suite-paper-compliance-cleanup
type: debt
status: open
priority: high
created: 2026-11-22
updated: 2026-11-22
agent: antigravity
tags: [tests, audit, paper-compliance, refactoring]
milestone: v5.0.0-agent-run-protocol-and-observability
blocked_by: []
related: [bug--engine-atomicity-and-gate-resilience]
---

# Test suite paper compliance cleanup and contract assertion hardening

## Problem
Audit of the repository test suite (132 test files) revealed several patterns of paper compliance, redundant execution, and shallow verification that inflate test metrics without providing real contract enforcement:
1. Redundant test suites: `tests/test_version_bump.py` subclasses `TestReleaseCiCheck` from `tests/test_release_ci_check.py` without adding test methods, causing the exact same 15 test cases to run twice in every full test pass.
2. Brittle marketing prose assertions: `tests/test_system_comparisons.py` and `tests/test_docs.py` perform literal string matching on marketing phrases in markdown documentation instead of asserting structural schema integrity, code fence validity, or link resolution.
3. Over-mocked preflight assertions: `tests/test_release_ci_check.py:264-281` mocks out subcommands and asserts only mock call arguments rather than asserting how the system responds to preflight failures and rollbacks.
4. Superficial file existence checks: `tests/test_docker_scripts.py` and `tests/test_skills_and_scripts.py` assert `os.path.isfile(path) is True` without verifying executable permissions, syntax validity (AST parsing), or YAML front-matter structure.

## Requirements
- REQ-1: Deduplicate test execution: Remove redundant test class aliases in `tests/test_version_bump.py` so each release check test runs exactly once.
- REQ-2: Semantic documentation validation: Replace brittle marketing phrase substring matching in `tests/test_system_comparisons.py` and `tests/test_docs.py` with structural AST/markdown link and code fence verification.
- REQ-3: Behavioral mock hardening: Refactor `tests/test_release_ci_check.py:264-281` to assert system behavior on mock failure (exit code, error reporting, transactional rollback) rather than tautological call-argument matching.
- REQ-4: Contract-level file verification: Enhance `tests/test_docker_scripts.py` and `tests/test_skills_and_scripts.py` to parse Python AST and validate SKILL.md front-matter schemas rather than relying solely on `os.path.isfile`.

## Acceptance Criteria
- [ ] Deduplicate test execution between `tests/test_version_bump.py` and `tests/test_release_ci_check.py`
- [ ] Replace brittle text matching in `tests/test_system_comparisons.py` and `tests/test_docs.py` with structural link and fence verification
- [ ] Harden mock assertions in `tests/test_release_ci_check.py` to verify failure behavior and rollbacks
- [ ] Upgrade superficial file existence checks in `tests/test_docker_scripts.py` and `tests/test_skills_and_scripts.py` to syntax and schema checks
- [ ] Full test pass passes with zero regressions and clean typography
