---
protocol: along
protocol_version: "4.4.4"
slug: readonly-classifier-pipelines
type: bug
status: done
completed: 2026-10-05
priority: medium
created: 2026-10-05
updated: 2026-10-05
agent: claude-code
tags: [hooks, inquiry, shellparse]
blocked_by: []
related: []
---

# Inquiry gate blocks read-only pipelines (cut, sort, for-loops, command substitution)

`alongkit.hooks.shellparse.is_read_only_command` drives the inquiry gate
[gate: require-plan-approval]. It rejected plainly read-only commands during a read-only audit:
- `grep X file | tail -2 | cut -c1-900` - `cut` is not in `_READ_COMMANDS`;
- `sed -n 1,80p f | grep ...` - `sed` (without `-i`/`w`) is not recognized;
- `for f in $(grep -rl X dir); do grep X "$f"; done` - any `$(...)` makes `split_segments` return None,
  and shell keywords (`for`, `do`, `done`) are not understood.

## Requirements
- REQ-1: Add pure filters to the read list: `cut`, `sort`, `uniq`, `tr`, `nl`, `basename`, `dirname`,
  `realpath`, `du`, `df`, `test`/`[`, `diff`, `cmp`.
- REQ-2: `sed` is read-only only without `-i`/`--in-place` and without `w`/`W`/`e` commands in scripts;
  `find` only without `-exec`, `-execdir`, `-ok`, `-delete`, `-fprint*`.
- REQ-3: `$(...)` / backticks are classified recursively: read-only when the inner command is.
- REQ-4: Shell control keywords (`for ... in ...`, `do`, `done`, `if`, `then`, `else`, `fi`, `while`)
  are stripped/accepted so the loop body decides.
- REQ-5: No regression: redirects to files, `sed -i`, `find -delete`, `$(rm x)` stay non-read-only.

## Acceptance Criteria
- [x] Unit tests for every REQ, positive and negative.
- [x] Automated tests passing (6 pre-existing env failures, identical on clean HEAD)
