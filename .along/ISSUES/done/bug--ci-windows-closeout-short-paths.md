---
protocol: along
protocol_version: "4.4.7"
slug: ci-windows-closeout-short-paths
type: bug
status: done
completed: 2026-10-07
priority: high
created: 2026-10-07
updated: 2026-10-07
agent: antigravity
tags: []
blocked_by: []
related: []
---

# Fix Windows 8.3 short path mismatch in parallel closeout engine

GitHub Actions CI matrix runs on windows-latest failed on Python 3.10 through 3.13
in tests/test_parallel_closeout.py due to path mismatches between Windows 8.3 short
paths (e.g. `C:\Users\RUNNER~1\...` returned by `tempfile.mkdtemp()`) and canonical
long paths returned by Git commands (`git rev-parse --show-toplevel`).

Root causes:
1. `closeout.git_top` did not normalize the Git toplevel with `os.path.realpath`.
2. `closeout.closeout_status` computed `prefix` via `os.path.relpath(session.binding_root(repo_root), top)`
   without canonicalizing both paths via `os.path.realpath`, leading to path traversal
   prefixes (`../../../../RUNNER~1/...`) on attributed files.
3. `closeout._commit`, `closeout._entity_files`, and `closeout.run_closeout` compared
   and resolved paths between raw `repo_root` and `top`.
4. `session.binding_root`, `session.binding_context`, and `session.workspace_path` did
   not resolve Windows 8.3 short paths to canonical long paths.

## Acceptance Criteria
- [x] Resolve `repo_root` and `top` with `os.path.realpath` in `closeout.py`.
- [x] Resolve `binding_root`, `binding_context`, and `workspace_path` with `os.path.realpath` in `session.py`.
- [x] Add regression test verifying short/long path mismatch resolution in `test_parallel_closeout.py`.
- [x] All automated tests passing across the suite.
- [x] Typography clean (zero non-ASCII characters).
