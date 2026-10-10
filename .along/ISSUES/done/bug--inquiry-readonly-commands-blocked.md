---
protocol: along
protocol_version: "4.4.6"
slug: inquiry-readonly-commands-blocked
type: bug
status: done
completed: 2026-10-09
priority: high
created: 2026-10-07
updated: 2026-10-09
agent: claude
tags: [gates, shellparse, powershell]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--plan-gate-blocks-readonly-git, bug--plan-gate-blocks-help, feat--tool-nature-classification, feat--tool-class-model]
---

# Read-only commands and test runs blocked in inquiry phase

## Problem

During a read-only audit (2026-10-06/07, no plan, inquiry phase) `require-plan-approval`
rejected commands that write nothing:

```powershell
Test-Path .along/.migration-backup/x; git status --porcelain -u | Select-Object -First 20
Get-Content a.json; Get-Content b.md -TotalCount 25; Get-ChildItem dir | ForEach-Object { $_.Name; Get-Content $_.FullName }
along session list; along plan status; git status --short | Measure-Object | Select-Object Count
Measure-Command { python .along/scripts/test.py -q *> $env:TEMP\t.txt } | Select-Object TotalSeconds
```

```bash
tail -c 1 .along/HISTORY.md | od -c | head -1
s=$(date +%s); python .along/scripts/test.py -q 2>&1 | grep -E "^Ran |^OK"; echo $(( $(date +%s) - s ))
```

Single commands of the same kind passed. The segment classifier does not know
`Test-Path`, `ForEach-Object` (with read-only body), `Measure-Object`, `Measure-Command`,
`od`, `date`, arithmetic expansion, and treats a redirect into the temp dir as a write.
A test run is verification, not a mutation of the repository (the suite is hermetic), yet it
is rejected in inquiry, so an audit cannot measure the suite.

## Requirements

- REQ-1: Add the listed PowerShell and POSIX read-only commands to the classifier; a
  script block is read-only when every command in it is.
- REQ-2: Redirects into the temp dir / scratchpad / `.along/artifacts/` do not make a
  command a mutation.
- REQ-3: Lifecycle test runs (`along test`, `.along/scripts/test.py`) pass in inquiry.
- REQ-4: Each example above becomes a regression case; coordinate the model with
  `feat--tool-nature-classification` (this bug is the near-term fix).

## Acceptance Criteria
- [x] All examples above classified read-only (hermetic tests)
- [x] `along test` passes the plan gate without a plan
- [x] Automated tests passing
