---
protocol: along
date: 2026-08-31
slug: centralize-scripts-and-clean-skills-purity
agent: antigravity
branch: main
commit: []
summary: Consolidate standalone tools into scripts/, purge skills/ of Python files, implement unified along_exec router, fix test discovery and update installers.
milestone: v2.1.0-along
issues_advanced: []
issues_completed: [feat--centralize-scripts-and-clean-skills-purity]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Centralize Scripts Suite, Skills Declarative Purity & Unified Command Router

Executed critical audit, refactoring, and consolidation of Along skills and executable scripts.

## Accomplishments
1. **Consolidated Scripts in `scripts/`**:
   - Moved all standalone tools into `scripts/` (`along_dep_scan.py`, `along_kb_sync.py`, `along_kb_search.py`, `along_history_sync.py`, `along_commit.py`, `along_version_bump.py`, `along_update.py`, `along_dash.py`, `migrate_protocol.py`, `sanitize_typography.py`).
   - Removed obsolete `scripts/dashboard.py` (66 KB) and redundant `analyze_git_history.py`.
2. **Purged `skills/` Directory**:
   - Removed all `.py` files and `__pycache__` directories from `skills/`. Every skill folder is now a pure declarative `SKILL.md`.
3. **Unified Dispatcher (`along_exec.py`)**:
   - Built comprehensive CLI-ready command router with script resolver supporting lifecycle hooks and all Along protocol tools.
4. **Resolved Test Discovery & Isolation**:
   - Isolated `dashboard.api` imports with try-except blocks, preventing test discovery crashes when `fastapi` is not in the system Python.
   - Standardized test execution to `python .along/scripts/test.py` and `python scripts/along_exec.py test`.
5. **Updated Installers**:
   - `install.ps1` and `install.sh` install executable scripts to `~/.along/bin/` and OpenCode helpers, and copy clean declarative skill folders to agents.

## Code Review & Blast Radius Assessment
- **Caller Impact**: Upstream agents and skill runners now have deterministic execution via `scripts/along_exec.py <cmd>` or `python scripts/along_<tool>.py`.
- **Typographic Cleanliness**: Verified zero non-ASCII typographic characters across all files.
- **Tests**: 17 unit tests passing with zero failures.
