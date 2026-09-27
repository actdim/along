---
protocol: along
protocol_version: "4.2.0"
slug: kb-search-archive-scope-default
type: feat
status: open
priority: medium
created: 2026-09-27
updated: 2026-09-27
agent: cowork
tags: [kb-search, retrieval, ranking]
milestone: v4.4.0-multi-user-merge-automation
blocked_by: []
related: [feat--progressive-disclosure-and-context-scaling, debt--constraints-superseded-adr-filtering]
---

# kb-search excludes archived issues and session logs by default

## Problem

The repository accumulated 104 session logs, 135 done issues and 41 ADRs in eight weeks. With `--category all` (the default), `along kb-search` results are dominated by this history: queries such as "worktree isolation", "typography gate" or "migration backup" return done issues and session logs ahead of, or instead of, the current `docs/topic--*.md` article. The protocol mandates kb-search before reading docs, so agents are steered to stale records. Superseded ADRs (see `debt--constraints-superseded-adr-filtering`) add further noise.

## Requirements

- REQ-1: Default scope = `docs/` topics, active ADRs, open/in-progress issues, milestones. Archived scopes (`issue:done`, `session`, superseded ADRs) require `--archive` or an explicit `--category`.
- REQ-2: Ranking boost for `docs/topic--*.md` and recency decay for archived records when they are included.
- REQ-3: Result lines show status (`open`, `done`, `superseded`) so agents can discard stale hits.
- REQ-4: Tests: the three queries above return the matching `docs/` topic in the top 3 by default.

## Acceptance Criteria

- [ ] Default queries on this repo return current docs first
- [ ] `--archive` restores the old behaviour
- [ ] Automated tests passing
