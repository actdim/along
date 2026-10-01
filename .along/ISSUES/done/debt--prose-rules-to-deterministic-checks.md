---
protocol: along
protocol_version: "4.4.1"
slug: prose-rules-to-deterministic-checks
type: debt
status: done
completed: 2026-09-30
priority: high
created: 2026-09-29
updated: 2026-09-30
agent: claude
tags: [gates, agents-md, determinism, ci]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [feat--git-level-gate-enforcement, feat--gate-strictness-profiles, debt--agents-md-core-slimming]
---

# Move AGENTS.md prose rules into deterministic checks

## Problem

Many `AGENTS.md` rules are written as prose ("MUST", "STRICTLY FORBIDDEN"). A prose rule is probabilistic: weak models skip it by inattention, strong models override it when they think they know better, and every rule costs context tokens every session. A rule enforced by code works identically with any model, costs zero tokens, and is portable across runtimes.

## Requirements

- REQ-1: Audit every rule in the managed `AGENTS.md` block and classify it: (a) already enforced by a gate/test, (b) mechanically checkable but not yet enforced, (c) judgment-only (cannot be checked by code).
- REQ-2: Record the audit as a table in `docs/topic--runtime-hooks-and-gates.md` (rule, class, enforcing gate/test, enforcement layer: runtime/git/ci).
- REQ-3: Implement checks for class (b) rules as gates or tests. Candidates: Stable Entry Point Rule (no links from `docs/`/`README.md` into `.along/`), portable links (no `file://`, no backslashes), Windows-safe filenames, untracked exports (`dashboard.html`, `DASHBOARD.md`), `ISSUES.md` size, code fence languages, no secrets in tracked files.
- REQ-4: For class (a) and newly enforced rules, shorten the prose in `AGENTS.md` to a one-line reference with the gate tag; the gate's error message carries the detail.
- REQ-5: Reuse the enforcement-layer field from `feat--git-level-gate-enforcement` (REQ-3 there) instead of inventing a parallel catalogue.

## Acceptance Criteria

- [x] Audit table published; every rule has a class
- [x] All class (b) rules have a gate or test with hermetic coverage (one left, canonical-key references, deferred to `feat--entity-reference-integrity-gate`)
- [x] `AGENTS.md` shrinks measurably: 13010 -> 12724 bytes (`protocol.md` 10954 -> 10668); `tests/test_context_budget.py` still passes
- [x] Automated tests passing (804 OK)
