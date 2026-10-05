---
protocol: along
protocol_version: "4.4.5"
slug: along-update-dev-repo
type: task
status: done
completed: 2026-10-05
priority: medium
created: 2026-10-05
updated: 2026-10-05
agent: claude-code
tags: [update, migration, maintenance]
blocked_by: []
related: [bug--diagnostics-files-stay-tracked]
---

# Run along update in the dev repository after the global reinstall

After the global reinstall (`install.ps1 -Target all`, v4.4.5 with migration Step 14), run
`along update` in this repository: it migrates every context (`migrate_protocol.py --apply` per
context), refreshes the managed AGENTS.md block and repairs inbound links. This is the path users
are told to take, so running it here checks it end to end.

## Acceptance Criteria
- [x] `along update --dry-run` reviewed (plus `along migrate --dry-run` per context, since the update preview hides the migration plan).
- [x] `along update` applied; every resulting change explained: `.gitattributes` managed merge-driver block (drivers were never registered here), `packages/dashboard-ui/.along/.protocol-version` 4.3.0 -> 4.4.5.
- [x] Automated tests passing (964, `along test` from the global install)

## Findings (not fixed here)
- F1: `along update --dry-run` does not show the migration plan of each context.
- F2: `_should_run_migrations` re-runs the full chain whenever `.agents/` exists, even when it holds only a `.gitkeep`.
- F3: Tag `v4.4.5` was never pushed (`along commit --push` pushes no tags), so `along update` reports remote v4.4.4.
- F4: `packages/dashboard-ui` AGENTS.md carries no protocol version marker (detected as v1.0.0).
- F5: `.gitattributes` keeps a stale `.along/DECISIONS.md merge=union` line, overridden by the managed block.
