---
protocol: along
protocol_version: "4.4.16"
slug: migration-backup-retention-and-cleanup
type: debt
status: done
completed: 2026-10-16
priority: medium
created: 2026-10-16
updated: 2026-10-16
agent: antigravity
tags: [maintenance, cleanup, migration]
blocked_by: []
related: []
---

# Prune and limit migration backups in .along

## Problem

The directory `.along/.migration-backup/` accumulates snapshots on every protocol migration run. Each snapshot copies nearly the entire `.along/` tree (hundreds of markdown files). Because `BACKUP_KEEP` default is 5 snapshots, `.along/.migration-backup/` holds over 2,100 redundant files consuming disk space and cluttering local directory trees. In addition, there is no direct CLI flag or function to purge all stale snapshots or limit retention to 1 snapshot.

## Requirements

- REQ-1: Reduce default `BACKUP_KEEP` in `scripts/alongkit/migration.py` from 5 to 1 (keep only the single most recent snapshot for rollback).
- REQ-2: Add `--clean-backups` flag to `migrate_protocol.py` CLI to purge all snapshots when requested, and ensure `prune_backups()` keeps at most 1 by default.
- REQ-3: Prune the existing stale snapshot directories in `.along/.migration-backup/`, keeping at most 1 most recent snapshot.
- REQ-4: Ensure existing test suites (`tests/test_update_maintenance_friction.py`, etc.) pass with zero regressions.

## Acceptance Criteria

- [x] `BACKUP_KEEP` default set to 1 in `scripts/alongkit/migration.py`
- [x] Existing snapshot directories in `.along/.migration-backup/` pruned to at most 1 snapshot
- [x] Total file count in `.along/.migration-backup/` reduced from >2100 to <=450
- [x] Automated tests passing
