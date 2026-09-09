---
protocol: along
slug: migration-version-cleanup-and-kb-schema-decoupling
type: debt
status: done
completed: 2026-09-09
priority: high
created: 2026-09-09
updated: 2026-09-09
agent: antigravity
tags: [migration, kb-sync, version, schema, debt]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [debt--consolidate-version-ssot-and-repair-protocol-desync]
---

# Debt: Migration Version Cleanup, KB Front-matter Schema Decoupling, and Idempotency

## Problem Statement

Following the consolidation of version declarations into a single Python SSOT:
1. `scripts/along_kb_sync.py` still contains legacy logic forcing `protocol_version: "2.2.27"` into all `docs/topic--*.md` articles during every sync, causing unnecessary diffs and file churn on version bumps.
2. Existing repositories migrating to `v3.0.0` retain hardcoded `protocol_version` in `docs/` and `[vX.Y.Z]` title suffixes in local `skills/*/SKILL.md` without an automated migration step to clean them up.
3. `AGENTS.md` and `skills/along-init/protocol.md` still state that `protocol_version` is mandatory in `docs/*.md`, whereas `protocol: along` is the only truly mandatory namespace marker.

## Remediation Objectives

1. **Decouple KB Sync from Version Churn**:
   - In `scripts/along_kb_sync.py`, remove automatic injection/updating of `protocol_version` into existing `docs/topic--*.md` articles.
2. **Add Step 10 to Protocol Migration Engine**:
   - In `scripts/migrate_protocol.py`, implement `step_migrate_v3_0_version_ssot_cleanup()` for versions `< 3.0.0`:
     - Strip legacy `protocol_version` from `docs/topic--*.md` and `docs/INDEX.md` front-matter while preserving `protocol: along`.
     - Strip ` [vX.Y.Z]` title suffixes from any local `skills/*/SKILL.md` manifests.
3. **Harmonize Protocol Specification**:
   - In `skills/along-init/protocol.md` and `AGENTS.md`, align the `docs/*.md` front-matter specification with `ISSUES`: `protocol: along` is mandatory; `protocol_version` is optional at creation.
4. **Update Consistency Tests**:
   - In `tests/test_skills_and_scripts.py`, update `test_04d` to verify that `protocol: along` is present across all `docs/*.md` and that articles are decoupled from version bump churn.
   - In `tests/test_migration.py`, add regression test verifying Step 10 execution on fixture repos.
