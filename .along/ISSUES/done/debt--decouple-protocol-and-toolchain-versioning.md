---
protocol: along
protocol_version: "4.9.1"
slug: decouple-protocol-and-toolchain-versioning
type: debt
status: done
completed: 2026-11-27
priority: high
created: 2026-11-24
updated: 2026-11-27
agent: antigravity
tags: [version, protocol, toolchain, release, packaging, debt]
blocked_by: []
related: [debt--consolidate-version-ssot-and-repair-protocol-desync]
plan_status: approved
---

# Decouple repository protocol specification version from toolchain package version

## Problem
In `scripts/alongkit/version.py`, `CURRENT_VERSION` is hardcoded as an alias to `CURRENT_PROTOCOL_VERSION` (`CURRENT_VERSION = CURRENT_PROTOCOL_VERSION = "4.9.1"`). Furthermore, `pyproject.toml` uses a `[tool.hatch.version]` pattern extracting `CURRENT_PROTOCOL_VERSION`, and `scripts/along_version_bump.py` treats toolchain patch/minor bumps as protocol bumps.

This directly violates the Protocol Versioning Policy in `VISION.md`:
1. Protocol specification version (`ALONG-PROTOCOL vX.Y.Z`) MUST increment only on format, schema, or structural protocol changes.
2. Toolchain features, bug fixes, and non-breaking capabilities MUST release as toolchain versions without mutating protocol specification headers across the repository.
3. Coupling them causes cascading provenance drift in `docs/topic--*.md` on every minor toolchain patch, and forces false-positive migration warnings in `along update` and `along doctor`.

## Requirements
- REQ-1: `scripts/alongkit/version.py` MUST decouple `CURRENT_VERSION` (toolchain package SemVer) and `CURRENT_PROTOCOL_VERSION` (protocol specification SemVer) into independent constants, and export both in `scripts/alongkit/__init__.py`.
- REQ-2: `pyproject.toml` `[tool.hatch.version]` pattern MUST extract `CURRENT_VERSION`, not `CURRENT_PROTOCOL_VERSION`.
- REQ-3: `scripts/along_version_bump.py` MUST migrate to `argparse`, support `--protocol [patch|minor|major|<ver>]`, and:
  - By default (toolchain bump): resolve base version from `version.CURRENT_VERSION`, update `CURRENT_VERSION` in `scripts/alongkit/version.py`, update `package.json` files, update `# ActDim Along (vX.Y.Z)` in `README.md` and `llms.txt`, and update milestones. It MUST NOT touch `CURRENT_PROTOCOL_VERSION`, `.along/.protocol-version`, `AGENTS.md`, or protocol headers.
  - When `--protocol` is passed: resolve base version from `version.CURRENT_PROTOCOL_VERSION`, update `CURRENT_PROTOCOL_VERSION` in `scripts/alongkit/version.py`, write `.along/.protocol-version`, update `# ALONG-PROTOCOL vX.Y.Z` in `AGENTS.md` and `skills/along-init/protocol.md`.
- REQ-4: Dead version regex substitutions in `scripts/along_version_bump.py` targeting engines that import `version.py` MUST be removed.
- REQ-5: `scripts/alongkit/version.py` MUST define `MIN_SUPPORTED_PROTOCOL_VERSION` and `is_protocol_supported(ver)` for SemVer-based protocol compatibility checks. `scripts/alongkit/commands/doctor.py` MUST preserve subproject-to-root skew detection while checking root against supported protocol ranges.
- REQ-6: Unit tests across `test_skills_and_scripts.py` (`test_04`, `test_04d`), `test_version_bump.py` (including a hermetic dev-repo fixture test), and `test_migration.py` MUST pass cleanly without regressions.

## Acceptance Criteria
- [x] `CURRENT_VERSION` and `CURRENT_PROTOCOL_VERSION` are distinct constants in `scripts/alongkit/version.py` and exported by `alongkit/__init__.py`.
- [x] `pyproject.toml` hatch pattern resolves package version from `CURRENT_VERSION`.
- [x] `along version-bump patch` increments `CURRENT_VERSION` without modifying `CURRENT_PROTOCOL_VERSION`, `.along/.protocol-version`, or `AGENTS.md`.
- [x] `along version-bump --protocol <type>` increments `CURRENT_PROTOCOL_VERSION`, updates `.along/.protocol-version`, and updates `AGENTS.md`.
- [x] Dead regex substitutions are pruned from `along_version_bump.py`.
- [x] `along --version` outputs both toolchain and protocol versions (`along <toolchain> (protocol v<protocol>)`).
- [x] Hermetic tests for dev-repo version bump (both toolchain and protocol modes) are added to `tests/test_version_bump.py`.
- [x] `test_04_protocol_version_consistency` validates README header against toolchain version and AGENTS.md against protocol version.
- [x] `python .along/scripts/test.py` passes.
