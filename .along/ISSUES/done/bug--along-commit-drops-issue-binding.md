---
protocol: along
protocol_version: "4.4.2"
slug: along-commit-drops-issue-binding
type: bug
status: done
completed: 2026-10-01
priority: medium
created: 2026-10-01
updated: 2026-10-01
agent: claude-code
tags: [commit, binding]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: []
---

# along commit -i does not append refs binding when message names issue slugs

## Problem
`format_commit_message()` in `scripts/along_commit.py` appends `(refs #<slug>)` only when
`slug not in msg`. A message that mentions the slug in any form (for example
`feat--rule-packs-local-extensions` in a list) gets no binding, although the
`commit_issue_binding` gate accepts only `(refs #slug)` or `[type--slug]`. Seen on 2026-10-01:
commit `f088cab` was created without a binding and had to be amended.

## Requirements
- REQ-1: The binding is skipped only when the message already carries `(refs #<slug>)` or
  `[<type>--<slug>]` for the bound issue.

## Acceptance Criteria
- [ ] Message naming the slug in prose still gets `(refs #<slug>)`
- [ ] Automated tests passing
