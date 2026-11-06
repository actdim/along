---
protocol: along
protocol_version: "4.6.0"
slug: cross-repo-entity-references
type: feat
status: done
completed: 2026-11-06
priority: medium
created: 2026-11-05
updated: 2026-11-06
agent: antigravity
tags: [entities, subprojects, submodules, graph]
blocked_by: []
related: []
plan_status: needs-approval
---

# Cross-repo and submodule entity references

Support qualified entity references across repositories and subprojects (such as `parent: <subproject-path>:<key>` and `children:` / `related: <subproject-path>:<key>`). Currently, entity reference validation only supports resolving upward ancestor root references (`root:<key>`); references pointing down into submodules or across sibling subprojects fail validation and trigger `[gate: entity-reference-integrity]`.

## Requirements
- REQ-1: Support path-qualified entity references in the format `<subproject-path>:<entity-key>` across entity relation fields (`parent`, `related`, `blocked_by`, `children`).
- REQ-2: `_resolve_ref` and `validate_entities` in `alongkit.entities` MUST resolve `<subproject-path>:<key>` by checking the target subproject's `.along/` context.
- REQ-3: If `<subproject-path>` points to an uninitialized Git submodule or missing path, `along doctor --entities` and git gates MUST emit a warning rather than crashing or blocking turns with a fatal integrity violation.
- REQ-4: `compile_issues_board` and `along issue sync` MUST render linked subproject child issues on superproject umbrella issues under an `### External Subproject Children` section.
- REQ-5: Hermetic unit tests in `tests/test_cross_repo_entities.py` testing cross-context reference validation, dangling link detection, and projection board rendering.

## Acceptance Criteria
- [x] Qualified entity references `<subproject-path>:<key>` parse and resolve in entity query helpers.
- [x] `validate_entities` respects subproject entity references without dangling false alarms.
- [x] Projection board renders external child issues under umbrella tickets.
- [x] Hermetic tests pass cleanly.
