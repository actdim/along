---
protocol: along
protocol_version: "4.4.6"
slug: update-maintenance-friction
type: bug
status: done
completed: 2026-10-06
priority: high
created: 2026-10-06
updated: 2026-10-06
agent: claude-code
tags: [gates, update, maintenance, entities, migration]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--subproject-model-overdetection]
---

# Update and maintenance friction: maintenance commands held, archived issues fail update, migration backups pile up

Field reports (2026-10-06) of a slow, failing `along update`, verified against the code:

1. Along maintenance commands (`along update`, `along init`, `along migrate`, `along hook install`,
   `along git setup|sync`, `along rules attach|restore`) are not in the plan gate's pass list
   (`shellparse._ALONG_STATE`), so a bound session without an approved plan is held running
   them. The reverse hole exists too: `along doctor --fix` writes files
   (`entities.drop_dangling_milestones`) but `_ALONG_READ` classifies every `doctor` as read-only.
2. Archived issues (`.along/ISSUES/done/`) with values a newer schema rejects (`type: refactor`,
   a removed milestone) are errors in `validate_entities`. `along update` runs `along issue sync`
   per context (`apply_migration_to_context`); its entity gate fails the update when such a
   problem is new against `HEAD` (file moved by migration, untracked, no `HEAD`).
3. `Migration.ensure_backup` copies the whole `.along/` (diagnostics, blackboards, artifacts,
   worktrees included) into `.along/.migration-backup/<timestamp>/` on every applying run, with no
   retention: snapshots accumulate (megabytes per snapshot) and the copy is a likely
   share of the update's run time. Rule-pack backups (`rules attach` on conflict,
   `rules restore`) land in the same directory without writing its self-ignore `.gitignore`.

Subproject-related update friction (root-only gate excludes, sibling refs, nested installs) is
tracked in [bug--subproject-model-overdetection].

## Requirements
- REQ-1: Maintenance subcommands (`update`, `init`, `migrate`, `hook install`, `git setup`,
  `git sync`, `rules attach`, `rules restore`) pass the plan gate. Removal (`uninstall`,
  `--uninstall`), `commit` and `bump` do not.
- REQ-2: `along doctor --fix` is not classified read-only.
- REQ-3: Schema findings on archived issues (invalid enums, missing dates, slug mismatch,
  dangling milestone) are warnings marked `(archived issue)`; open issues keep them as errors.
  Dangling issue references (`parent`, `blocked_by`, `related`, `superseded_by`,
  `duplicate_of`) stay errors everywhere: they guard against deleting a referenced entity.
  `along doctor --entities --fix` still drops dangling milestones of archived issues.
- REQ-4: Migration backups keep the newest N snapshots (default 5) and skip machine-local
  state (`diagnostics`, `.session`, `artifacts`, `worktrees`). Every writer of
  `.along/.migration-backup/` ensures its `.gitignore`.

## Acceptance Criteria
- [x] REQ-1..REQ-4 covered by hermetic tests
- [x] Automated tests passing

## Resolution
- REQ-1: `shellparse._ALONG_MAINTENANCE` checked by `is_along_state_command`
  (`_is_maintenance_subcommand`, `uninstall` excluded); `along_commit_issue` is unchanged.
- REQ-2: `shellparse._is_read_subcommand` drops `doctor ... --fix` from the read-only set.
- REQ-3: `validate_entities` routes the schema findings of archived issues through
  `_archived_reporter` (warnings, suffix `(archived issue)`); dangling issue references stay
  errors. `drop_dangling_milestones` reads errors and warnings.
- REQ-4: `migration.backup_root` (self-ignore file, shared with `rules attach/restore`),
  `migration.BACKUP_SKIP`, `migration.prune_backups` (`BACKUP_KEEP = 5`).
- Tests: `tests/test_update_maintenance_friction.py`. Docs: `topic--runtime-hooks-and-gates`,
  `topic--migrations`, `topic--architecture`.
- Update slowness was not profiled; the full-state backup copy was the one cost found.
