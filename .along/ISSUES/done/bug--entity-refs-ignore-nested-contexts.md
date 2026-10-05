---
protocol: along
protocol_version: "4.4.5"
slug: entity-refs-ignore-nested-contexts
type: bug
status: done
completed: 2026-10-05
priority: high
created: 2026-10-05
updated: 2026-10-05
agent: claude-code
tags: [entities, monorepo, gates]
blocked_by: []
related: [bug--migration-dangling-template-milestones, bug--entity-gate-blocks-preexisting-problems]
---

# Entity references to nested subproject contexts are reported as dangling

## Problem
`entities.validate_entities()` resolves references against the current `.along/` plus
`ancestor_entity_keys()` (enclosing contexts up to the git boundary). Entities of nested
subproject contexts (`<sub>/.along/`) are never collected. The subproject-boundary rule
places subproject issues in the nearest `.along/`, so a root epic's `related` /
`blocked_by` and a root session log's `issues_completed` naturally point down into
subprojects - and are always reported as dangling. Upward references work, downward ones
never do. Migration Step 6 uses the same validator, so the migration state marker is never
written in such a monorepo and the whole chain re-runs on every update.

## Requirements
- REQ-1: `descendant_entity_keys(repo_root)` collects entity keys from every nested
  `.along/` below `repo_root` (ISSUES, MILESTONES, DECISIONS, RISKS, SPIKES), skipping
  dependency/build dirs (`repo.IGNORED_DIRS`), `.along/.session`, `.along/.migration-backup`,
  projection files, and nested git repositories (a submodule has its own boundary, just
  as the ancestor walk stops at `.git`).
- REQ-2: `validate_entities(repo_root, ancestors=True, descendants=True)` merges the
  descendant keys into the issue, milestone and entity key sets, so issue references,
  milestone references and session `issues_*` lists resolve downward.
- REQ-3: One walk per `validate_entities` call (no repeated traversal per reference).
- REQ-4: Tests: root issue -> nested issue via `related` / `blocked_by`, root session ->
  nested issue via `issues_completed`, zero errors; a real dangling reference is still
  reported; `descendants=False` restores the old behavior; a nested git repository is not
  entered.

## Acceptance Criteria
- [x] REQ-1..REQ-3 implemented
- [x] REQ-4 tests pass
- [x] Automated tests passing
