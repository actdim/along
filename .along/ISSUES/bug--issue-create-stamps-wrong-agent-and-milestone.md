---
protocol: along
protocol_version: 2.2.8
slug: issue-create-stamps-wrong-agent-and-milestone
type: bug
status: open
priority: high
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [along-exec, entity-generator, metadata, dangling-reference]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [issue-done-corrupts-status-and-drops-completed, entity-status-enum-and-unused-taxonomy]
parent: protocol-quality-audit-remediation
---

# issue create hardcodes the agent name and stamps a milestone that does not exist

## Problem 1: `agent` is hardcoded to a single provider

`along_exec.py` `handle_issue_command` -> `create` writes a template with
`agent: antigravity` regardless of which tool is running. Observed directly:

```text
python scripts/along_exec.py issue create bug adr-retrieval-blind-to-slug-headers ...
-> Created issue: .along/ISSUES/bug--adr-retrieval-blind-to-slug-headers.md

# resulting front-matter
agent: antigravity        <- created by claude-code
```

The `agent` field is defined in `AGENTS.md` as "model or tool name (e.g. `antigravity`,
`claude-code`)". For a product whose primary claim is provider agnosticism, the entity
generator attributing every issue to one specific provider corrupts the attribution data
that dashboards and history reconstruction consume.

## Problem 2: `milestone` points at a non-existent file

The same template stamps `milestone: v2.1.0-along`. Existing milestones:

```text
.along/MILESTONES/v1.0.0-initial-architecture.md
.along/MILESTONES/v1.1.0-antigravity-support-and-issues-model.md
.along/MILESTONES/v1.3.0-knowledge-base-and-graph.md
.along/MILESTONES/v1.5.0-dashboard-and-analytics.md
.along/MILESTONES/v2.0.0-along-transition.md
```

There is no `v2.1.0-along`. Every issue created by the CLI therefore carries a dangling
milestone reference. `AGENTS.md` requires entity references to be canonical keys that
resolve, and milestone progress reconciliation
(`along_version_bump.py:403-414`) matches milestones by filename, so these references are
silently inert.

### Scope of the existing damage

A reference sweep across all 71 entities on 2026-09-01 found every `parent`, `related`,
`blocked_by`, and inline citation resolving correctly, and **14 dangling milestone
references** pointing at three milestones that were never created:

```text
v2.1.0-along       9 issues
v2.2.0-along       5 issues   (entire v2.2.x line tracked against a non-existent milestone)
v2.1.0-wiki-llm    1 issue
```

Existing milestone files: `v1.0.0-initial-architecture`, `v1.1.0-antigravity-support-and-issues-model`,
`v1.3.0-knowledge-base-and-graph`, `v1.5.0-dashboard-and-analytics`, `v2.0.0-along-transition`,
`v3.0.0-global-quality-revision`.

So the whole v2.1 and v2.2 release history has no milestone entity, which means milestone
progress, release grouping, and any roadmap view derived from milestones are empty for those
versions. Two issues closed during this audit initially inherited the same phantom
`v2.2.0-along` by convention and were repointed to `v3.0.0-global-quality-revision`; the other
12 are historical and need a decision (create the missing milestone files retroactively, or
clear the field).

## Problem 3: no validation of enumerated fields

The generator accepts arbitrary values:

- `type` is taken verbatim from `argv`, so `issue create feature my-slug` produces
  `type: feature`, outside the documented enum (`feat | bug | debt | task | docs`), and the
  filename becomes `feature--my-slug.md`.
- `priority` is taken verbatim, so a typo yields `priority: hihg`.
- No check that the slug is 2-5 kebab-case words as the protocol specifies.
- No check for an existing issue with the same slug in `ISSUES/` or `ISSUES/done/`.

## Problem 4: missing `protocol_version`

The template omits `protocol_version`, which `AGENTS.md` documents as optional but which
`docs/` articles require. The result is inconsistent stamping across entity types.

## Impact

Every entity created through the protocol's own deterministic CLI starts with wrong
attribution, a dangling milestone link, and no schema validation. Since the CLI is the
documented "deterministic entity execution" path that agents are instructed to prefer over
hand-editing, the defects propagate into all project memory.

## Requirements

- REQ-1: Determine `agent` at runtime. Accept `--agent <name>`; otherwise infer from
  environment (for example an Along-set env var or provider-specific markers) and fall back
  to `unknown` rather than a hardcoded provider name.
- REQ-2: Do not stamp `milestone` unless it is passed explicitly or exactly one milestone has
  `status: in-progress`. Validate that the referenced milestone file exists; refuse with a
  clear message otherwise.
- REQ-3: Validate `type` against the documented enum and `priority` against
  `critical | high | medium | low`; exit non-zero on invalid values listing the allowed set.
- REQ-4: Validate the slug shape and reject a slug that already exists in `ISSUES/` or
  `ISSUES/done/`.
- REQ-5: Stamp `protocol_version` consistently for all generated entities (issues,
  sessions, decisions, milestones, risks, spikes, checklists).
- REQ-6: Add an entity-schema validator subcommand (`along_exec.py doctor --entities`) that
  reports invalid enums, dangling `milestone` / `parent` / `blocked_by` / `related` keys, and
  missing mandatory fields across all entities.
- REQ-7: Tests: created issue has the correct agent; invalid type rejected; dangling
  milestone refused; duplicate slug refused; validator detects a dangling `parent`.

## Acceptance Criteria

- [ ] `agent` reflects the actual tool, never a hardcoded provider.
- [ ] No generated entity carries a dangling milestone reference.
- [ ] Enum and slug validation enforced with non-zero exit codes.
- [ ] `doctor --entities` reports dangling references across the entity graph.
- [ ] All 14 dangling milestone references resolved (missing milestones created or field cleared).
