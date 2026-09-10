---
protocol: along
date: 2026-09-09
slug: migration-version-cleanup-and-kb-schema-decoupling
agent: antigravity
branch: main
commit: pending
summary: "Implemented Step 10 in migration engine to clean up legacy protocol_version in docs/ and version suffixes in skills, decoupled docs/*.md and docs/INDEX.md from version bump churn, harmonized protocol specification (protocol: along mandatory, protocol_version optional at creation), updated consistency tests, and added regression test."
milestone: v3.0.0-global-quality-revision
issues_advanced: []
issues_completed: [debt--migration-version-cleanup-and-kb-schema-decoupling]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Migration Version Cleanup, KB Front-matter Schema Decoupling, and Idempotency

## Summary
Addressed documentation version churn and automated legacy version cleanup during migration:
1. Decoupled `docs/*.md` from version churn: in `scripts/along_kb_sync.py`, removed automatic injection and forced updating of `protocol_version` during synchronization, and ensured `docs/INDEX.md` preserves its original `created` timestamp and omits hardcoded `protocol_version`.
2. Implemented Step 10 in `scripts/migrate_protocol.py` (`step_migrate_v3_0_version_ssot_cleanup`) for repositories migrating to `< 3.0.0`:
   - Strips legacy `protocol_version` from `docs/*.md` front-matter while preserving mandatory `protocol: along`.
   - Strips legacy ` [vX.Y.Z]` title suffixes from local `skills/*/SKILL.md` manifests.
3. Harmonized protocol specification in `skills/along-init/protocol.md` and `AGENTS.md`: `protocol: along` is mandatory; `protocol_version` is optional at creation (stamped at creation only, matching `ISSUES/` standard).
4. Updated `test_04d` in `tests/test_skills_and_scripts.py` to assert mandatory `protocol: along` across all `docs/*.md` while allowing version decoupling.
5. Added comprehensive regression and idempotency test `test_step_10_version_ssot_cleanup` to `tests/test_migration.py`.
6. Documented Step 10 in `docs/topic--migrations.md`.
7. Closed tracking issue `debt--migration-version-cleanup-and-kb-schema-decoupling` and purged session blackboard.

## Initial Implementation Plan (Baseline)
1. **Phase 1 (Step 1)**: Decouple KB Sync from Version Churn & Harmonize Protocol Specification (`scripts/along_kb_sync.py`, `skills/along-init/protocol.md`, `AGENTS.md`).
2. **Phase 2 (Step 2)**: Add Step 10 to Protocol Migration Engine (`scripts/migrate_protocol.py`).
3. **Phase 3 (Step 3)**: Update Consistency Tests & Regression Suite (`tests/test_skills_and_scripts.py`, `tests/test_migration.py`, `docs/topic--migrations.md`).

## Execution & Loop Trace (Fixes & Re-plans)
- `[Hermetic Suite Working Tree Check]`: The hermetic working tree check (`test_zz_hermetic_suite.py`) caught an in-flight modification to `tests/test_migration.py` during an initial test run. Completed file edits statically and re-ran the full suite cleanly (338 passed).
- `[Fixture Regeneration Count in Test 10]`: Noted that `along_kb_sync.py` in Step 7 regenerates `INDEX.md` without `protocol_version` before Step 10 executes. Added a second topic fixture `topic--extra.md` to ensure Step 10 explicitly exercises multi-document `protocol_version` removal.

## Verification Walkthrough & Gate Manifest
- **Automated Tests**: `python .along/scripts/test.py` -> 338 passed, 0 failed, 1 skipped.
- **Entity Doctor**: `python scripts/along_exec.py doctor --entities` -> 0 errors, 0 warnings across 174 entities.
- **Typography Check**: `python scripts/along_exec.py sanitize` -> 307 files scanned, 0 violations.
- **Migration Idempotency**: `python scripts/migrate_protocol.py . --dry-run` -> `Already at v2.2.27; nothing to do.`
- **Migration Force Dry Run**: `python scripts/migrate_protocol.py . --dry-run --force` -> Step 10 confirms: `docs/ front-matter is clean; no protocol_version churn detected.`

[CRITICAL WARNING: code-review-graph OFFLINE, degraded to static search]

Gate Execution Manifest:
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [test.py: 338/338]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS)
- Blast Radius: DEGRADED (PASS) [static search, code-review-graph offline/timed out]
- Documentation Parity: EXECUTED (PASS)
- Clean Typography: EXECUTED (PASS)
