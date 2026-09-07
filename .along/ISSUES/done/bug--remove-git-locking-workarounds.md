---
protocol: along
slug: remove-git-locking-workarounds
type: bug
status: done
completed: 2026-09-07
priority: high
created: 2026-09-07
updated: 2026-09-07
agent: antigravity
tags: [git, windows, cache]
blocked_by: []
related: []
---

# Remove broken git locking workarounds and restore clean stat-cache

Remove `GIT_OPTIONAL_LOCKS=0` and `diff.autoRefreshIndex false` workarounds across repository code, documentation, and tooling. These flags break the Git stat-cache on Windows, producing phantom `" M"` file modifications without resolving `.git/index` sharing conflicts during write operations.

## Acceptance Criteria
- [x] Remove `GIT_OPTIONAL_LOCKS: "0"` from `scripts/alongkit/proc.py`.
- [x] Clean up `.vscode/settings.json` removing injected `GIT_OPTIONAL_LOCKS` env.
- [x] Remove `GIT_OPTIONAL_LOCKS` and `diff.autoRefreshIndex` recommendations from `install.ps1`, `skills/along-init/SKILL.md`, and `docs/topic--setup-and-workflow.md`.
- [x] Synchronize `llms-full.txt` via KB sync if needed.
- [x] All automated tests pass hermetically without false `" M"` stat cache drift.
