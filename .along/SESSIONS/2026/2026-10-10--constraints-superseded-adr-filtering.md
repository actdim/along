---
protocol: along
protocol_version: "4.4.8"
date: 2026-10-10
slug: constraints-superseded-adr-filtering
agent: antigravity
branch: main
commit: d1c8c7c
summary: filter superseded ADRs from CONSTRAINTS.md, add decision conflict detection and sync check
milestone: v4.5.0-multi-user-merge-automation
issues_advanced: []
issues_completed: [debt--constraints-superseded-adr-filtering]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Constraints superseded adr filtering

## Summary
filter superseded ADRs from CONSTRAINTS.md, add decision conflict detection and sync check

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: role-based; plan revision 1; approved: true.

| Step | Title | Status | Retries | Review |
| --- | --- | --- | --- | --- |
| 1 | Update frontmatter of 4 superseded ADRs in .along/DECISIONS/ setting status and superseded_by | passed | 0 | yes |
| 2 | Implement decision status updates, check_decision_conflicts, and along decision sync --check in entities.py and along_exec.py | passed | 0 | yes |
| 3 | Safeguard docs/decisions/ in along_kb_search.py and sync decisions mirror banner | passed | 0 | yes |
| 4 | Recompile projections, add tests in test_modular_decisions.py, verify test suite | passed | 0 | yes |

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/DECISIONS/ADR-2026-08-26--code-graph-mcp-and-hybrid-kb-search.md` | state | 1 | 2026-10-10T12:43:07Z | antigravity--1f3fe0f2-9f67-4e9d-ad59-4ca91133f7b7 |
| `.along/DECISIONS/ADR-2026-08-26--protocol-v120-knowledge-base-architecture.md` | state | 1 | 2026-10-10T12:43:02Z | antigravity--1f3fe0f2-9f67-4e9d-ad59-4ca91133f7b7 |
| `.along/DECISIONS/ADR-2026-08-27--protocol-v150-automated-entities-and-intent-heuristics.md` | state | 1 | 2026-10-10T12:43:12Z | antigravity--1f3fe0f2-9f67-4e9d-ad59-4ca91133f7b7 |
| `.along/DECISIONS/ADR-2026-08-27--universal-version-bumping-and-scripts-ecosystem.md` | state | 1 | 2026-10-10T12:43:17Z | antigravity--1f3fe0f2-9f67-4e9d-ad59-4ca91133f7b7 |
| `scripts/along_exec.py` | source | 2 | 2026-10-10T12:49:23Z | antigravity--1f3fe0f2-9f67-4e9d-ad59-4ca91133f7b7 |
| `scripts/along_kb_search.py` | source | 1 | 2026-10-10T12:48:29Z | antigravity--1f3fe0f2-9f67-4e9d-ad59-4ca91133f7b7 |
| `scripts/along_kb_sync.py` | source | 1 | 2026-10-10T12:48:35Z | antigravity--1f3fe0f2-9f67-4e9d-ad59-4ca91133f7b7 |
| `scripts/alongkit/entities.py` | source | 4 | 2026-10-10T12:46:25Z | antigravity--1f3fe0f2-9f67-4e9d-ad59-4ca91133f7b7 |
| `tests/test_modular_decisions.py` | source | 4 | 2026-10-10T12:51:09Z | antigravity--1f3fe0f2-9f67-4e9d-ad59-4ca91133f7b7 |

### Plan

#### Living Plan: constraints-superseded-adr-filtering

Title: CONSTRAINTS.md lists superseded ADRs as active constraints

##### Execution Mode
Role-Based (along-team)

##### Requirements Traceability
- REQ-1: Audit ADRs in `.along/DECISIONS/` and set `status: superseded` and `superseded_by` for replaced decisions.
- REQ-2: Exclude `superseded`, `deprecated`, and `rejected` ADRs from `CONSTRAINTS.md`, list them under Superseded in `DECISIONS.md`.
- REQ-3: Implement conflict detection gate in `entities.py` and hook into `along decision sync --check`.
- REQ-4: Formalize `docs/decisions/` as a generated MkDocs mirror with explicit double-count protection in `kb-search`.

##### Steps
- [x] Step 1: Update frontmatter of 4 superseded ADRs in `.along/DECISIONS/` setting status and superseded_by.
- [x] Step 2: Implement decision status updates, check_decision_conflicts, and along decision sync --check in entities.py and along_exec.py.
- [x] Step 3: Safeguard docs/decisions/ in along_kb_search.py and sync decisions mirror banner.
- [x] Step 4: Recompile projections, add tests in test_modular_decisions.py, verify test suite.

### Research

#### Research & Findings: constraints-superseded-adr-filtering

##### Target Symbols and Files
- `scripts/alongkit/entities.py`: `DECISION_STATUSES`, `ACTIVE_DECISION_STATUSES`, `sync_constraints`, `compile_decisions_board`, `check_decision_conflicts`
- `scripts/along_exec.py`: `handle_decision_command` (`along decision sync [--check]`)
- `scripts/along_kb_sync.py`: `sync_decisions_to_docs`
- `scripts/along_kb_search.py`: `collect_knowledge_base_entries`
- `.along/DECISIONS/`: 4 ADRs to mark superseded:
  - `ADR-2026-08-26--protocol-v120-knowledge-base-architecture.md` (superseded by `llm-wiki-docs-architecture-and-singular-skills-refactoring`)
  - `ADR-2026-08-26--code-graph-mcp-and-hybrid-kb-search.md` (superseded by `decouple-code-review-graph-from-mcp-to-direct-cli`)
  - `ADR-2026-08-27--protocol-v150-automated-entities-and-intent-heuristics.md` (superseded by `entity-relationships-unidirectional-graph-and-canonical-slugs`)
  - `ADR-2026-08-27--universal-version-bumping-and-scripts-ecosystem.md` (superseded by `version-ssot-consolidation-and-dynamic-packaging`)
- `tests/test_modular_decisions.py`: test cases for superseded exclusion, conflict detection, and `--check` CLI flag.

##### Constraints & Risks
- `CONSTRAINTS.md` is read by agents at every session start, must remain concise and accurate without contradictory superseded advice.
- `docs/decisions/` is needed by MkDocs for static site builds and must be preserved as a generated mirror without being double-counted in `kb-search`.
- Conflict detection heuristic should reliably flag accepted ADR pairs where a newer ADR references an older one with shared tags, unless explicitly marked complementary.

### Execution Trace

#### Execution Trace: constraints-superseded-adr-filtering
- 2026-10-10T12:23:32Z denied [require_plan_approval] run_command: Inquiry Read-Only Invariance [gate: require-plan-approval]: No approved plan for issue 'constraints-superseded-adr-filtering' (phase: 'planning', plan_approv... (x2)
- 2026-10-10T12:42:24Z plan approved (along plan approve)
- 2026-10-10T12:42:33Z step 1: pending -> in-progress
- 2026-10-10T12:43:02Z edit .along/DECISIONS/ADR-2026-08-26--protocol-v120-knowledge-base-architecture.md
- 2026-10-10T12:43:07Z edit .along/DECISIONS/ADR-2026-08-26--code-graph-mcp-and-hybrid-kb-search.md
- 2026-10-10T12:43:12Z edit .along/DECISIONS/ADR-2026-08-27--protocol-v150-automated-entities-and-intent-heuristics.md
- 2026-10-10T12:43:17Z edit .along/DECISIONS/ADR-2026-08-27--universal-version-bumping-and-scripts-ecosystem.md
- 2026-10-10T12:43:28Z step 1: in-progress -> passed
- 2026-10-10T12:43:33Z step 2: pending -> in-progress
- 2026-10-10T12:45:20Z edit scripts/alongkit/entities.py (x3)
- 2026-10-10T12:45:34Z edit scripts/along_exec.py
- 2026-10-10T12:46:25Z edit scripts/alongkit/entities.py
- 2026-10-10T12:46:41Z step 2: in-progress -> passed
- 2026-10-10T12:46:45Z step 3: pending -> in-progress
- 2026-10-10T12:48:29Z edit scripts/along_kb_search.py
- 2026-10-10T12:48:35Z edit scripts/along_kb_sync.py
- 2026-10-10T12:48:51Z step 3: in-progress -> passed
- 2026-10-10T12:48:54Z step 4: pending -> in-progress
- 2026-10-10T12:49:23Z edit scripts/along_exec.py
- 2026-10-10T12:51:09Z edit tests/test_modular_decisions.py (x4)
- 2026-10-10T12:51:33Z step 4: in-progress -> passed
- 2026-10-10T12:56:07Z test pass (Wrap Quality Gate)

### Review step-1

#### Review: Step 1

##### Rubric Checks
- Zero-Byte & File Integrity Gate: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS)
- Diff Scope Audit: EXECUTED (PASS) [4 ADRs in .along/DECISIONS/ marked superseded with superseded_by links]
- Requirement Traceability Gate: EXECUTED (PASS) [REQ-1: Audit all ADRs and set status: superseded]
- Blast Radius & Architecture: EXECUTED (PASS)
- Clean Typography: EXECUTED (PASS)

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS)
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-1]
- Blast Radius: EXECUTED (PASS)
- Clean Typography: EXECUTED (PASS)

VERDICT: PASS

### Review step-2

#### Review: Step 2

##### Rubric Checks
- Zero-Byte & File Integrity Gate: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS)
- Diff Scope Audit: EXECUTED (PASS) [entities.py, along_exec.py updated with deprecated status, check_decision_conflicts, and --check mode]
- Requirement Traceability Gate: EXECUTED (PASS) [REQ-2, REQ-3: along decision sync --check and conflict detection heuristic implemented]
- Blast Radius & Architecture: EXECUTED (PASS)
- Clean Typography: EXECUTED (PASS)

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS)
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-2, REQ-3]
- Blast Radius: EXECUTED (PASS)
- Clean Typography: EXECUTED (PASS)

VERDICT: PASS

### Review step-3

#### Review: Step 3

##### Rubric Checks
- Zero-Byte & File Integrity Gate: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [test_kb_search.py passed]
- Diff Scope Audit: EXECUTED (PASS) [along_kb_search.py excludes docs/decisions, along_kb_sync.py includes projection banner]
- Requirement Traceability Gate: EXECUTED (PASS) [REQ-4: docs/decisions mirror safeguarded against double-counting and banner formalized]
- Blast Radius & Architecture: EXECUTED (PASS)
- Clean Typography: EXECUTED (PASS)

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS)
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-4]
- Blast Radius: EXECUTED (PASS)
- Clean Typography: EXECUTED (PASS)

VERDICT: PASS

### Review step-4

#### Review: Step 4

##### Rubric Checks
- Zero-Byte & File Integrity Gate: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [15 tests in test_modular_decisions.py passed]
- Diff Scope Audit: EXECUTED (PASS) [projections compiled, along_exec.py local variable scoping fixed, comprehensive unit tests added]
- Requirement Traceability Gate: EXECUTED (PASS) [REQ-1, REQ-2, REQ-3, REQ-4: full test coverage and projection verification]
- Blast Radius & Architecture: EXECUTED (PASS)
- Clean Typography: EXECUTED (PASS)

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS)
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-1, REQ-2, REQ-3, REQ-4]
- Blast Radius: EXECUTED (PASS)
- Clean Typography: EXECUTED (PASS)

VERDICT: PASS
