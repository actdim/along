---
protocol: along
protocol_version: "3.0.0"
slug: updater-regressions-and-sync-constraints
type: bug
status: done
priority: critical
created: 2026-09-10
updated: 2026-09-10
completed: 2026-09-10
agent: antigravity
title: Fix sync_constraints return value, along_update help CLI flag, and protocol block spacing
---

# Bug: Fix sync_constraints return value, along_update help CLI flag, and protocol block spacing

## Description
1. `alongkit/entities.py:sync_constraints`: returned compiled text content instead of the target file path `constraints_file`. Callers (`along_update.py` and `migrate_protocol.py`) passed the return value to `os.path.relpath`, crashing or printing multi-line content as a relative path.
2. `along_update.py`: missing `-h`/`--help` flag handling in `__main__`, causing `--help` to immediately trigger repository update.
3. `along_update.py`: protocol block replacement regex consumed trailing whitespace without `block` having proper trailing newlines, causing marker to glue to subsequent headers in `AGENTS.md`.
