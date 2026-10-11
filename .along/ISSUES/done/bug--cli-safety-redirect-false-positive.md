---
protocol: along
protocol_version: "4.4.9"
slug: cli-safety-redirect-false-positive
type: bug
status: done
completed: 2026-10-11
priority: low
created: 2026-10-11
updated: 2026-10-11
agent: claude-code
tags: [cli-safety, gates]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: []
parent: task--field-report-fixes
---

# CLI Safety Gate false positive on stderr redirection

Reported from field use (2026-10-11).

## Problem

```bash
for d in a b; do grep -l x "$d" 2>/dev/null | while read f; do echo "$f -> ok"; done; done
```

is rejected with "Inline shell file writer (echo/printf > file) detected", although nothing
is written to a file.

## Requirements

- REQ-1: Trigger only on writes to a file: `echo/printf ... > path`, `>> path`, `tee path`,
  heredoc into a file.
- REQ-2: Do not trigger on `2>/dev/null`, `>/dev/null`, `2>&1`, `&>/dev/null`, or `echo` to
  stdout or into a pipe (including `->` inside quoted strings).

## Acceptance Criteria
- [ ] Table-driven test with 15-20 command lines and expected true/false
- [ ] Automated tests passing
