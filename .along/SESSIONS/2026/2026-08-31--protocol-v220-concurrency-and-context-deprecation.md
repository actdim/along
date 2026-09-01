---
protocol: along
date: 2026-08-31
slug: protocol-v220-concurrency-and-context-deprecation
agent: antigravity
branch: main
commit: pending
summary: 'Along Protocol v2.2.0: Multi-branch concurrency, derived projections, decentralized ADR slug format, and removal of degenerate CONTEXT.md.'
milestone: v2.2.0-along
issues_advanced: []
issues_completed: [feat--concurrency-projections-and-context-deprecation]
decisions: [ADR-2026-08-31--concurrency-projections-and-context-deprecation]
risks_logged: []
spikes_conducted: []
---

# Session: Protocol v220 concurrency and context deprecation

## Summary
Along Protocol v2.2.0: Multi-branch concurrency, derived projections, decentralized ADR slug format, and removal of degenerate CONTEXT.md.

## Work Completed
- Configured `.gitattributes` with `merge=union` for append-only files (`HISTORY.md`, `DECISIONS.md`).
- Formally classified `ISSUES.md`, `docs/INDEX.md`, and `DASHBOARD.md` as Derived Projections with Zero-Manual-Merge policy.
- Completely removed `CONTEXT.md` across repository, protocol definitions, startup instructions, and wrap checklists.
- Migrated all 15 past ADRs in `.along/DECISIONS.md` from sequential numbering to `ADR-YYYY-MM-DD--<slug>` and added ADR-016.
- Codified Mandatory Issue Anchoring in `AGENTS.md` before making code changes.
- Added `status`, `doctor`, and `issue sync` subcommands to `scripts/along_exec.py`.
- Updated all skills (`along-init`, `along-wrap`, `along-decision-sync`, `along-context-sync`, `along-team`).
- Updated `docs/topic--architecture.md` and `README.md`.

## Code Review & Blast Radius
- **Test Suite**: All 25 automated unit tests verified passing (`python -m unittest discover tests -v`).
- **Protocol Doctor**: `python scripts/along_exec.py doctor` reports 0 errors and 0 warnings.
- **Typography**: Verified zero non-ASCII typographic characters across all files.
- **Blast Radius**: Zero breaking changes to consumers; backward compatibility maintained with automatic projection rebuilds.
