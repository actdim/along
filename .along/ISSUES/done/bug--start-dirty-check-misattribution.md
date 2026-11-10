---
protocol: along
protocol_version: "4.6.1"
slug: start-dirty-check-misattribution
type: bug
status: done
completed: 2026-11-10
priority: high
created: 2026-11-08
updated: 2026-11-10
agent: claude-code
tags: [gates, feedback]
blocked_by: []
related: []
---

# along start blames the current session's edits on wrapped issues

## Problem

Field report (2026-11-08, dynstruct subproject in a 12-root monorepo): a session bound to an in-progress issue with an approved plan ran `along start <same-slug> --write-scope <path>` to extend its scope. `along start` refused with "Working tree has uncommitted changes from completed (wrapped) issue(s)" and listed files that the current session had edited under the bound issue. The only exit offered was `--allow-dirty`, a bypass flag, although no rule was broken.

Root cause (`scripts/alongkit/commands/lifecycle.py`, the dirty-tree block of `along start`): a dirty path is blamed on every wrapped issue whose session log lists that path (`closeout.done_issues_attribution`). That list records files the issue ever touched, so any later edit to the same file by another issue still matches the old wrapped issue. The hook edit log (`session.attributed_files`) already knows which in-progress issue made the change but is not consulted for check 1. The check also runs when the slug being started is already in progress and bound to the calling session, where no new work starts.

## Requirements
- REQ-1: `along start` MUST NOT count a dirty path against a wrapped issue when an in-progress issue (including the one being started) has an edit event for that path.
- REQ-2: `along start <slug>` MUST skip both dirty-tree checks when `<slug>` is already in progress and bound to the calling agent session (a re-start that only extends `--write-scope` / `--allow-root`).
- REQ-3: Paths that only a wrapped issue touched MUST still block, as today (`bug--wrapped-work-left-uncommitted` stays covered).

## Acceptance Criteria
- [x] A test reproduces the report: a wrapped issue's log lists `a.py`, the in-progress issue has an edit event for `a.py`, `a.py` is dirty; `along start <in-progress slug> --write-scope x` succeeds.
- [x] A test: re-start of the bound in-progress slug with other dirty files succeeds without `--allow-dirty`.
- [x] Existing start-guard tests (`feat--atomic-wrap-commit-and-start-guard`) still pass.
- [x] Automated tests passing
