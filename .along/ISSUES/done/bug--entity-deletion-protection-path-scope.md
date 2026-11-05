---
protocol: along
protocol_version: "4.6.0"
slug: entity-deletion-protection-path-scope
type: bug
status: done
completed: 2026-11-06
priority: high
created: 2026-11-05
updated: 2026-11-06
agent: antigravity
tags: [gates, entities, hooks]
blocked_by: []
related: []
plan_status: needs-approval
---

# entity-deletion-protection treats non-entity files under .along/ISSUES/ as protected entities

Runtime gate `entity-deletion-protection` (mislabelled as `entity-reference-integrity` in its error message) intercepts file deletion tools and shell commands deleting anything matching `\.along[/\\]+(?:ISSUES|DECISIONS|MILESTONES)(?:[/\\]|$)`. This prevents agents and users from deleting non-entity files such as plan drafts, scratch files, or attachments inside issue subfolders (e.g., `.along/ISSUES/<epic>/plans/14c--old-name.md`).

## Requirements
- REQ-1: `check_entity_deletion_protection` MUST guard only canonical entity files (`.along/ISSUES/<type>--<slug>.md`, `.along/ISSUES/<key>/plan.md`, `.along/DECISIONS/ADR-*.md`, `.along/MILESTONES/<slug>.md`) and must NOT block deletion of non-entity files in issue subdirectories (such as `plans/*` or `attachments/*`).
- REQ-2: The error message returned on deletion denial MUST accurately cite `[gate: entity-deletion-protection]` rather than `[gate: entity-reference-integrity]`.
- REQ-3: `touches_entities` in `gitgates.py` MUST distinguish canonical entity files from arbitrary nested files inside issue directories.
- REQ-4: Add hermetic unit tests covering file-tool deletion and shell command deletion for both protected entity files and allowed non-entity attachments.

## Acceptance Criteria
- [x] Canonical entity files and plans remain guarded against deletion.
- [x] Non-entity draft plans and attachments in issue subfolders are allowed to be removed.
- [x] Error message cites `[gate: entity-deletion-protection]`.
- [x] All hermetic tests pass cleanly.
