---
protocol: along
protocol_version: 2.2.8
date: 2026-09-01
slug: quality-audit-and-remediation-plan
agent: claude-code
branch: main
commit: pending
summary: Critical repository audit, two P0/P1 fixes with regression tests, and a full 28-issue remediation plan under the new v3.0.0 global quality revision milestone
milestone: v3.0.0-global-quality-revision
issues_advanced: [protocol-quality-audit-remediation]
issues_completed: [adr-retrieval-blind-to-slug-headers, issue-done-corrupts-status-and-drops-completed]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Critical Quality Audit, First Fixes, and the v3.0.0 Remediation Plan

## Summary

Performed a critical audit of the repository at the user's request, focused on
implementation quality rather than features. Fixed the two most severe defects found, with
behavioral regression tests, then recorded the complete finding set as 28 child issues under
a new epic and the `v3.0.0-global-quality-revision` milestone.

## Root Cause Theme

The conceptual layer is strong (provider-agnostic in-repo memory, nearest context boundary,
SSOT versus derived projections, dependency AI-doc scanning). The executive layer lags
behind its own declarations, and the test suite cannot detect the lag because it asserts
textual properties of the documentation rather than behavior of the engines. Three
recurring mechanisms produce most defects:

1. Prose gates: mandatory checks exist only as instructions, with no enforcement and no
   failure signal.
2. Meta tests: version strings, front-matter presence, typography, installer name coverage.
   All valuable, none behavioral. A broken engine keeps the suite green.
3. Unanchored regex over whole files instead of parsing the structure being edited, which
   silently corrupts bodies and unrelated content.

## Fixes Delivered

### 1. ADR retrieval returned zero results (critical)

`scripts/along_kb_search.py`. The splitter required `\d+[.:]` headers. Protocol v2.2.0 moved
ADRs to slug headers, and the actual legacy headers in git history are `## 012 - Title`
(digit, space, dash), which the old pattern never matched either. So ADR search was broken
in every released version, not only since v2.2.0.

Extracted `parse_decision_entries()` and `github_heading_anchor()` as testable units; both
header formats supported; ISO date headings excluded; blocks truncated at the next level-2
heading; case-insensitive `superseded` detection (the protocol's own lowercase form was
previously missed); real GitHub anchors instead of `#<N>`; canonical ADR key as entry slug,
which also improves ranking. 17 ADRs now indexed, previously 0.

### 2. `issue done` wrote an invalid status and dropped a mandatory field (high)

`scripts/along_exec.py`. `re.sub(r'status:\s*\w+', 'status: done')` turned `in-progress`
into `done-progress` (`\w` excludes hyphen), which then prevented the conditional
`completed:` insertion from matching, so closing an in-progress issue silently lost a field
the protocol declares mandatory. Both substitutions were also global, rewriting `status:`
and `updated:` occurrences in the markdown body.

Added `FRONTMATTER_RE`, `has_frontmatter()`, and `update_frontmatter_fields()`: line-anchored,
front-matter only, line endings preserved, BOM tolerated and normalized. `issue done` now
refuses with exit code 1 when front-matter is unparseable instead of reporting success.

Found during verification: a BOM-prefixed entity (routinely produced by
`Set-Content -Encoding utf8` on Windows PowerShell 5.1) made every update a silent no-op
while the CLI still printed success.

## Tests

34 to 55. Two new files, both behavioral:

- `tests/test_kb_search.py` (9): both ADR formats, template exclusion, case-insensitive
  supersession, anchors, plus two invariants against the live `DECISIONS.md` so the header
  format and the parser cannot drift apart silently again.
- `tests/test_issue_lifecycle.py` (12): hyphenated status, mandatory `completed` placement,
  body immutability, idempotent re-close, CRLF preservation, BOM handling, and two
  repository invariants: no issue may carry a status outside the enum, and every issue in
  `ISSUES/done/` must declare `completed`.

Remaining failure: pre-existing `test_06`, caused by missing `encoding="utf-8"` on every
`subprocess.run` in the repository. Tracked as
`[bug--subprocess-encoding-breaks-on-non-utf8-locale]`.

## Remediation Plan Recorded

Epic `[debt--protocol-quality-audit-remediation]` with 28 child issues, each carrying
reproduction with `file:line` references, impact, numbered `REQ-N` requirements, and
acceptance criteria. Ten critical, twelve high, six medium or low. Suggested sequencing:
shared library and YAML foundation first, then the destructive engines, then consumer-repo
portability, then making the gates real, then the multi-agent state machine, then honesty of
metrics.

New milestone `v3.0.0-global-quality-revision` carries a feature verification matrix: every
advertised capability must be executable outside this repository, behaviorally tested,
honestly worded, and non-destructive before the major version ships. Project version stays
`2.2.8` until that definition of done is met.

## Findings Surfaced By The Work Itself

- Wrote an ad-hoc entity reference validator across all 71 entities. Every `parent`,
  `related`, `blocked_by`, and inline citation resolves. Fourteen milestone references do
  not: three milestones were never created (`v2.1.0-along` 9 issues, `v2.2.0-along` 5,
  `v2.1.0-wiki-llm` 1), so the entire v2.1 and v2.2 release history has no milestone entity.
  Two of those were mine and were repointed; the remaining 12 are historical and tracked in
  `[bug--issue-create-stamps-wrong-agent-and-milestone]`.
- `test_07` runs `migrate_protocol.py` against `REPO_ROOT`. It stripped the quotes from
  `protocol_version` in all 29 newly created entity files during a routine test run, the
  third occurrence in one session. Tracked as `[bug--tests-mutate-working-tree]`.
- Recording the plan grew `.along/ISSUES.md` from 5.5 KB to 9.5 KB, immediate evidence for
  `[debt--always-on-context-budget-exceeds-claims]`: the mandatory session read nearly
  doubled from one act of planning, because the projection caps neither `Active` nor
  `Done (recent)`.
- `along_exec.py issue create` stamps `agent: antigravity` regardless of the running tool,
  so attribution data is wrong by construction.

## Code Review and Impact

Diff scoped to `scripts/along_kb_search.py` and `scripts/along_exec.py` plus two new test
files and the entity records. No public interface changed; both fixed functions gained
module-level entry points that tests import. Blast radius checked by search: the ADR parser
had no other callers, and `update_frontmatter_fields` is new. `code-review-graph` MCP was
unavailable this session (`CONNECTION_CLOSED`), so impact analysis was done by symbol search
instead; that gap is itself tracked as
`[debt--unpinned-mcp-and-ghost-wiki-query-tool]`.

Deliberately not run: `/along-kb-sync` (rewrites links destructively per
`[bug--kb-sync-rewrites-unrelated-numbered-links]`) and dashboard regeneration (tracked
artifact churn per `[debt--generated-dashboard-artifact-committed]`). Documentation blast
radius for `docs/topic--*.md` is deferred to the individual fix issues, since no public
surface changed in this session.
