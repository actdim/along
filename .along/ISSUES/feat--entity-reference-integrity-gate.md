---
protocol: along
protocol_version: "4.3.0"
slug: entity-reference-integrity-gate
type: feat
status: open
priority: high
created: 2026-09-29
updated: 2026-09-29
agent: claude-code
tags: [entities, integrity, gates, wrap, issue-sync]
milestone: v4.4.0-multi-user-merge-automation
blocked_by: []
related: [feat--kb-search-deterministic-gate-and-skill-hardening, feat--entity-lifecycle-cli-orchestration]
---

# Entity reference integrity gate and reference-rewriting rename/supersede

## Problem Description

The `along update` run on 2026-09-29 surfaced three entity graph errors that had been sitting
unnoticed in `.along/` for up to a week:

1. `feat--code-review-graph-user-skills` had a `related` link to `feat--kb-search-mcp-tool-and-skill-hardening`.
   On 2026-09-23 that issue was deleted by hand and replaced by
   `feat--kb-search-deterministic-gate-and-skill-hardening`. The milestone was updated, but back-references
   in other issues were not.
2. `feat--dashboard-architecture-graph-and-pages-publish` pointed at milestone
   `v4.0.0-dashboard-and-knowledge-base`, which never existed. The work shipped in tag `v4.0.0`
   (`v4.0.0-runtime-gates-and-worktree-isolation`).
3. `feat--secret-scrubbing-in-hooks-and-diagnostics` had `priority: normal`, outside the
   `critical|high|medium|low` enum.

All three were fixed by hand. The root cause is systemic:

- `alongkit.entities.validate_entities` already detects dangling `milestone`, `parent`, `blocked_by`,
  `related`, `superseded_by`, `duplicate_of` and `target_issues` references and enum violations, but it only
  runs from the opt-in `along doctor --entities`. The migration engine's own graph check
  (`migrate_protocol.validate_and_build_entity_graph`) reports dangling links only as a warning.
- None of `/along-wrap`, `/along-commit`, `/along-issue-sync` or the Stop gates run the validation, so entities
  hand-edited by an agent (all three cases above were written by hand, bypassing `along issue create`) are never checked.
- There is no CLI operation to rename, replace or supersede an entity, so an agent deletes the file
  and has to find and rewrite inbound references itself.

## Requirements

- `REQ-1`: Run `validate_entities` as a declarative gate (`default_gates.yaml` + predicate) in the
  wrap and projection-sync stages (`/along-wrap`, `along issue sync`). Errors block in `enforce` mode and warn in `shadow` mode.
- `REQ-2`: `along commit` runs the same check for staged `.along/` entity files and aborts on new
  dangling references or enum violations in them (report pre-existing ones without blocking).
- `REQ-3`: Add `along issue rename <old-key> <new-key>` and `along issue supersede <old-key> --by <new-key>`,
  which rewrite every inbound reference (`related`, `blocked_by`, `parent`, `superseded_by`,
  `duplicate_of`, milestone `target_issues`) in the nearest `.along/`, and in the case of supersede keep the old
  file with `status: superseded` + `superseded_by` instead of deleting it.
- `REQ-4`: Make the migration-engine graph check reuse `validate_entities` instead of its own
  duplicate logic (the `tests/test_alongkit.py` no-duplicates rule).
- `REQ-5`: Anchor the rule in `skills/along-init/protocol.md` / `AGENTS.md` ("never delete an entity
  that other entities reference; use supersede") with a `[gate: ...]` tag for traceability.
- `REQ-6`: Hermetic tests on `tempfile.mkdtemp()` fixtures for the gate, commit check, rename and supersede.

## Acceptance Criteria
- [ ] Wrap / issue-sync gate reports and (in enforce mode) blocks dangling references and enum violations
- [ ] `along commit` rejects newly introduced dangling references in staged entities
- [ ] `along issue rename` and `along issue supersede` rewrite all inbound references
- [ ] Migration engine uses the shared validator; no duplicated logic
- [ ] Protocol rule anchored and `along hook verify --strict` passes
- [ ] `along doctor --entities` is clean on the live repo
- [ ] Automated tests passing
