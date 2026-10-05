---
protocol: along
protocol_version: "4.4.5"
slug: migration-dangling-template-milestones
type: bug
status: done
completed: 2026-10-05
priority: high
created: 2026-10-05
updated: 2026-10-05
agent: claude-code
tags: [migration, entities]
blocked_by: []
related: [bug--entity-refs-ignore-nested-contexts, bug--entity-gate-blocks-preexisting-problems]
---

# Migration writes milestone references to files it never created

## Problem
Step 3 of `migrate_protocol.py` (`_v1_5_synthesize_milestones_from_history`) writes the
template milestones `v1.3.0-knowledge-base-and-graph` and `v2.0.0-along-transition` only
when `.along/MILESTONES/` is empty. `_v1_5_enrich_issues_frontmatter` assigns them to every
issue without a milestone unconditionally, and `_v1_5_enrich_sessions_frontmatter` sets
`milestone: v2.0.0-along-transition` on every session log without one. A repository that
already has any milestone file gets dangling references on every closed issue, and every
re-run of the chain (each protocol upgrade) adds them to newly closed issues.

The `v1.3.0` template also carries Along's own release history (title and body), which
does not belong in a consumer repository.

## Requirements
- REQ-1: Migration never assigns a milestone that does not exist; issues and sessions
  without a milestone keep the field unset.
- REQ-2: Migration no longer synthesizes milestones from Along's own history.
- REQ-3: Re-running the chain is idempotent for `milestone`, and it removes the two
  template references from issues and sessions when their milestone file does not exist.
- REQ-4: `along doctor --entities --fix` removes `milestone` fields that resolve to no
  milestone (issues and session logs) and reports what it changed.
- REQ-5: Tests: a fixture with one existing milestone and a closed issue without one
  migrates with zero `dangling milestone` errors; a fixture already carrying a dangling
  template reference is repaired; `doctor --fix` clears an arbitrary dangling milestone.

## Acceptance Criteria
- [x] REQ-1..REQ-4 implemented
- [x] REQ-5 tests pass
- [x] Automated tests passing
