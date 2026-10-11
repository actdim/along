---
protocol: along
protocol_version: "4.4.9"
slug: gate-friction-and-bypass-accountability
type: feat
status: done
completed: 2026-10-11
priority: high
created: 2026-10-11
updated: 2026-10-11
agent: claude-code
tags: [gates, hooks, bypass]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [feat--gate-strictness-profiles, bug--plan-approval-self-and-lost]
parent: task--field-report-fixes
---

# Gate friction and bypass accountability

## Problem

Observed in one session (2026-10-11): every block was a false positive or a deadlock, none
caught a real violation. A read-only compound (`along sanitize && along plan status`) was
denied; the Stop gate demanded `along issue sync` while plan mode forbade it (three rejected
turns); a subagent's read-only diff and an `echo "a -> b"` were blocked. Frequent false
blocks train agents and humans to bypass, and bypass flags (`--no-verify`,
`--force-reason`, `start --approved`) are agent-usable and mostly unrecorded, so a bypass
becomes routine instead of a deliberate, human, recorded decision.

Principle: reads never block; mechanical fixups are done by the hook; every block has a legal
exit cheaper than a bypass; a bypass is a human decision and is recorded; gate quality is
measured.

## Requirements

- REQ-1: Read-only classification: `sanitize` (check mode), `issue show`, `milestone show`,
  `kb search`, `gates check`, read modes of other commands pass; compound commands are judged
  per segment (read-only OR Along state OR verification).
- REQ-2: `projection_sync_before_stop` compares content (compiled board vs file) instead of
  mtimes, and rewrites a stale `ISSUES.md` itself instead of rejecting the turn.
- REQ-3: Bypass flags (`commit -n`, `wrap -n`, `wrap --force-reason`, `bump -n`,
  `scratch fallback`, `scratch purge --force`) require a reason and, where the runtime records
  user prompts, a user message after the latest failure of that gate; every bypass is recorded
  (session trace, `hooks_audit.jsonl` `decision: bypass`, commit trailer `Along-Bypass:`).
- REQ-4: Gate tiers `invariant | process | advisory` in the gate catalogue; invariant gates
  cannot be shadowed/disabled by repo config and cannot be bypassed.
- REQ-5: `along gates stats` aggregates deny / shadow / bypass per gate; `along doctor` shows
  the gates with the highest bypass ratio and gates shadowed/disabled by repo config.
- REQ-6 (deferred): dashboard panel for gate stats.

## Resolution (2026-10-11)

REQ-1..REQ-5 implemented; ADR-2026-10-11--gate-friction-fixes. REQ-6 (dashboard panel for
gate stats) deferred. The live hooks run from the installed copy (`~/.along/bin`), so the
fixes reach running sessions only after a reinstall.

## Acceptance Criteria
- [ ] Hermetic tests for REQ-1..REQ-5
- [ ] ADR recorded (tiers and bypass authorization)
- [ ] Docs: topic--runtime-hooks-and-gates updated
- [ ] Automated tests passing
