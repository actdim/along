---
protocol: along
protocol_version: "4.5.1"
slug: release-v4-5-1
type: task
status: done
completed: 2026-10-21
priority: high
created: 2026-10-21
updated: 2026-10-21
agent: antigravity
milestone: v4.5.1-entity-model-slimming-and-hotfixes
tags: [release, hotfix, entities]
blocked_by: []
related: [debt--entity-model-slimming, bug--wrap-misses-engine-writes, bug--along-issue-sync-frontmatter-quotes]
---

# Release Along v4.5.1: Entity model slimming, wrap engine writes fix, and skill frontmatter hotfix

## Requirements

- REQ-1: Consolidate entity model per ADR-2026-10-19 (retire risks and checklists, spike as issue type, migration Step 16).
- REQ-2: Fix `along wrap` and session close auto-commit for engine-refreshed managed files (`docs/topic--along-protocol.md`, `AGENTS.md`).
- REQ-3: Fix YAML frontmatter parsing defect in `skills/along-issue-sync/SKILL.md` (quoted `description` string).
- REQ-4: Ensure full automated test suite passes.
- REQ-5: Release v4.5.1 via `along bump patch`, update CHANGELOG.md, and create tag `v4.5.1`.
- REQ-6: Push release commits and tag to remote repository.
- REQ-7: Update global installation (`install.ps1 -Target all`).

## Acceptance Criteria

- [x] Entity model slimming implemented, covered by tests, and migrated.
- [x] Engine-refreshed files committed cleanly during wrap.
- [x] Frontmatter in `skills/along-issue-sync/SKILL.md` parses cleanly with strict YAML parsers.
- [x] Full automated test suite passing (1440 tests OK).
- [x] Release v4.5.1 committed and tagged with `v4.5.1`.
- [x] Pushed to remote repository (`origin/main`, tag `v4.5.1`).
- [x] Global installation verified and updated.
