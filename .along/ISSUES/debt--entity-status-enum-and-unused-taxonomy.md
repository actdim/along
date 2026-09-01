---
protocol: along
protocol_version: 2.2.8
slug: entity-status-enum-and-unused-taxonomy
type: debt
status: open
priority: medium
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [domain-model, taxonomy, metrics, schema]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [issue-create-stamps-wrong-agent-and-milestone, unpinned-mcp-and-ghost-wiki-query-tool]
parent: protocol-quality-audit-remediation
---

# Entity taxonomy is unused in practice and the status enum cannot express real outcomes

## Problem 1: the type taxonomy is decorative

`AGENTS.md` defines five issue types: `feat | bug | debt | task | docs`. Actual distribution
at audit time (2026-09-01, before this epic):

```text
feat: 39
docs:  1
bug:   0
debt:  0
task:  0
```

Forty issues, thirty-nine of them `feat`, including entries that are plainly bug fixes or
refactors, for example:

- `feat--code-review-graph-resilience-and-windows-mcp-optimization` (a bug fix)
- `feat--installer-junction-fallback-and-dependencies` (a bug fix)
- `feat--centralize-scripts-and-clean-skills-purity` (refactoring / debt)
- `feat--bump-version-skill-and-typography-sanitizer` (mixed)

Since nothing validates the type and agents default to `feat`, every metric derived from
type is meaningless: no bug rate, no debt ratio, no way to answer "what keeps breaking".

## Problem 2: the status enum cannot express common outcomes

Allowed: `open | in-progress | blocked | done`. Real outcomes that have no representation:

- **superseded** - `ISSUES/done/feat--add-sqlite-vector-indexing.md` is marked `done` while
  its body says "Superseded by `feat--integrate-wiki-llm-mcp`". It was never implemented, yet
  it counts as delivered in every "Done" metric.
- **cancelled / wontfix** - decided against.
- **duplicate** - merged into another issue.

Forcing all of these into `done` inflates completion counts and makes the history
untrustworthy: the log says a capability was delivered when it was not. Compare
`[debt--unpinned-mcp-and-ghost-wiki-query-tool]` Problem 3.

## Problem 3: no supersession or duplication links

Front-matter supports `blocked_by`, `related`, and `parent`, but not `supersedes` /
`superseded_by` or `duplicate_of`. ADRs have an explicit supersession convention
("Superseded by ADR-YYYY-MM-DD--slug"); issues do not, so the relationship is recorded only
as prose in the body and is invisible to the DAG and the dashboard.

## Problem 4: no schema validation anywhere

Nothing checks the enums, mandatory fields, or reference resolvability. Two examples found
during this audit: a `status: done-progress` written by the CLI itself
(`[bug--issue-done-corrupts-status-and-drops-completed]`) and a dangling
`milestone: v2.1.0-along` on every generated issue
(`[bug--issue-create-stamps-wrong-agent-and-milestone]`).

## Requirements

- REQ-1: Extend the status enum to `open | in-progress | blocked | done | superseded |
  cancelled | duplicate`, and define which statuses count as delivered for metrics.
  Update `AGENTS.md`, `protocol.md`, `docs/topic--domain-model.md`, the dashboard collector,
  and the projection generator.
- REQ-2: Add `superseded_by` and `duplicate_of` to the front-matter schema, with the same
  canonical-key linking rules as `blocked_by` / `related`.
- REQ-3: Correct the existing misclassified entities: retype obvious bug fixes and refactors
  in `ISSUES/done/`, and set `superseded` where a body says superseded. Record the retyping
  in a session log so history explains the change.
- REQ-4: Implement schema validation (`along_exec.py doctor --entities`, shared with
  `[bug--issue-create-stamps-wrong-agent-and-milestone]` REQ-6) covering enums, mandatory
  fields per status, and reference resolvability.
- REQ-5: Add type-inference assistance at creation: when the description matches bug or
  refactor language, propose the type rather than silently defaulting to `feat`.
- REQ-6: Dashboard and metrics must exclude non-delivered statuses from completion counts,
  and surface a bug/debt ratio once the taxonomy is meaningful.
- REQ-7: Tests: invalid status rejected; `superseded` excluded from delivered counts;
  dangling `superseded_by` detected by the validator.

## Acceptance Criteria

- [ ] Status enum extended and consistently implemented across schema, engines, docs.
- [ ] Supersession and duplication expressible in front-matter.
- [ ] Existing misclassified entities corrected.
- [ ] Entity validator implemented and green.
- [ ] Metrics exclude non-delivered outcomes.
