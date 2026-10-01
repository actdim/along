---
protocol: along
protocol_version: "4.4.1"
date: 2026-09-29
slug: git-merge-drivers-and-setup
agent: claude-code
branch: main
commit: 27c6642
summary: Implemented along-projection and along-frontmatter git merge drivers and the along git setup/status/sync command (uncommitted, per user)
issues_advanced: []
issues_completed: [feat--git-merge-drivers-and-setup]
decisions: [ADR-2026-09-29--projection-merge-driver-defers-recompile]
risks_logged: []
spikes_conducted: []
milestone: v4.5.0-multi-user-merge-automation
---

# Session: Git merge drivers and `along git setup`

## Summary

First v4.5.0 task, taken by priority. Executed via `/along-team` (single-agent sequential,
workspace: inherit). The user asked for no commits: all changes are left in the working tree
on top of the parallel roadmap-shift session's uncommitted edits.

## Initial Implementation Plan (Baseline)

1. `scripts/alongkit/merge.py` + `scripts/along_merge_driver.py` - driver engines (REQ-1, REQ-2).
2. `along git setup|status|sync` in `scripts/along_exec.py` (REQ-3).
3. Integration: `along update` (root context), `along doctor`, `skills/along-init` (REQ-4).
4. `tests/test_merge_driver.py`, docs, ADR (REQ-5).

## Execution & Loop Trace (Fixes & Re-plans)

- Design change against the issue text: the projection driver does NOT recompile in place.
  Git runs drivers before merged entity files reach the working tree, so an in-driver
  recompile rebuilds the pre-merge board. The driver keeps ours and writes
  `$GIT_DIR/along-projection-resync`; `along git sync` recompiles. Recorded as
  ADR-2026-09-29--projection-merge-driver-defers-recompile.
- Fix loop 1 (repository contracts): broad `except Exception`, literal BOM character,
  missing library execution guard, missing `pyproject.toml` engine mapping, and test helper
  names colliding with the no-duplicate-helpers contract. All fixed; suite green.
- Driver path resolution also covers the wheel layout (`alongkit/engines/`).

## Verification Walkthrough & Gate Manifest

- `along test -q`: 741 tests, OK (17 new in `tests/test_merge_driver.py`, including an
  end-to-end merge of two concurrent branches in a temp repo with zero conflict markers).
- `along git status` / `along git setup --dry-run` on the live repo: read-only, reports drivers
  missing. The live repo was NOT registered (left for the user to decide).
- `along kb-sync`: 404 relative links verified.

```text
Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [along test -q, 741 OK]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-1..REQ-5]
- Blast Radius: DEGRADED (PASS) [static search: new module; callers along_exec git/doctor, along_update]
- Documentation Parity: EXECUTED (PASS) [cli-reference, architecture, AGENTS.md/protocol.md, along-init SKILL]
- Clean Typography: EXECUTED (PASS) [test_05_clean_typography]
```

## Follow-ups

- `feat--docs-semantic-conflict-resolution` is now unblocked.
- Optional: run `along git setup` in this repository to dogfood the drivers.
