---
protocol: along
protocol_version: "4.2.1"
slug: shell-classifier-residual-bypasses
type: bug
status: done
completed: 2026-09-29
priority: high
created: 2026-09-29
updated: 2026-09-29
agent: claude-code
tags: [hooks, gates, security]
milestone: v4.3.0-developer-experience-and-runtime-resilience
blocked_by: []
related: [bug--safe-command-prefix-bypass]
---

# Shell read-only classifier still lets single &, python -c and mutating git flags through

## Problem

Review of [bug--safe-command-prefix-bypass] found that `alongkit/hooks/shellparse.py` still classified these commands as read-only, so the plan-approval gate let them through:

```text
ls & rm -rf src                                          -> read-only
dir & del /s /q src                                      -> read-only (cmd.exe separator)
python -c "print(1); import shutil; shutil.rmtree('src')" -> read-only
git branch -D main                                       -> read-only
git diff --output=src/a.py                               -> read-only
```

## Requirements

- REQ-1: A single `&` outside quotes splits segments, except where it belongs to a redirection (`2>&1`, `>&2`, `&>file`).
- REQ-2: `python -c` is read-only only for one `print(...)` call with no other call inside its arguments.
- REQ-3: `git diff/log/show` with `--output` is a write; `git branch` is read-only only with listing flags (or a pattern after `--list`).
- REQ-4: Table-driven tests for every case above, plus no false positives for common reads.

## Acceptance Criteria
- [x] All evidence commands are classified as mutating
- [x] Listing forms (`git branch -a -vv`, `git branch --list "feat/*"`, `python -c "print('a; b')"`, `pytest 2>&1 &`) stay read-only
- [x] Automated tests passing

## Resolution

- `split_segments` treats a lone `&` as a separator unless the previous char is `>` or it starts `&>` (REQ-1).
- `_python_c_is_read_only` parses the code with `ast`: exactly one expression statement, a call to `print`, and no other `Call` node (REQ-2).
- `_git_is_read_only` rejects `--output`/`--output=` and any `git branch` argument outside the listing flag set (REQ-3).
- `tests/test_shell_classification.py`: 9 new read-only and 16 new mutating cases, a splitter test for `&`, and three evidence commands added to the end-to-end Claude adapter check (REQ-4).
- Verified: full suite on Python 3.12 via `.along/scripts/test.py -q`, 699 tests OK.
