---
protocol: along
protocol_version: "4.4.6"
slug: history-append-blocked-after-wrap
type: bug
status: open
priority: medium
created: 2026-10-07
updated: 2026-10-07
agent: claude
tags: [wrap, history, gates]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [task--release-v4-4-7, task--file-v4-5-fixes-update]
---

# HISTORY append blocked after wrap (checklist order conflict)

## Problem

`along wrap` appends the `.along/HISTORY.md` line only when `--summary` is given
(`lifecycle.execute_wrap`, step 6). Without it the wrap succeeds silently, and the protocol
checklist then asks for the HISTORY line as step 8, after the wrap (step 6). By then the
wrap has purged the blackboard and unbound the session, so `require-plan-approval` rejects
the manual edit of `.along/HISTORY.md` ("No approved plan for this session").

Observed 2026-10-07: `along wrap release-v4-4-7 --no-decisions` (no `--summary`) left no
HISTORY line, and the manual append was rejected; the line for that release is still
missing. `along wrap file-v4-5-fixes-update --summary "..."` appended it correctly.

## Requirements

- REQ-1: `along wrap` always writes the HISTORY line: `--summary` when given, else the
  session log summary / issue title. Idempotent per slug.
- REQ-2: Without `--summary` the wrap at least warns that no HISTORY line was written and how
  to add it (rerun-safe command, e.g. `along history append <slug> "..."`) that passes the
  plan gate as Along state.
- REQ-3: The protocol checklist folds step 8 into the wrap (or moves it before step 6) and
  names `--summary`.
- REQ-4: Backfill the missing `release-v4-4-7` HISTORY line.

## Acceptance Criteria
- [ ] Wrap without `--summary` still yields exactly one HISTORY line (hermetic test)
- [ ] Protocol checklist updated
- [ ] release-v4-4-7 line backfilled
- [ ] Automated tests passing
