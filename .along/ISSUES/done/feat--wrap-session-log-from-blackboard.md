---
protocol: along
protocol_version: "4.4.2"
slug: wrap-session-log-from-blackboard
type: feat
status: done
completed: 2026-10-01
priority: medium
created: 2026-10-01
updated: 2026-10-01
agent: claude-code
tags: [wrap, session, adr]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [feat--along-team-step-enforcement]
---

# along wrap builds session log from blackboard and confirms decisions

## Problem
`along wrap` writes the session log without the blackboard (plan, reviews, trace), which purge
then deletes. The frontmatter normalizer can drop `issues_completed` instead of deriving it from
the issue key. Empty `decisions: []` is never questioned, so architectural choices go unrecorded.

## Requirements
- REQ-1: Wrap renders plan, step statuses, review verdicts and trace from
  `.along/.session/<slug>/` into the session log before purge.
- REQ-2: `issues_completed` defaults to the wrapped issue key when it is done.
- REQ-3: Wrap requires `--decisions <ADR...>` or `--no-decisions` (explicit confirmation).

## Acceptance Criteria
- [x] Session log contains blackboard content after purge
- [x] Wrap refuses without a decisions answer
- [x] Automated tests passing
