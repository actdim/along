---
protocol: along
date: 2026-09-09
slug: generated-dashboard-artifact-committed
agent: antigravity
branch: main
commit: pending
summary: Untracked generated dashboard artifacts from Git, ignored them in .gitignore, formalized the derived projection vs export artifact boundary in AGENTS.md, logged ADR-2026-09-09--untracked-dashboard-artifacts-and-projection-policy, and added a regression guard in test_zz_hermetic_suite.py.
milestone: v3.0.0-global-quality-revision
issues_advanced: []
issues_completed: [debt--generated-dashboard-artifact-committed]
decisions: [ADR-2026-09-09--untracked-dashboard-artifacts-and-projection-policy]
risks_logged: []
spikes_conducted: []
---

# Session: Untracked Dashboard Artifacts and Derived Projection Boundary

## Summary
Resolved technical debt `[debt--generated-dashboard-artifact-committed]`. Removed the 205 KB `.along/dashboard.html` static bundle and 3 KB dead `.along/DASHBOARD.md` from Git tracking and added them to `.gitignore`. Updated concurrency protocol in `AGENTS.md` and `skills/along-init/protocol.md` to cleanly separate Tracked Derived Projections (`.along/ISSUES.md`, `docs/INDEX.md`) from Untracked Export Artifacts (`.along/dashboard.html`, `.along/DASHBOARD.md`). Rejected `merge=ours` in `.gitattributes` due to standard Git missing a built-in driver. Recorded `ADR-2026-09-09--untracked-dashboard-artifacts-and-projection-policy` in `.along/DECISIONS.md`, recompiled `.along/CONSTRAINTS.md`, and added regression guard `test_03_no_unapproved_derived_projections_are_tracked` to `tests/test_zz_hermetic_suite.py`.

## Work Completed
1. **Git Tracking & .gitignore**:
   - Executed `git rm .along/dashboard.html .along/DASHBOARD.md`.
   - Updated `.gitignore` to exclude `.along/dashboard.html` and `.along/DASHBOARD.md`.
2. **Protocol & Concurrency Rules (`AGENTS.md`, `skills/along-init/protocol.md`)**:
   - Delineated Tracked Derived Projections (`.along/ISSUES.md`, `docs/INDEX.md`) from Untracked Export Artifacts (`.along/dashboard.html`, `.along/DASHBOARD.md`).
   - Reaffirmed Zero-Manual-Merge Rule (recompilation from atomic sources) as the resolution strategy for tracked projections.
   - Evaluated and rejected `merge=ours` in `.gitattributes`.
3. **Architectural Decisions & Constraints**:
   - Appended `ADR-2026-09-09--untracked-dashboard-artifacts-and-projection-policy` to `.along/DECISIONS.md`.
   - Recompiled `.along/CONSTRAINTS.md` via `along decision sync`.
4. **Knowledge Base Documentation**:
   - Updated `docs/topic--architecture.md` (diagram and projections text) and `docs/topic--skills-reference.md`.
   - Recompiled `docs/INDEX.md` and `llms-full.txt` via `along_kb_sync.py`.
5. **Regression Guard Test (`tests/test_zz_hermetic_suite.py`)**:
   - Added `test_03_no_unapproved_derived_projections_are_tracked` enforcing that no banned projection artifacts are tracked in Git.
6. **Issue Closure**:
   - Updated `debt--generated-dashboard-artifact-committed.md`, set status to `done`, completed on `2026-09-09`, moved to `.along/ISSUES/done/`, and updated `.along/ISSUES.md`.

## Verification
- Run `python .along/scripts/test.py`: 328 tests passed (`OK (skipped=1)`).
- Tested `python scripts/along_dash.py --export .along/dashboard.html` to ensure file is generated locally but ignored by Git.
