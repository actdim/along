---
protocol: along
slug: agents-md-context-budget-pruning
type: debt
status: done
completed: 2026-09-10
priority: high
created: 2026-09-09
updated: 2026-09-10
agent: antigravity
tags: [context-budget, prompt-optimization, agents-md, token-efficiency]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [debt--always-on-context-budget-exceeds-claims]
---

# Prune AGENTS.md Context Budget to Under 14 KB

## 1. Problem Statement

The repository's root `AGENTS.md` protocol file currently measures **32.6 KB (approximately 8,500 tokens)**.

In `debt--always-on-context-budget-exceeds-claims`, REQ-2 established a strict budget target:
> "Set explicit budgets and enforce them by test, for example: AGENTS.md under 12 KB, ISSUES.md under 4 KB, mandatory session reads under 40 KB total. Fail the suite when a budget is exceeded."

The issue was prematurely marked `status: done` on 2026-09-07 without reducing `AGENTS.md` to this limit. Because `AGENTS.md` is loaded automatically on every agent turn and by every subagent spawn, this bloat consumes over 25-30% of standard context windows on repetitive protocol prose before any task work begins.

## 2. Root Causes of Bloat in `AGENTS.md`

1. **Repetitive Checklists**: The 9-step session completion checklist appears both in `## Mandatory Stage & Session Completion Checklist` and again in descriptive prose rules.
2. **Verbose Submodule & Placement Instructions**: Detailed monorepo explanations occupy 25 lines that can be condensed into 5 concise directives.
3. **Duplicated Typography Tables**: Banned character listings duplicate information already provided in `rules/INDEX.md` and rule packs.
4. **Historical Migration Verbiage**: Explanations of why legacy `.agents/` or `.along/KB/` were replaced clutter the active protocol.

## 3. Requirements

- REQ-1: Refactor and compress `AGENTS.md` and its canonical template in `skills/along-init/protocol.md` to under **14 KB** without removing normative constraints or behavioral invariants.
- REQ-2: Offload detailed monorepo rationale and migration mechanics to referenced documentation in `docs/` (`topic--architecture.md`, `topic--setup-and-workflow.md`).
- REQ-3: Maintain strict imperative directives (`MUST`, `FORBIDDEN`) for file modification, issue anchoring, testing, and typography.
- REQ-4: Add a hard regression test in `tests/test_context_budget.py` asserting `os.path.getsize("AGENTS.md") < 14336` (14 KB) and `os.path.getsize("skills/along-init/protocol.md") < 14336`.

## 4. Acceptance Criteria

- [x] `AGENTS.md` file size reduced to under 14 KB (measured: 10,764 B).
- [x] Canonical template `skills/along-init/protocol.md` stays synchronized under 14 KB (measured: 8,593 B).
- [x] No normative rules (issue anchoring, test-first lifecycle, clean typography, ASCII safety) are lost.
- [x] Regression test enforces the 14 KB budget ceiling on every test suite execution.
