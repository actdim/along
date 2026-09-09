---
protocol: along
slug: consolidate-version-ssot-and-repair-protocol-desync
type: debt
status: done
completed: 2026-09-09
priority: critical
created: 2026-09-09
updated: 2026-09-09
agent: antigravity
tags: [version, ssot, packaging, release, protocol-version, debt]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: []
---

# Debt: Consolidate Version Single Source of Truth (SSOT) and Repair Protocol Version Desync

## Problem Statement

The repository suffers from severe version duplication (Shotgun Surgery), requiring updates to 35-50+ files on every version bump:
1. `skills/along-*/SKILL.md` (18 files): each has a version suffix in title (`# Along ... [vX.Y.Z]`).
2. `pyproject.toml`: has hardcoded static `version = "..."`.
3. `dashboard/app.py`: has hardcoded static `version = "..."`.
4. `scripts/along_version_bump.py`: maintains an ad-hoc list of files to rewrite, which missed `.along/.protocol-version`.
5. `.along/.protocol-version`: was stranded at `2.2.13` for 14 releases while the repository advanced to `2.2.27`, causing `migrate_protocol.py` to attempt unnecessary rewrites.

## Remediation Objectives

1. **Establish Single Source of Truth (SSOT)**:
   - `scripts/alongkit/version.py` is the single canonical version definition (`CURRENT_PROTOCOL_VERSION`, `CURRENT_VERSION`, `__version__`).
2. **PEP 621 Dynamic Versioning**:
   - Configure `pyproject.toml` to use `dynamic = ["version"]` resolved via Hatchling regex from `scripts/alongkit/version.py`.
3. **Eliminate Runtime Literal**:
   - `dashboard/app.py` imports `CURRENT_VERSION` directly from `alongkit.version`.
4. **Remove Skill Version Churn**:
   - Strip ` [vX.Y.Z]` title suffixes from all 18 `skills/*/SKILL.md` files; remove the skill rewrite loop in `along_version_bump.py`.
5. **Fix Release Bumper & State Marker**:
   - Include `.along/.protocol-version` in `bump_along_dev_repo()` in `scripts/along_version_bump.py`.
   - Update `.along/.protocol-version` immediately to `2.2.27`.
6. **Enforce Consistency in Tests**:
   - Add assertion in `tests/test_skills_and_scripts.py` verifying `.along/.protocol-version` matches `CURRENT_PROTOCOL_VERSION`.
