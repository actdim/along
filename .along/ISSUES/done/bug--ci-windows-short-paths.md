---
protocol: along
protocol_version: "4.4.6"
slug: ci-windows-short-paths
type: bug
status: done
completed: 2026-10-06
priority: high
created: 2026-10-05
updated: 2026-10-06
agent: antigravity
tags: []
blocked_by: []
related: []
---

# CI matrix failures on windows-latest from 8.3 short paths

GitHub Actions CI matrix runs on windows-latest failed on Python 3.10 through 3.13
due to path mismatch between Windows 8.3 short paths (e.g. `C:\Users\RUNNER~1\...`
returned by `tempfile.mkdtemp()`) and canonical long paths returned by Git commands
(`git rev-parse --show-toplevel`).

Root causes:
1. `gates.zero_byte_working_tree_audit`: computed `top_rel` via `os.path.relpath` between
   short and long paths, yielding traversal paths (`../../..`) that broke `git cat-file`.
2. `gitgates.baseline_entity_problems`: computed `prefix` via `os.path.relpath` between
   short and long paths, causing the temporary extraction directory to be mislocated.
3. `predicates._entity_files_changed`: ran `git status` with `cwd` containing short paths,
   preventing path prefix matching against `.along/`.

## Acceptance Criteria
- [x] Resolve `repo_root` and `top` with `os.path.realpath` in `gates.py`.
- [x] Resolve `repo_root` and `top` with `os.path.realpath` in `gitgates.py`.
- [x] Resolve `repo_root` with `os.path.realpath` in `predicates._entity_files_changed`.
- [x] Targeted unit tests passing.
