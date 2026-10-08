---
protocol: along
protocol_version: "4.4.7"
slug: lexical-path-root-resolution
type: bug
status: done
completed: 2026-10-08
priority: high
created: 2026-10-08
updated: 2026-10-08
agent: antigravity
tags: [windows, paths, ci]
blocked_by: []
related: []
---

# Preserve lexical path form in root discovery while enforcing semantic canonicalization

Fix root discovery and hook preflight regressions on Windows CI where find_repo_root, find_context, find_session_root, and find_hook_root converted short DOS 8.3 paths (RUNNER~1) to expanded canonical paths, breaking callers and tests expecting lexical path preservation. Enforce semantic path comparisons (_same_path, is_within) without altering lexical walk representation.

## Acceptance Criteria
- [x] find_repo_root, find_context, find_session_root, and find_hook_root preserve lexical path representation
- [x] subproject_context and boundary checks use repo._same_path instead of lexical string comparisons
- [x] _inside in hookpreflight delegates to repo.is_within
- [x] worktree git_worktrees indexing uses canonical_path
- [x] 100% test suite passing (1126/1126 tests)

