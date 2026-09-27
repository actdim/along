---
protocol: along
protocol_version: "4.1.0"
slug: milestone-version-uniqueness-gate
type: feat
status: done
completed: 2026-09-27
priority: high
created: 2026-09-27
updated: 2026-09-27
agent: antigravity
tags: [milestones, semver, validation, entity-integrity, doctor, quality-gate]
milestone: v4.2.0-monorepo-subprojects
blocked_by: []
related: []
---

# Milestone Version Uniqueness Validation & SemVer Collision Gate

## Goal
Enforce SemVer version uniqueness across project milestones in `alongkit.entities.validate_entities` and CLI creation commands, preventing architectural anti-patterns where multiple active milestones share identical versions or minor version prefixes.

## Problem Statement
When roadmaps grow, teams or agents occasionally create multiple milestone files with the same version prefix (such as `v5.0.0-a.md` and `v5.0.0-b.md`), conflating shippable release boundaries with thematic feature tracks (which should be Epics).
This causes:
1. Ambiguities during automated version bumping (`along_version_bump.py`).
2. Indeterminism in active milestone resolution (`resolve_in_progress_milestone`).
3. Violation of SemVer principles where each Git release tag must represent an atomic, unique milestone.

## Technical Specifications

### 1. Entity Validation Engine (`alongkit.entities.validate_entities`)
- Parse SemVer `(major, minor, patch)` from milestone slugs via `alongkit.semver.parse(slug)`.
- For all milestones:
  - Assert that no two milestones have the exact same `(major, minor, patch)` unless both are legacy completed records.
- For all active/open milestones (`status != "completed"`):
  - Enforce minor version uniqueness: no two active milestones may share the same `(major, minor)` tuple. Planned feature milestones must target distinct minor releases (e.g. `5.0`, `5.1`, `5.2`).
- Report collisions as entity errors during `along doctor` and `along milestone sync`.

### 2. Milestone CLI Pre-Flight Guard (`along milestone create`)
- Check target slug against existing milestones before creating a new milestone file.
- Reject creation with a descriptive error if the proposed version collides with an existing active milestone.

## Acceptance Criteria
- [ ] `validate_entities` reports SemVer collisions when duplicate milestone versions are detected.
- [ ] Active milestones sharing `(major, minor)` are blocked with clear actionable messages.
- [ ] Legacy completed milestones do not cause false positives.
- [ ] Hermetic tests verify collision detection and clean reporting.
