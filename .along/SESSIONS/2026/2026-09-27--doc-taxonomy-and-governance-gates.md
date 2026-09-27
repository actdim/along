---
protocol: along
slug: doc-taxonomy-and-governance-gates
date: 2026-09-27
agent: antigravity
summary: "Implemented topic types taxonomy, write_policy: manual lock gate, milestone SemVer collision prevention gate, and CLI safety inline python interception"
milestone: v4.2.0-monorepo-subprojects
issues_advanced: []
issues_completed: [feat--doc-taxonomy-and-write-policy, feat--milestone-version-uniqueness-gate, bug--cli-safety-inline-python-and-budget-ceiling]
decisions: [ADR-2026-09-27--decouple-code-review-graph-from-mcp-to-direct-cli]
risks_logged: []
spikes_conducted: []
branch: main
commit: unknown
---

# Session Log: 2026-09-27 - Topic Taxonomy, Governance Gates & CLI Safety

## 1. Initial Implementation Plan (Baseline)

The objective was to implement documentation taxonomy, runtime protection gates, and entity integrity:
- Expand `alongkit.kb` with granular topic taxonomy (`reference`, `explanation`, `guide`, `architecture`, `domain-model`, `setup-workflow`, `topic`) to differentiate AST-grounded references from conceptual documents.
- Introduce `[gate: doc-manual-lock]` in declarative gates (`default_gates.yaml`) and `alongkit.hooks.predicates` to protect manual documentation from automated blast radius mutations.
- Enforce SemVer uniqueness across active milestones in `alongkit.entities` and `along milestone create`, preventing ambiguous release planning.
- Intercept exploratory inline Python executions probing internal modules via `[gate: cli_safety]` and calibrate context budget for `ISSUES.md`.

## 2. Execution & Loop Trace (Fixes & Re-plans)

- **Step 1: Topic Types Taxonomy & Manual Lock**:
  - Updated `scripts/alongkit/kb.py` defining taxonomy sets and `is_manual_write_policy` predicate.
  - Implemented `check_doc_manual_lock` in `scripts/alongkit/hooks/predicates.py` and registered `doc_manual_lock` in `default_gates.yaml`.
  - Updated `along_graph_impact.py` to skip `write_policy: manual` files during blast radius analysis.
  - Exempted `explanation` articles from ghost symbol checks in `scripts/along_kb_sync.py`.
- **Step 2: Milestone Version Collision Gate**:
  - Implemented `check_milestone_version_collision` in `scripts/alongkit/entities.py`.
  - Added duplicate check in `along milestone create` CLI command (`scripts/along_exec.py`).
  - Added collision detection in `validate_entities` to flag colliding active milestones during `along doctor`.
- **Step 3: CLI Safety & Budget Calibration**:
  - Added dangerous pattern detection in `DANGEROUS_CLI_PATTERNS` catching exploratory `python -c "import alongkit..."` calls.
  - Adjusted `DEFAULT_BUDGET_LIMITS["issues_md_bytes"]` to 6144 bytes to prevent false ceiling failures with 35+ tracked issues.
- **Step 4: Tests & Traceability**:
  - Authored hermetic tests in `tests/test_kb_sync.py` and `tests/test_along_exec.py`.
  - Verified gate traceability between `default_gates.yaml`, `AGENTS.md`, and `skills/along-init/protocol.md`.

## 3. Verification Walkthrough & Gate Manifest

```text
Gate Execution Manifest:
- Doc Manual Lock Gate: EXECUTED (PASS) [Manual documents protected from mutation]
- Milestone Collision Gate: EXECUTED (PASS) [SemVer collisions rejected in CLI and validation]
- CLI Safety Interception: EXECUTED (PASS) [Ad-hoc module probing blocked]
- Context Budget Compliance: EXECUTED (PASS) [ISSUES.md within calibrated 6 KB ceiling]
- Full Regression Test Suite: EXECUTED (PASS) [638 tests passing cleanly]
```
