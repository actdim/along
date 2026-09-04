---
name: along-history-sync
description: Reconstruct and reconcile .along/ project history (ISSUES, MILESTONES, SESSIONS, HISTORY.md) from Git commits, tags, and PRs. Use when initializing on an existing git repo or when invoking /along-history-sync.
---

# Along History Sync (`/along-history-sync`) [v2.2.19]

Analyzes Git commits, tags, and PRs to synthesize missing `.along/` entities (`ISSUES/done/`, `MILESTONES/`, `SESSIONS/`, `HISTORY.md`) with `protocol: along`.

## When to use
- **Onboarding Existing Repositories**: When running `/along-init` on an existing repository with prior Git commit history.
- **Retroactive Entity Synchronization**: When commits were made without session logs or tracked issues.
- **Milestone & Release Reconstruction**: Reconstruct past releases from Git tags and changelogs.

## Usage

```bash
python scripts/along_history_sync.py [repo_root] [--check] [--synthesize] [--limit <N>]
```
*(Or `python scripts/along_exec.py history-sync` / `/along-history-sync`)*

### CLI Flags
- `--check`: Inspect and report unmapped commits without modifying `.along/` files (default).
- `--synthesize` / `--apply`: Retroactively generate missing done issues (`.along/ISSUES/done/`), session logs (`.along/SESSIONS/`), and update `HISTORY.md`.
- `--limit <N>`: Maximum number of commits to scan (default: 100).
- `--json`: Output report in structured JSON format.
- `--quiet` / `-q`: Minimal output.
