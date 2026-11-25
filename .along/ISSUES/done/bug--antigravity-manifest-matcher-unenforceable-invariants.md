---
protocol: along
protocol_version: "4.9.1"
slug: antigravity-manifest-matcher-unenforceable-invariants
title: "Antigravity hook matcher excludes the tools its own invariant gates declare"
type: bug
status: done
completed: 2026-11-25
priority: high
created: 2026-11-24
updated: 2026-11-25
agent: dsh
tags: [hooks, gates, antigravity, matcher, containment, invariants]
blocked_by: []
related: []
plan_status: approved
---

# Antigravity hook matcher excludes the tools its own invariant gates declare

## Problem

The Antigravity hook manifest admits only three tool names:

```yaml
# scripts/alongkit/hooks/config.py:348 and :360
matcher: "write_to_file|replace_file_content|run_command"
```

A runtime starts `along_hook.py` only for a tool name its matcher admits, so any gate whose
`tools:` list names something outside that triple never evaluates in Antigravity. Two of the
affected gates are `tier: invariant`, which the protocol defines as always enforced and
impossible to shadow:

- `workspace_containment` (`scripts/alongkit/hooks/default_gates.yaml:330`) declares
  `view_file`, `read_file`, `view_image`, `list_dir`, `list_directory`, `grep_search`, `grep`,
  `find_by_name`, `find_files`, `file_search` besides the shell tools.
- `entity_deletion_protection` (`default_gates.yaml:283`) declares `delete_file`,
  `remove_file`, `unlink`, `delete`, `file_delete`, `remove`.

Measured consequence: in Antigravity, a read of `~/.ssh/id_ed25519` never reaches
`containment.violations()`, so the credential-store ban that `AGENTS.md` states as
`[gate: workspace-containment]` is not mechanical there, and deleting an issue or ADR file is
not held by `[gate: entity-deletion-protection]`. The same class of gap exists in the sibling
manifests: the Codex matcher (`config.py:575`, `:581`) lists writes and shells only, and the
Cursor manifest (`config.py:545`) has no matcher at all, so its payloads reach
`GenericCliAdapter`, whose `TOOL_NAME_MAP` does not know Cursor's own names.

The docs state the enforcement layer honestly (`docs/topic--runtime-hooks-and-gates.md:340`),
so this is not a documentation lie; it is a manifest that is narrower than the catalogue it
serves.

## Requirements

- REQ-1: Each runtime manifest matcher MUST be a superset of the union of the `tools:` lists
  of every catalogue gate whose `enforcement` includes `runtime`.
- REQ-2: A hermetic test MUST derive that union from `default_gates.yaml` and assert the
  superset relation for every installed runtime, so adding a gate tool cannot silently fall
  out of a matcher.
- REQ-3: A payload-level test MUST feed a `view_file` of a credential path and a
  `delete_file` of an issue file through `along_hook.py --runtime antigravity` and assert the
  gate fires, not merely that `check_workspace_containment` returns a string when called
  directly (the existing `tests/test_workspace_containment.py` calls the predicate, which
  bypasses the matcher).
- REQ-4: Where a runtime genuinely cannot express a tool name (Cursor today), the narrowing
  MUST be recorded in the manifest and reported by `along doctor`, not left implicit.

## Acceptance Criteria

- [x] `get_antigravity_hook_manifest()` matcher is a superset of the runtime gate tool union.
- [x] A hermetic test fails if a new gate names a tool absent from an installed matcher.
- [x] A `view_file` payload for a credential store is denied under `--runtime antigravity`.
- [x] A `delete_file` payload for `.along/ISSUES/*.md` is denied under `--runtime antigravity`.
- [x] Cursor's narrowing is either closed or reported by `along doctor`.

## Evidence

- Matcher: `scripts/alongkit/hooks/config.py:348`, `:360`; Codex `:575`, `:581`; Cursor `:545`.
- Gate tool lists: `scripts/alongkit/hooks/default_gates.yaml:339` (`workspace_containment`),
  `:293` (`entity_deletion_protection`).
- Predicate reachable only after the hook starts: `scripts/alongkit/hooks/containment.py`.
- Not covered today: `tests/test_update_and_hooks_hardening.py` asserts the command string
  only; `tests/test_workspace_containment.py` calls the predicate directly.
