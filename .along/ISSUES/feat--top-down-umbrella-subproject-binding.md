---
protocol: along
protocol_version: "4.8.0"
slug: top-down-umbrella-subproject-binding
type: feat
status: open
priority: high
created: 2026-11-10
updated: 2026-11-10
agent: antigravity
tags: [subproject, gates, umbrella, submodule]
blocked_by: []
related: [feat--cross-repo-entity-references, feat--subproject-boundary-by-active-issue]
---

# Top-down umbrella and child issues across superproject and submodules

## Problem

A superproject and a nested Git submodule with its own `AGENTS.md` and `.along/` cannot hold a working umbrella and child pair of issues when the submodule forbids cross-repo `parent:` references (for standalone submodule portability and repository decoupling).

Currently, gate `subproject-boundary` (`predicates.py`) only recognizes child-to-parent linkage bottom-up:
1. `_subproject_issue_ok` scans all issues in `context_root`'s `ISSUES/` to check whether `root_slug in _parent_chain_slugs(context_root, child)`. If the child issue does not define `parent: <root-key>`, source edits in the submodule are denied while bound to the root umbrella issue.
2. `_bound_subproject_owns_root_entity` only permits writing to a root issue ticket if the root ticket is in the bound issue's `_parent_chain_slugs`.
3. In standalone checkouts of a submodule, any hard `parent: root:<key>` reference causes `validate_entities` to fail with a dangling parent error because the parent context does not exist.

As a result, agents working across superprojects and submodules must repeatedly switch session binding (`along start <root>` and `along start <child>`), or violate submodule isolation rules.

## Requirements

- REQ-1 (Top-Down Children Declaration): An umbrella issue in a superproject context MUST be able to declare its child subproject issues via a `children:` list field using path-qualified keys (e.g. `children: [src/submodule:task--child]`).
- REQ-2 (Subproject Gate Top-Down Authorization): Gate `subproject-boundary` (`predicates._subproject_issue_ok`) MUST permit source modifications in a subproject if the currently bound root umbrella issue lists an issue of that subproject in its `children:` field.
- REQ-3 (Root Entity Modification by Child): Gate `subproject-boundary` (`predicates._bound_subproject_owns_root_entity`) MUST permit writing to a root umbrella issue or its issue folder when the session is bound to a submodule child listed in the root issue's `children:` field.
- REQ-4 (Entity Vocabulary and Validation):
  - Add `children` to `REFERENCE_FIELDS` in `alongkit.entities.vocabulary` and `_DELETE_BLOCKING_FIELDS` in `alongkit.entities.mutation`.
  - Validate `children` entries in `alongkit.entities.validation.validate_entities` across subproject contexts.
  - In `alongkit.entities.query.resolve_entity_reference`: if a reference is qualified with `root:` but the repository has no enclosing context (standalone clone), emit a non-blocking diagnostic warning instead of a blocking dangling error.
- REQ-5 (Remedy Alignment): The violation text in `subproject-boundary` MUST present both bottom-up (`parent:`) and top-down (`children:`) remedies.
- REQ-6 (Hermetic Tests): Regression and unit tests MUST cover top-down umbrella authorization, bidirectional write permissions, standalone submodule validation, and typography rules.

## Acceptance Criteria

- [ ] Superproject issue declaring `children: [<sub>:<child-key>]` allows source edits in `<sub>` without requiring `parent:` in `<sub>`'s issue.
- [ ] Submodule session bound to a listed child issue is permitted to edit the root umbrella issue ticket and its issue folder.
- [ ] Submodule issue declaring `parent: root:<key>` or `umbrella: root:<key>` produces non-blocking warnings in a standalone clone.
- [ ] `along doctor --entities` and `along issue sync` validate `children` references accurately.
- [ ] Hermetic tests pass cleanly.
