---
protocol: along
slug: version-ssot-consolidation-and-dynamic-packaging
title: "Single Source of Truth Versioning, PEP 621 Dynamic Hatchling Packaging, and Skill Manifest Decoupling"
date: 2026-09-09
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-09-09--version-ssot-consolidation-and-dynamic-packaging - Single Source of Truth Versioning, PEP 621 Dynamic Hatchling Packaging, and Skill Manifest Decoupling

- Date: 2026-09-09
- Status: accepted
- Context:
  1. The repository suffered from severe version duplication (Shotgun Surgery), requiring updates to 35-50+ files on every version bump.
  2. All 18 skill manifests (`skills/*/SKILL.md`) had redundant version numbers in their titles (`# Along ... [vX.Y.Z]`), even though skills are distributed as a unified package with Along rather than independently.
  3. `pyproject.toml` and `dashboard/app.py` hardcoded static version strings instead of resolving them dynamically from the shared engine module.
  4. `.along/.protocol-version` was omitted from `bump_along_dev_repo()` in `scripts/along_version_bump.py`, causing a 14-release drift (stuck at 2.2.13 while the protocol advanced to 2.2.27) that broke `migrate_protocol.py` idempotency.
- Decision:
  1. **Canonical Python SSOT**: `scripts/alongkit/version.py` is the single source of truth (`CURRENT_PROTOCOL_VERSION`, `CURRENT_VERSION`, `__version__`).
  2. **PEP 621 Dynamic Packaging**: `pyproject.toml` adopts standard `dynamic = ["version"]` resolved via Hatchling regex from `scripts/alongkit/version.py`.
  3. **Runtime Import in Dashboard**: `dashboard/app.py` imports `CURRENT_VERSION` directly from `alongkit.version`.
  4. **Skill Decoupling**: Removed version suffixes from all 18 `skills/*/SKILL.md` titles and eliminated the skill rewriting loop from `along_version_bump.py`.
  5. **State Marker Synchronization**: Added `.along/.protocol-version` to `bump_along_dev_repo()` and added regression tests in `tests/test_skills_and_scripts.py`.
- Consequences:
  - Releases modify only ~5 core files instead of 35-50+ files, eliminating git commit noise and Shotgun Surgery.
  - Zero risk of `.along/.protocol-version` desync across releases.
  - Full backward compatibility with Hatchling wheel builds and test runners.
