---
protocol: along
date: 2026-09-09
slug: consolidate-version-ssot-and-repair-protocol-desync
agent: antigravity
branch: main
commit: pending
summary: Consolidated version Single Source of Truth into scripts/alongkit/version.py, configured PEP 621 dynamic Hatchling packaging in pyproject.toml, decoupled 18 skill manifests from release version rewriting, repaired .along/.protocol-version desync, and recorded ADR.
milestone: v3.0.0-global-quality-revision
issues_advanced: []
issues_completed: [debt--consolidate-version-ssot-and-repair-protocol-desync]
decisions: [ADR-2026-09-09--version-ssot-consolidation-and-dynamic-packaging]
risks_logged: []
spikes_conducted: []
---

# Session: Consolidate Version SSOT and Repair Protocol Version Desync

## Summary
Addressed architectural version duplication (Shotgun Surgery) and repaired the 14-release `.along/.protocol-version` desync:
1. Established `scripts/alongkit/version.py` as the canonical Single Source of Truth (`CURRENT_PROTOCOL_VERSION`, `CURRENT_VERSION`, and standard `__version__ = CURRENT_VERSION`).
2. Converted `pyproject.toml` to standard PEP 621 `dynamic = ["version"]` using Hatchling regex resolution, removing static version hardcoding from Python packaging.
3. Updated `dashboard/app.py` to import `CURRENT_VERSION` directly from `alongkit.version`.
4. Stripped ` [vX.Y.Z]` title suffixes from all 18 `skills/*/SKILL.md` files and removed the skill rewriting loop from `scripts/along_version_bump.py`.
5. Corrected `.along/.protocol-version` from stale `2.2.13` to `2.2.27`, restoring `migrate_protocol.py` idempotency, and wired `.along/.protocol-version` into `bump_along_dev_repo()`.
6. Extended `test_04_protocol_version_consistency` in `tests/test_skills_and_scripts.py` to prevent future regressions.
7. Recorded `ADR-2026-09-09--version-ssot-consolidation-and-dynamic-packaging` and closed `debt--consolidate-version-ssot-and-repair-protocol-desync`.

## Initial Implementation Plan (Baseline)
1. **Phase 0 & 1 (Analyze & Research)**: Audit all version definitions across repository and initialize blackboard.
2. **Phase 2 (Architect)**: Design dynamic Hatchling integration and decoupled release workflow.
3. **Phase 3 (Implement)**:
   - Step 1: SSOT & Python packaging (`alongkit/version.py`, `pyproject.toml`, `dashboard/app.py`).
   - Step 2: Skills manifest cleanup & release bumper decoupling (`skills/*/SKILL.md`, `along_version_bump.py`).
   - Step 3: State marker repair & release bumper integration (`.along/.protocol-version`).
   - Step 4: Verification, consistency tests & gate manifest (`test_skills_and_scripts.py`).
4. **Phase 4 & 5 (Review & Reassess)**: Run hermetic test suite and verify migration engine idempotency.
5. **Phase 7 (Finish & Wrap)**: Record ADR, compile session log, update projections, and purge blackboard.

## Execution & Loop Trace (Fixes & Re-plans)
- `[Fix Loop - Test Script Path in Test 04]`: During initial test assertion addition, `os.path.join(REPO_ROOT, name)` dropped the `"scripts"` folder segment, causing `FileNotFoundError` on `along_commit.py`. Repaired path to `os.path.join(REPO_ROOT, "scripts", name)` and verified 337 tests pass.
- `[Fix Loop - Dynamic Wheel Build Verification]`: Verified via scratch script using `hatchling.builders.wheel.WheelBuilder` that `dynamic = ["version"]` correctly extracts `2.2.27` from `scripts/alongkit/version.py`.

## Verification Walkthrough & Gate Manifest
- **Automated Tests**: `python .along/scripts/test.py` -> 337 passed, 0 failed, 1 skipped.
- **Entity Doctor**: `python scripts/along_exec.py doctor --entities` -> 0 errors, 0 warnings across 172 entities.
- **Typography Check**: `python scripts/along_exec.py sanitize` -> 305 files scanned, 0 violations.
- **Migration Idempotency**: `python scripts/migrate_protocol.py . --dry-run` -> `Already at v2.2.27; nothing to do.`
- **Wheel Build Dynamic Metadata**: `hatchling.builders.wheel.WheelBuilder(".").metadata.version` -> `2.2.27`.

[CRITICAL WARNING: code-review-graph OFFLINE, degraded to static search]

Gate Execution Manifest:
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [test.py: 337/337]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-1 to REQ-6]
- Blast Radius: DEGRADED (PASS) [static search, code-review-graph offline/timed out]
- Documentation Parity: EXECUTED (PASS)
- Clean Typography: EXECUTED (PASS)
