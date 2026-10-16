---
protocol: along
protocol_version: "4.4.14"
slug: consolidate-dashboard-ui-subproject
type: debt
status: done
completed: 2026-10-16
priority: high
created: 2026-10-16
updated: 2026-10-16
agent: antigravity
tags: [monorepo, consolidation, subprojects, dashboard-ui]
blocked_by: []
related: [bug--subproject-model-overdetection]
---

# Consolidate packages/dashboard-ui subproject into repository root

## Problem

In early protocol versions, package manifests triggered automated subproject creation, creating an isolated `packages/dashboard-ui/.along/` context without an independent Git repository or submodule. Following ADR-2026-10-06, subproject boundaries are strictly nested `.git` roots or explicit user initializations. Having an orphaned nested `.along/` in `packages/dashboard-ui` fragments project memory, triggers `along doctor` warnings, and complicates cross-component development.

## Requirements

- REQ-1: Migrate completed issues and sessions from `packages/dashboard-ui/.along/` into root `.along/` without data loss or slug collisions.
- REQ-2: Update `packages/dashboard-ui/AGENTS.md` to reference root rules and remove obsolete subproject context markers.
- REQ-3: Remove the redundant `packages/dashboard-ui/.along/` directory.
- REQ-4: Recompile root projections (`.along/ISSUES.md`, `docs/INDEX.md`) and verify zero errors in `along doctor` and automated test suites.

## Acceptance Criteria

- [x] Completed issues and sessions moved to root `.along/`.
- [x] `packages/dashboard-ui/.along/` cleanly removed from Git and filesystem.
- [x] `along doctor` reports 0 nested contexts and 0 errors.
- [x] `python .along/scripts/test.py` and `pnpm test` pass cleanly.
