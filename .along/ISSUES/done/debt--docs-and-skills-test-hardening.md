---
protocol: along
protocol_version: "4.9.1"
slug: docs-and-skills-test-hardening
type: debt
status: done
completed: 2026-11-25
priority: high
created: 2026-11-24
updated: 2026-11-25
agent: antigravity
tags: [tests, audit, paper-compliance, refactoring]
milestone: v5.0.0-agent-run-protocol-and-observability
blocked_by: []
related: [debt--test-suite-paper-compliance-cleanup]
plan_status: approved
---

# Harden test_docs.py and test_skills_and_scripts.py assertions

## Problem
Follow-up to `debt--test-suite-paper-compliance-cleanup`. Commit `0171a45` updated `test_version_bump.py`, `test_release_ci_check.py`, `test_system_comparisons.py`, and `test_docker_scripts.py`, but left `tests/test_docs.py` and `tests/test_skills_and_scripts.py` untouched despite REQ-2 and REQ-4 in the original ticket.

## Requirements
- REQ-1: `tests/test_docs.py` MUST replace brittle marketing/prose substring matching with structural Markdown link, code fence, and schema verification.
- REQ-2: `tests/test_skills_and_scripts.py` MUST upgrade superficial `os.path.isfile` checks to Python AST parsing and `SKILL.md` YAML frontmatter schema validation.

## Acceptance Criteria
- [x] `tests/test_docs.py` uses structural link, fence, and schema checks instead of brittle phrase matching
- [x] `tests/test_skills_and_scripts.py` validates Python AST syntax and `SKILL.md` frontmatter schemas
- [x] Automated tests in `tests/test_docs.py` and `tests/test_skills_and_scripts.py` pass with zero regressions
