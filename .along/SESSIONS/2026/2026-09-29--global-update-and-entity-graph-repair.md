---
protocol: along
protocol_version: "4.4.0"
date: 2026-09-29
slug: global-update-and-entity-graph-repair
agent: claude-code
branch: main
commit: c1ed519
summary: Ran along update --global (host skills v4.2.0 -> v4.3.0); repaired 3 entity graph errors; opened feat--entity-reference-integrity-gate for v4.4.0; patch release v4.4.1
issues_advanced: [feat--entity-reference-integrity-gate]
issues_completed: []
decisions: []
risks_logged: []
spikes_conducted: []
milestone: v4.4.0-multi-user-merge-automation
---

# Session: Global update and entity graph repair

## Summary
Ran `along update --global`, repaired the entity graph errors it surfaced, and opened an issue to
prevent the class of error from recurring. Closed with a patch release.

## Work Completed
- `along update --global`: host skills for Claude, Codex and Gemini refreshed from the dev repo
  (global v4.2.0 -> v4.3.0), runtime hooks and Cursor attribution settings written, code-review-graph MCP
  registered for Claude only. `packages/dashboard-ui` was migrated from an unrecorded version to v4.3.0 and
  received new `.along/` and `docs/` scaffolding.
- `along doctor --entities` reported 3 errors, all fixed by hand:
  - `feat--code-review-graph-user-skills`: `related` pointed at `feat--kb-search-mcp-tool-and-skill-hardening`,
    deleted on 2026-09-23 and replaced by `feat--kb-search-deterministic-gate-and-skill-hardening` without
    rewriting back-references. Relinked to the replacement.
  - `feat--dashboard-architecture-graph-and-pages-publish`: milestone `v4.0.0-dashboard-and-knowledge-base`
    never existed. The commit `d1a67f0` shipped in tag `v4.0.0`, so the issue now belongs to
    `v4.0.0-runtime-gates-and-worktree-isolation` and is listed in its `target_issues`.
  - `feat--secret-scrubbing-in-hooks-and-diagnostics`: `priority: normal` -> `medium`.
- Opened `feat--entity-reference-integrity-gate` (v4.4.0, high): validation as a wrap / issue-sync gate,
  commit-time check, `along issue rename` / `supersede` with reference rewriting, shared validator in the
  migration engine, and `REQ-7` for `along issue create --milestone` not updating the milestone's `target_issues`.

## Observations
- A concurrent session committed most of these edits in `9db6147` and released `v4.4.0` in `c1ed519`.
  That release marked milestone `v4.4.0-multi-user-merge-automation` as `completed` / `progress_pct: 100`
  while 19 of its 20 target issues are still open. Left as is pending a decision; the version-bump engine sets
  milestone completion from the version alone, without checking target issue status.

## Verification
- `along doctor --entities`: 0 errors, 0 warnings.
- `along sanitize` on the new issue: no banned characters.
