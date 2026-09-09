---
protocol: along
date: 2026-09-10
slug: agents-md-context-budget-pruning
agent: antigravity
branch: main
commit: pending
summary: Pruned AGENTS.md context budget from 32.6 KB to 10.8 KB and canonical protocol.md to 8.6 KB, enforcing 14 KB budget ceiling with automated regression tests.
milestone: v3.0.0-global-quality-revision
issues_advanced: []
issues_completed: [debt--agents-md-context-budget-pruning]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: AGENTS.md Context Budget Pruning

## Summary
Pruned root `AGENTS.md` and `skills/along-init/protocol.md` context budget:
1. Reduced `AGENTS.md` from 32,592 bytes to 10,764 bytes (-67%).
2. Reduced canonical template `skills/along-init/protocol.md` from 28,305 bytes to 8,593 bytes (-70%).
3. Lowered budget limit `DEFAULT_BUDGET_LIMITS["agents_md_bytes"]` from 32,768 to 14,336 bytes (14 KB) and `mandatory_session_bytes` from 49,152 to 32,768 bytes in `scripts/alongkit/budget.py`.
4. Added hard size regression tests `test_agents_md_hard_size_limit` and `test_protocol_md_hard_size_limit` in `tests/test_context_budget.py`.
5. Preserved 100% of normative behavioral rules and directives (MUST, FORBIDDEN, NEVER), eliminating only redundant prose, duplicates, and offloaded entity schemas.
6. Closed issue `debt--agents-md-context-budget-pruning`.

## Initial Implementation Plan (Baseline)
1. **Step 1**: Refactor `protocol.md` (SSOT) from 28,305 B to under 10,000 B.
2. **Step 2**: Sync `AGENTS.md` managed block and tighten Project specifics to under 14,336 B.
3. **Step 3**: Update budget limits to 14,336 B and add hard regression tests.
4. **Step 4**: Full test suite verification and documentation blast radius audit.

## Execution & Loop Trace (Fixes & Re-plans)
- `[Fix Loop - Skills Source Regex]`: `tests/test_skills_and_scripts.py` asserted exact regex `\*\*Skills Source\*\*:\s*\`skills/\`\s*\(([^)]+)\)` in `AGENTS.md`. Fixed tightened Project specifics section to retain the exact skills source format and full skill names.
- `[Fix Loop - Normative Title Match]`: `test_33_programmatic_integrity_gates_and_git_guard` asserted exact headings `Inquiry Read-Only Invariance (Zero-Mutation Rule on Questions)` and `Mandatory Adaptive Complexity Escalation & Execution Mode Routing`. Restored full headings in both `protocol.md` and `AGENTS.md`.

## Verification Walkthrough & Gate Manifest
- **Unit & Behavioral Tests**: `python .along/scripts/test.py` -> 353 passed, 0 failures, 1 skipped.
- **Size Verification**: `AGENTS.md`: 10,764 B < 14,336 B; `protocol.md`: 8,593 B < 14,336 B.
- **Typography Check**: `python scripts/along_exec.py sanitize` -> 320 files scanned, 0 violations.
- **Link Integrity Gate**: 0 broken relative markdown links.
