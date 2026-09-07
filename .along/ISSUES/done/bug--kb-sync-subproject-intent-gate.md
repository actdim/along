---
protocol: along
protocol_version: "2.2.25"
slug: kb-sync-subproject-intent-gate
type: bug
status: done
completed: 2026-09-07
priority: high
created: 2026-09-07
updated: 2026-09-07
agent: antigravity
tags: [kb-sync, git, monorepo, intent-gate]
blocked_by: []
related: []
---

# Fix Intent Gate false positive in subprojects during kb-sync

## Problem Description
When cascading Knowledge Base synchronization runs on subprojects that are directories inside a parent Git repository (not separate Git repositories), `along_kb_sync.py` checks for document content reduction against Git HEAD using `git show HEAD:{rel_to_repo}` with `cwd=repo_root` (the subproject directory).
In Git revision syntax, `HEAD:<path>` without a `./` or `../` prefix resolves relative to the top-level repository working tree root rather than `cwd`.
If matching filenames exist both in the repository root and in the subproject (e.g., `docs/topic--architecture.md`), Git returns the root file instead of the subproject file. If the root file is larger, the script detects a false content reduction of 80-90% and halts with "Operation halted to prevent accidental data loss".

## Acceptance Criteria
- [x] Prefix `rel_to_repo` with `./` in `git show HEAD:...` within `scripts/along_kb_sync.py`.
- [x] Ensure Git resolves paths relative to the subproject working directory `cwd`.
- [x] Add hermetic unit test covering cascading sync in a subproject inside a monorepo git tree with identically named doc files.
- [x] Automated tests pass with zero failures.


