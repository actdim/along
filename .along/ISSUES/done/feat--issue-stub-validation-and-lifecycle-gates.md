---
protocol: along
protocol_version: "4.4.15"
slug: issue-stub-validation-and-lifecycle-gates
type: feat
status: done
completed: 2026-10-16
priority: critical
created: 2026-10-16
updated: 2026-10-16
agent: antigravity
tags: [lifecycle, gates, quality, validation, anti-stub]
blocked_by: []
related: []
---

# Issue Stub Validation, Content Gates, and Lifecycle Hardening

## Background Context
During task execution across repositories, an issue was discovered where agent workflows closed empty scaffold tickets containing default boilerplate text:
- `Describe the feature, requirements, and background context here.`
- `Task requirement 1`
- `- [ ]` unchecked checkboxes

This was caused by multiple systemic architectural loopholes in Along:
1. `along issue done` did not validate markdown body content, allowing tickets with scaffold placeholders and unchecked criteria to be closed and relocated to `done/`.
2. `along wrap` validated unchecked checkboxes (`- [ ]`), but did not validate scaffold placeholder text or detect missing/empty acceptance criteria.
3. Neither `along start` nor plan approval blocked starting execution against an unpopulated stub ticket.
4. `AGENTS.md` contained conflicting instructions: `Entity Ecosystem` advised closing issues via `along issue done <slug>`, while `Stage & Session Completion Checklist` mandated `along wrap <slug>`.
5. `along commit` lacked protection against committing issues with scaffold placeholder boilerplate.

## Requirements
- REQ-1: Implement centralized issue content validation in `alongkit.entities` / `alongkit.gates` that detects template scaffold placeholder text, empty acceptance criteria, and uncompleted checklist items.
- REQ-2: Integrate content validation into `along issue done`, rejecting `status: done` if placeholder text remains, acceptance criteria are missing/empty, or unchecked `- [ ]` items exist.
- REQ-3: Integrate stub pre-check into `along start` and plan approval, preventing agents from starting execution or approving plans on unpopulated scaffold stubs.
- REQ-4: Enhance `along wrap` to run entity stub validation in addition to existing unchecked checklist verification.
- REQ-5: Add pre-commit check in `along commit` preventing commits containing issue scaffold placeholder strings in `.along/ISSUES/` and uncompleted checklist items in `.along/ISSUES/done/`.
- REQ-6: Reconcile `AGENTS.md` protocol to eliminate ambiguity between `along issue done` and `along wrap`.
- REQ-7: Provide comprehensive hermetic unit and behavioral regression tests in `tests/`.

## Acceptance Criteria
- [x] Centralized validator function `validate_issue_content` rejects scaffold placeholder phrases, missing acceptance criteria, and uncompleted checklist items for done status
- [x] `along issue done <slug>` fails with non-zero exit code when issue contains scaffold placeholders or unchecked items
- [x] `along start <slug>` rejects starting work on scaffold stubs that have not been populated with real requirements
- [x] `along wrap <slug>` rejects wrapping when issue contains scaffold placeholders
- [x] `along commit` fails when staged `.along/ISSUES/done/*.md` contains unchecked items or any `.along/ISSUES/**/*.md` contains template scaffold text
- [x] `AGENTS.md` protocol cleanly documents that active issues must be completed via `along wrap`
- [x] All test suites pass cleanly via `python .along/scripts/test.py`
