---
protocol: along
protocol_version: 2.2.8
slug: protocol-quality-audit-remediation
type: debt
status: in-progress
priority: critical
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [audit, quality, epic, remediation]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [adr-retrieval-blind-to-slug-headers, issue-done-corrupts-status-and-drops-completed]
---

# Epic: Protocol Quality Audit Remediation (2026-09-01)

Parent tracking issue for the findings of the critical repository audit performed on
2026-09-01. Each finding is tracked as a child issue with `parent: protocol-quality-audit-remediation`.

## Root Cause Analysis

The conceptual layer of Along is strong: provider-agnostic in-repo memory, nearest context
boundary, SSOT versus derived projections, dependency AI-doc scanning. The executive layer
systematically lags behind its own declarations, and the test suite cannot detect the lag
because it asserts textual properties of the documentation rather than behavior of the
engines.

Three recurring mechanisms produce most defects:

1. **Prose gates**: mandatory checks exist only as instructions in `AGENTS.md` and
   `SKILL.md` files, with no executable enforcement and no failure signal.
2. **Meta tests**: `tests/test_skills_and_scripts.py` verifies version strings, front-matter
   presence, typography, and installer coverage. All valuable, none behavioral. A broken
   engine keeps the suite green.
3. **Unanchored regex over whole files**: repeated pattern of `re.sub` across an entire
   markdown file (statuses, links, typography) instead of parsing the structure being
   edited. Produces silent corruption of bodies and unrelated content.

## Child Issues by Severity

### Critical - functionally broken or destroys data

- [x] `[bug--adr-retrieval-blind-to-slug-headers]` - ADR search returned zero results (fixed 2026-09-01)
- [x] `[bug--issue-done-corrupts-status-and-drops-completed]` - invalid status, lost mandatory field (fixed 2026-09-01)
- [ ] `[bug--subprocess-encoding-breaks-on-non-utf8-locale]`
- [ ] `[bug--skill-commands-reference-missing-script-paths]`
- [ ] `[bug--commit-binds-arbitrary-active-issue]`
- [ ] `[bug--typography-sanitizer-destroys-non-utf8-files]`
- [ ] `[bug--migration-deletes-destination-without-backup]`
- [ ] `[bug--release-engine-mutates-before-tests-and-reinstalls-globals]`
- [ ] `[bug--handrolled-yaml-loses-block-lists]`
- [ ] `[bug--installer-parity-and-destructive-rules-overwrite]`
- [ ] `[bug--team-skill-uses-provider-specific-subagent-api]`
- [ ] `[debt--team-skill-state-not-persisted]`

### High - wrong results, contradictions, or structural debt

- [ ] `[bug--commit-stages-all-and-dead-test-detection]`
- [ ] `[bug--quality-gates-skip-hidden-directories]`
- [ ] `[bug--kb-sync-rewrites-unrelated-numbered-links]`
- [ ] `[bug--kb-sync-ingestion-not-idempotent]`
- [ ] `[bug--link-gates-skip-along-directory]`
- [ ] `[bug--generated-docs-emit-file-uri-links]`
- [ ] `[bug--tests-mutate-working-tree]`
- [ ] `[bug--issue-create-stamps-wrong-agent-and-milestone]`
- [ ] `[debt--protocol-documentation-drift]`
- [ ] `[debt--extract-shared-python-library]`
- [ ] `[debt--always-on-context-budget-exceeds-claims]`
- [ ] `[debt--unpinned-mcp-and-ghost-wiki-query-tool]`

### Medium / Low - quality, hygiene, honesty of metrics

- [ ] `[bug--generated-lifecycle-hooks-use-shell-string-concat]`
- [ ] `[debt--generated-dashboard-artifact-committed]`
- [ ] `[debt--entity-status-enum-and-unused-taxonomy]`
- [ ] `[debt--exception-swallowing-hides-failures]`
- [ ] `[debt--kb-search-ranking-and-snippet-quality]`
- [ ] `[debt--line-ending-churn-vs-gitattributes]`

## Suggested Sequencing

1. **Foundation first**: `[debt--extract-shared-python-library]` and
   `[bug--handrolled-yaml-loses-block-lists]`. Several other fixes touch front-matter and
   path resolution; doing them on top of five copies of `find_repo_root` and a hand-rolled
   YAML writer would multiply the work.
2. **Stop the bleeding**: the destructive engines
   (`typography-sanitizer`, `migration`, `release-engine`, `installer`).
3. **Make it usable outside this repo**: `skill-commands-reference-missing-script-paths`,
   `subprocess-encoding`, installer parity.
4. **Make the gates real**: hidden-directory scanning, link gates, hermetic tests.
5. **Make the multi-agent claim true**: team-skill state persistence and provider mapping.
6. **Then the honesty pass**: documentation drift, context budget, metrics.

## Acceptance Criteria

- [ ] Every child issue is closed or explicitly deferred with a recorded rationale.
- [ ] An ADR is recorded for each architectural decision taken during remediation
      (shared library boundary, YAML dependency, destructive-operation policy,
      provider abstraction for subagents).
- [ ] `docs/topic--*.md` articles updated where behavior or public surface changed.
