---
protocol: along
protocol_version: "4.9.1"
slug: session-hierarchy-and-submodule-automation
type: feat
status: done
completed: 2026-11-22
priority: medium
created: 2026-11-22
updated: 2026-11-22
agent: antigravity
tags: [sessions, subprojects, submodules, update]
milestone: v5.0.0-agent-run-protocol-and-observability
blocked_by: []
related: [bug--engine-atomicity-and-gate-resilience]
plan_status: approved
---

# Umbrella session hierarchy and automated submodule protocol updates

## Problem
Working across monorepo boundaries and nested git submodules under Along v4.9.1 introduces severe workflow friction:
1. Flat single-issue binding: A session can only bind to a single issue in one subproject. Subagents or workflows touching root and submodules are repeatedly blocked by `subproject-boundary` gates. `along start` also refuses to switch or start on a dirty working tree even when dirty files belong to the active tree of work.
2. Unautomated submodule protocol updates: Running `along update` modifies protocol files (`AGENTS.md`, `PROTOCOL.md`, `.protocol-version`, etc.) across all submodules. Committing these requires manual per-submodule interventions and fails the `commit-issue-binding` gate unless a dummy issue is created in each submodule.
3. Silent `.gitattributes` driver changes: Protocol migrations modify merge drivers without explicit warnings in update outputs or release notes.

## Requirements
- REQ-1: Umbrella Session Inheritance: The session engine MUST support umbrella issues that declare child issues across subprojects via `children:`. A session bound to an umbrella issue automatically authorizes edits to declared child entities across subproject boundaries without re-binding.
- REQ-2: Smart Dirty Tree Handling: `along start` MUST permit starting work without explicit `--allow-dirty` if the uncommitted modifications in the tree belong to the issue or its declared umbrella hierarchy.
- REQ-3: Submodule Protocol Auto-Commit: `along update` MUST support a `--commit` flag (or `along protocol commit`) that automatically commits protocol-managed files in each dirty submodule with a standardized `chore(along): protocol vX.Y.Z` message, exempt from `commit-issue-binding`.
- REQ-4: Merge Driver Transparency: `along update` MUST print any changes made to `.gitattributes` merge drivers in its summary output and log the rationale.

## Acceptance Criteria
- [x] Session binding to an umbrella issue permits subagents and commands to edit declared child issues across subprojects
- [x] `along start` allows dirty trees when dirty files are attributed to the target issue or umbrella tree
- [x] `along update --commit` commits protocol-owned files across all touched submodules under `chore(along): ...`
- [x] Changes to merge drivers in `.gitattributes` are explicitly reported in the `along update` console output
- [x] Automated tests in `tests/` verifying umbrella hierarchy binding and submodule auto-commit
