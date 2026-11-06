---
protocol: along
protocol_version: "4.6.0"
slug: partial-session-wrap
type: feat
status: done
completed: 2026-11-06
priority: high
created: 2026-11-05
updated: 2026-11-06
agent: antigravity
tags: [lifecycle, wrap, sessions]
blocked_by: []
related: []
plan_status: needs-approval
---

# Partial wrap and phase checkpoints for multi-session issues

Allow wrapping an agent session without closing the bound issue via `along session wrap <slug> --keep-open` (and `--phase <name>`). Currently, `along wrap` and `along session wrap` always require a closed issue status (`done`, `superseded`, etc.), relocate the issue to `done/`, and purge the blackboard, forcing agents working on large multi-part issues to employ fragile `--dry-run` workarounds.

## Requirements
- REQ-1: `along session wrap <slug> --keep-open` MUST record the session log in `.along/SESSIONS/<date>--<slug>.md`, append a line to `.along/HISTORY.md`, sync projections, and leave the issue in `.along/ISSUES/` with `status: in-progress`.
- REQ-2: When `--keep-open` is used, the canonical plan `.along/ISSUES/<key>/plan.md` and approved plan status MUST be preserved so subsequent sessions can resume immediately without re-planning.
- REQ-3: Support an optional `--phase <name>` argument. When provided, wrap verifies and ticks the corresponding task list checkbox `- [ ] <name>` to `- [x] <name>` in the issue body.
- REQ-4: Pre-flight test verification and working tree integrity checks MUST execute during partial wrap unless `-n` / `--no-verify` is explicitly authorized.
- REQ-5: Purge active session agent bindings (`bindings.json`) while preserving blackboard traces needed for multi-session history.
- REQ-6: Unit tests in `tests/test_session_wrap_partial.py` verifying `--keep-open`, session logging, HISTORY append, phase checkbox ticking, and subsequent session resumption.

## Acceptance Criteria
- [x] `along session wrap <slug> --keep-open` writes session log and HISTORY while keeping issue `in-progress`.
- [x] Issue plan `.along/ISSUES/<key>/plan.md` is preserved across sessions.
- [x] Option `--phase <name>` ticks matching task list checkbox in the issue body.
- [x] Full suite of hermetic tests passes.
