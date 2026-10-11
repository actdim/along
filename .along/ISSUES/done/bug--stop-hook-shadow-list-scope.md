---
protocol: along
protocol_version: "4.4.9"
slug: stop-hook-shadow-list-scope
type: bug
status: done
completed: 2026-10-11
priority: low
created: 2026-10-11
updated: 2026-10-11
agent: claude-code
tags: [stop-hook, sessions]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--wrapped-work-left-uncommitted]
parent: task--field-report-fixes
---

# Stop hook lists uncommitted attributed files of all sessions

Reported from field use (2026-10-11).

## Problem

The working tree has uncommitted files attributed to N >= 10 closed issues of other sessions;
the current session is bound to a different issue. On every end of turn the Stop hook prints
all N issues ("attributed files remain uncommitted: a, b, c, ...").

## Requirements

- REQ-1: Full list only for the issues of the current session.
- REQ-2: Everything else collapses to one line:
  "N other sessions have uncommitted attributed files (`along session list`)".

## Acceptance Criteria
- [ ] Hermetic test: current-session issues listed, others summarized in one line
- [ ] Automated tests passing
