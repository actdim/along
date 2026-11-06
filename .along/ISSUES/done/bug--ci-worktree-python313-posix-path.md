---
protocol: along
protocol_version: "4.7.0"
slug: ci-worktree-python313-posix-path
type: bug
status: done
completed: 2026-11-06
priority: high
created: 2026-11-06
updated: 2026-11-06
agent: antigravity
tags: []
blocked_by: []
related: []
plan_status: approved
---

# Fix worktree inspect_git_dir POSIX path handling on Windows in Python 3.13

In Python 3.13 on Windows, ntpath.isabs() returns False for drive-relative paths starting with a single slash (such as /var/repos/main or \var\repos). In scripts/alongkit/worktree.py (inspect_git_dir) and scripts/alongkit/proc.py (find_git_dir), checking only os.path.isabs() causes POSIX root paths in gitdir and commondir files to be treated as relative, incorrectly joining them with the current directory and prepending the drive letter. This breaks test_19_posix_path_preservation_in_inspect_git_dir on Windows under Python 3.13 in CI.

## Requirements
- REQ-1: inspect_git_dir MUST treat paths starting with '/' or '\' as rooted/absolute across all Python versions on Windows.
- REQ-2: find_git_dir in proc.py MUST treat gitdir paths starting with '/' or '\' as rooted/absolute.
- REQ-3: test_19_posix_path_preservation_in_inspect_git_dir MUST pass under Python 3.10, 3.11, 3.12, and 3.13 on Windows.

## Acceptance Criteria
- [x] inspect_git_dir preserves POSIX gitdir and commondir targets on Windows across Python 3.10-3.13
- [x] proc.py find_git_dir does not misclassify rooted gitdir paths as relative
- [x] All 1743 automated tests pass on Python 3.13 on Windows
