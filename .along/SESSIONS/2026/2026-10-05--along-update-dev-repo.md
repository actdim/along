---
protocol: along
protocol_version: "4.4.5"
date: 2026-10-05
slug: along-update-dev-repo
agent: claude-code
branch: main
commit: 0edd557
summary: 'along update run in the dev repository after the global reinstall: merge drivers registered, dashboard-ui migration state 4.3.0 -> 4.4.5; findings F1-F5 recorded'
issues_advanced: []
issues_completed: [task--along-update-dev-repo]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Along update dev repo

## Summary
along update run in the dev repository after the global reinstall: merge drivers registered, dashboard-ui migration state 4.3.0 -> 4.4.5; findings F1-F5 recorded

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

| Step | Title | Status | Retries | Review |
| --- | --- | --- | --- | --- |
| 1 | Step 1 | passed | 0 | no |

### Plan

#### Living Plan: along-update-dev-repo

Title: Run along update in the dev repository after the global reinstall

Approved by the user in chat on 2026-10-05 ("да").

##### Steps
- [x] Step 1: `along update --dry-run`; it only says it would run the migration, so `along migrate --dry-run` was run per context to see the real plan (root: `keep .agents`; dashboard-ui: nothing to do).
- [x] Step 2: `along update` applied in both contexts (root, `packages/dashboard-ui`).
- [x] Step 3: Changes inspected: `.gitattributes` gained the managed merge-driver block (`along git setup`), `packages/dashboard-ui/.along/.protocol-version` 4.3.0 -> 4.4.5. AGENTS.md blocks unchanged (already current).
- [x] Step 4: Tests, issue close, wrap, commit and push.

##### Expectations
- Dev repository: isolated mode, `protocol.md` from `skills/along-init/`, global skills untouched.
- Expected result: no change or projection re-sync only. Actual: merge drivers were never registered here; now they are.

### Research

#### Research & Findings: along-update-dev-repo

##### Target Symbols and Files
- `scripts/along_update.py`: `run_update`, `apply_migration_to_context` (runs `migrate_protocol.py --apply|--dry-run` per context), remote version from `git ls-remote --tags` (line ~129).
- `scripts/migrate_protocol.py`: `_should_run_migrations`.

##### Constraints & Risks
- F1: `along update --dry-run` prints "Would refresh protocol block and run migration engine" per context but not the migration plan itself; the preview hides what would change.
- F2: The root runs the full migration chain on every update although it is at v4.4.5: `_should_run_migrations` returns True whenever `.agents/` exists, and here `.agents/` holds only `.gitkeep` (not Along state). Harmless (one `keep` op) but slow and noisy.
- F3: Tag `v4.4.5` exists locally but was never pushed (`along commit --push` pushes commits, not tags). `along update` reads the remote version from tags, so users see v4.4.4 and are not offered 4.4.5.
- F4: `packages/dashboard-ui` reports "Detected Protocol Version: v1.0.0" (its AGENTS.md carries no version marker) while its recorded migration state was v4.3.0.
- F5: `.gitattributes` keeps the old `.along/DECISIONS.md merge=union` line; the new managed block's `**/.along/DECISIONS.md merge=along-projection` comes later and wins. Correct for a generated DECISIONS.md, but the stale line is misleading.

##### Architectural Patterns
- `along update` is the user path after a reinstall: it migrates every context (`along migrate` covers only the current folder), refreshes managed blocks, registers merge drivers and repairs links.
