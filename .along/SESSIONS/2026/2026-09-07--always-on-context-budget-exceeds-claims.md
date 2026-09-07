---
protocol: along
date: 2026-09-07
slug: always-on-context-budget-exceeds-claims
agent: antigravity
branch: main
commit: pending
summary: Resolved always-on context budget overrun by implementing measurement engine (along context-budget), capping ISSUES.md sliding window to 5 items, creating compiled active constraints projection (.along/CONSTRAINTS.md), optimizing session-start protocol reads, and enforcing CI budget gates.
milestone: v3.0.0-global-quality-revision
issues_advanced: []
issues_completed: [debt--always-on-context-budget-exceeds-claims]
decisions: [ADR-2026-09-07--bounded-context-budget-and-active-projections]
risks_logged: []
spikes_conducted: []
---

# Session: Always-On Context Budget Optimization and Active Constraints Projection

## Summary
Remediated [debt--always-on-context-budget-exceeds-claims](../../ISSUES/done/debt--always-on-context-budget-exceeds-claims.md) using the along-team sequential state machine protocol. Before remediation, always-on context read at session start ballooned to 113 KB (~30,000 tokens) due to unbounded growth of `DECISIONS.md` (72 KB, 30 ADRs) and `ISSUES.md` (10.5 KB, all 67 completed issues retained). Designed and implemented a comprehensive context budget and active projection subsystem:
1. Created `alongkit/budget.py` context measurement engine and wired `along context-budget` (alias `along budget`) supporting `--json` data contracts and `--check` automated regression gates.
2. Capped `ISSUES.md` `## Done (recent)` projection to a chronological sliding window of 5 items sorted by completion date, reducing file size from 10,552 bytes to 3,082 bytes (70% reduction).
3. Introduced dual-layer decision architecture: `.along/DECISIONS.md` remains the append-only Single Source of Truth (SSOT) preserving Git union-merge safety, while `.along/CONSTRAINTS.md` serves as a concise, compiled projection of active architectural constraints (12,327 bytes, down 83% from 72 KB). Wired `along decision sync` and auto-compilation into `along decision create`.
4. Updated session-start protocol item 3 in `skills/along-init/protocol.md` and `AGENTS.md` to read `.along/CONSTRAINTS.md` instead of full `DECISIONS.md`.
5. Added automated CI test gates in `tests/test_context_budget.py` guarding live repository context limits (`agents_md_bytes <= 32 KB`, `issues_md_bytes <= 4 KB`, `constraints_md_bytes <= 16 KB`, `mandatory_session_bytes <= 48 KB`).
6. Grounded published claims in `README.md` and `docs/topic--domain-model.md`, removing outdated "< 300 tokens" claim and documenting the dual-layer architecture.
7. Appended `ADR-2026-09-07--bounded-context-budget-and-active-projections` and marked `ADR-2026-08-15` as superseded. Total test suite expanded from 304 to 305 tests with 100% pass rate.

## Requirements Traceability & Verification
- **REQ-1 (Measurement Tool & CLI)**: Implemented in `scripts/alongkit/budget.py` and `scripts/along_exec.py`. Supports human report, `--json`, and `--check`. Verified by `test_cli_json_output`, `test_cli_human_readable_output`, and `test_cli_check_mode_exit_codes`.
- **REQ-2 (Explicit Budgets & Test Gates)**: Enforced default limits in `scripts/alongkit/budget.py` and implemented `test_live_repo_budget_compliance` in `tests/test_context_budget.py`. Exits code 1 on budget violation.
- **REQ-3 (Per-Stack Rule Attachment)**: Pre-verified and maintained.
- **REQ-4 (Dual-Layer Decision Log)**: SSOT append-only log in `DECISIONS.md` preserved; compiled active constraints projection generated at `.along/CONSTRAINTS.md`.
- **REQ-5 (Cap ISSUES.md Recent Done)**: Implemented sliding window of 5 recent completed issues sorted chronologically by front-matter `completed` date.
- **REQ-6 (System Prompt Progressive Disclosure)**: Updated session-start reading list in `skills/along-init/protocol.md` and synchronized `AGENTS.md` managed block byte-for-byte (`test_03b` passed).
- **REQ-7 (Grounded Claims & ADR Supersession)**: Re-derived metrics from measurements; updated `README.md` and `docs/topic--domain-model.md`; recorded new ADR superseding `ADR-2026-08-15`.

## Code Review & Blast Radius
- All 305 automated tests passed in 19.4s via `python .along/scripts/test.py`.
- Working tree integrity: All new and modified files have non-zero size.
- Typography: Zero banned characters across 292 scanned files (`along sanitize`).
- Context budget: Mandatory session reads decreased from 113 KB to 46.2 KB (~12,066 tokens), a net reduction of ~60%.
