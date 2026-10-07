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
related: [task--release-v4-4-7]
---

# HISTORY append blocked after wrap (checklist order conflict)

## Problem

The completion checklist in `AGENTS.md` runs `along wrap` at step 6 and appends the
`.along/HISTORY.md` line at step 8. `along wrap` purges the blackboard and unbinds the
session, after which `require-plan-approval` rejects the edit of `.along/HISTORY.md`
("No approved plan for this session"). The `release-v4-4-7` HISTORY line could not be
written (2026-10-07).

## Requirements

- REQ-1: `along wrap` appends the HISTORY line itself (date, slug, agent, summary, session
  log link), in its transaction, so the checklist step becomes a check, not a manual edit.
  `--summary` feeds it.
- REQ-2: Alternatively or additionally, `.along/HISTORY.md` appends pass the plan gate as
  Along state (append-only, union-merged).
- REQ-3: Checklist order in the protocol block matches what the engines allow.

## Acceptance Criteria
- [ ] Wrap writes exactly one HISTORY line per slug (idempotent on rerun)
- [ ] Protocol checklist updated
- [ ] Automated tests passing
