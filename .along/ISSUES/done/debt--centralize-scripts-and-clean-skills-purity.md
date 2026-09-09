---
protocol: along
slug: centralize-scripts-and-clean-skills-purity
type: debt
status: done
priority: high
created: 2026-08-31
updated: 2026-08-31
completed: 2026-08-31
agent: antigravity
tags: [skills, scripts, architecture, cli, test]
milestone: v2.1.0-along
blocked_by: []
related: []
---

# Centralize Scripts Suite, Enforce Skills Declarative Purity & CLI Precursor Router

Consolidate all Along Python tools into `scripts/`, purge executable files from `skills/`, establish `along_exec.py` unified command router, and prevent runtime launch/discovery errors.

## Acceptance Criteria
- [x] All `.py` scripts and `__pycache__` removed from `skills/`. Every skill folder contains only pure `SKILL.md`.
- [x] All 10 standalone tools consolidated into `scripts/` (`along_dep_scan.py`, `along_kb_sync.py`, `along_kb_search.py`, `along_history_sync.py`, `along_commit.py`, `along_version_bump.py`, `along_update.py`, `along_dash.py`, `migrate_protocol.py`, `sanitize_typography.py`).
- [x] `scripts/dashboard.py` (legacy 66KB) and `analyze_git_history.py` removed.
- [x] `scripts/along_exec.py` enhanced with intelligent script resolver and multi-command dispatch.
- [x] Test discovery isolated with protected `dashboard/api/__init__.py` try-except block.
- [x] Install scripts updated to install tools to `~/.along/bin/` and pure skills to agents.
- [x] 100% test pass rate across 17 automated tests.
