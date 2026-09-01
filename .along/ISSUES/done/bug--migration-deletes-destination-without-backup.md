---
protocol: along
protocol_version: 2.2.8
slug: migration-deletes-destination-without-backup
type: bug
status: done
completed: 2026-09-01
priority: critical
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [migration, data-loss, idempotency, dry-run]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [tests-mutate-working-tree]
parent: protocol-quality-audit-remediation
---

# Protocol migration deletes existing destination files without backup or dry-run

## Problem

`scripts/migrate_protocol.py` moves legacy `.agents/` content into `.along/` by deleting
whatever already occupies the destination:

```python
# migrate_protocol.py:360-367
for fname in recognized_files:          # ISSUES.md, DECISIONS.md, HISTORY.md, GLOSSARY.md, ...
    src = os.path.join(agents_dir, fname)
    dst = os.path.join(along_dir, fname)
    if os.path.exists(src):
        if os.path.exists(dst):
            os.remove(dst)              # <- destination content destroyed
        shutil.move(src, dst)
```

The same pattern repeats for directory merges:

```python
# migrate_protocol.py:378-388
for f in files:
    d_file = os.path.join(target_dir, f)
    if os.path.exists(d_file):
        os.remove(d_file)               # <- per-file destination destroyed
    shutil.move(s_file, d_file)
shutil.rmtree(src, ignore_errors=True)
```

If a repository has both a legacy `.agents/` and an already-started `.along/` (a realistic
state during a partial migration, or when two developers migrated on different branches),
the newer `.along/DECISIONS.md`, `HISTORY.md`, and issue files are deleted in favor of the
stale legacy copies. `DECISIONS.md` and `HISTORY.md` are append-only by protocol, so this
is irreversible loss of project memory.

## Aggravating factors

1. **No dry-run.** The engine has no `--check` / `--dry-run` flag. There is no way to see
   what it would do before it does it.
2. **No backup.** No `.bak`, no timestamped copy, no staging area.
3. **No merge for append-only files.** For `DECISIONS.md` and `HISTORY.md` the correct
   operation is a union append (which `.gitattributes` already declares as the git
   strategy), not a replace.
4. **Lossy reads.** `errors="ignore"` when reading markdown for `protocol: along`
   injection (`migrate_protocol.py:409`), same silent-truncation class as
   `[bug--typography-sanitizer-destroys-non-utf8-files]`.
5. **No migration state.** No version marker is written, so every invocation re-runs all
   steps. Idempotency holds only by accident of each step's own guards.
6. **Run against the live repository by the test suite.** `tests/test_skills_and_scripts.py:187-194`
   executes `migrate_protocol.py REPO_ROOT`. During this audit that run rewrote the
   front-matter quoting of a freshly created issue file mid-session. See
   `[bug--tests-mutate-working-tree]`.
7. **Invoked automatically by the installer.** `install.ps1:297-302` runs the migration
   against `$PSScriptRoot` whenever `.along/` or `.agents/` exists, so simply installing
   can mutate a repository.

## Impact

The engine whose job is to protect the migration path is the most likely to destroy the
memory it migrates, and it can be triggered by an unrelated action (installing, or running
tests).

## Requirements

- REQ-1: Add `--dry-run` printing the full planned operation list, and make dry-run the
  default when invoked non-interactively by another tool.
- REQ-2: Never delete a destination file. On collision, choose per file class:
  - append-only (`DECISIONS.md`, `HISTORY.md`): union merge, deduplicated, order preserved;
  - projections (`ISSUES.md`, `docs/INDEX.md`): discard the legacy copy and recompile;
  - entity files: keep destination, move the legacy copy aside as `<name>.legacy.md` and
    report the conflict.
- REQ-3: Write a timestamped backup (for example `.along/.migration-backup/<ts>/`) before
  any destructive step, and print its path.
- REQ-4: Persist migration state (`.along/.protocol-version`) so completed steps are not
  re-executed and the engine can report "already at v2.2.8, nothing to do".
- REQ-5: Read strictly (no `errors="ignore"`) and skip undecodable files with a report.
- REQ-6: Remove the automatic invocation from `install.ps1` / `install.sh`, or gate it
  behind an explicit `-Migrate` flag.
- REQ-7: Tests must run the migration only against temporary fixtures, never `REPO_ROOT`.
- REQ-8: Regression test: repository with populated `.agents/` AND populated `.along/`
  loses no content; both histories are present after migration.

## Acceptance Criteria

- [x] Collision fixture test proves zero content loss.
- [x] `--dry-run` implemented and used by tool-to-tool invocations.
- [x] Backup directory created before destructive steps.
- [x] Migration state file honored; second run is a no-op.
- [x] Installer no longer migrates implicitly.

## Resolution

Every file operation in the engine now goes through `alongkit/migration.py`, a new shared
module holding the collision policy, the on-disk backup, and the plan. `migrate_protocol.py`
contains no `shutil.move`, `shutil.rmtree`, `os.remove` or `os.rename` of its own, and
`TestNoRawFileOperations` fails if one reappears - the point being that each of the
deletions this issue is about was a single call that no test had been written to catch.

| REQ | Where |
| :--- | :--- |
| REQ-1 dry run | `--dry-run` / `--apply` on the engine, and dry run is the default whenever stdin and stdout are not both a TTY. Every step honours it: `sanitizer.Mode.DRY_RUN` in step 5, `--check` into `along_kb_sync` in step 7, `rewrite_inbound_links(dry_run=True)` in step 8. Both modes end with the same report; a dry run also prints the full operation list. |
| REQ-2 never delete a destination | `Migration.adopt` dispatches on `migration.classify`: `union_merge` for `DECISIONS.md` and `HISTORY.md` (section-wise for `## ` files, line-wise otherwise, deduplicated, destination order first), keep-destination for the projections, and `sidecar_path` preservation as `<name>.legacy.md` for everything else. Every collision is reported. |
| REQ-3 backup | `Migration.ensure_backup` copies `.along/` and `.agents/` to `.along/.migration-backup/<timestamp>/` before the first modification of an existing file, and prints the path. It is called from the mutating primitives rather than from each call site, so the guarantee does not depend on remembering it. The directory ignores itself with its own `.gitignore` instead of editing the user's. |
| REQ-4 state | `.along/.protocol-version`, written last so a half-finished run is not recorded as complete. A second run prints `already at v<version>; nothing to do`; `--force` overrides. |
| REQ-5 strict reads | `errors="ignore"` is gone from the engine. `detect_protocol_version`, the entity and session loops, the AGENTS.md rewrite and `.code-review-graph-ignore` all read strictly; an undecodable file is recorded by `note_skipped` and listed in the report. |
| REQ-6 no implicit migration | `install.ps1 -Migrate` and `install.sh --migrate`. Without the flag both print the dry-run and apply commands and touch nothing. `along_update.py` passes `--apply` or `--dry-run` explicitly, matching its own flag. |
| REQ-7 fixtures only | The three tests that invoked the engine now pass `--apply` against temporary trees, and the non-interactive default means a forgotten flag inspects rather than writes. |
| REQ-8 collision regression | `tests/test_migration.py`, 22 cases. The central one builds a repository with a populated `.agents/` beside a populated `.along/` and asserts that both ADRs, both history lines, the destination entity body and the legacy body all survive. |

Found while converting, neither of which had an issue:

- The protocol-injection walk in step 4 would have descended into the backup it had just
  written, rewriting front-matter inside the copy meant to preserve it. `os.walk` now
  prunes `.migration-backup`.
- The two marker-dedup substitutions on `AGENTS.md` used `+` and a hardcoded `\n`, and
  `\s*` swallows the marker's own line ending, so every run over an already-current CRLF
  `AGENTS.md` rewrote two line endings as LF and reported a migration. Now `{2,}`, so they
  fire only on genuine duplication, and the replacement uses the file's own newline. Same
  family as the legacy renames guarded in `eb9fea7`; reading the dry-run plan of a
  repository with nothing to migrate is what exposed it, which is the plan earning its
  keep on its first use.

Deliberately unchanged: graph validation errors still exit 0. Making a cycle fail the run
is a behaviour change for `/along-update` callers and belongs with the honesty pass, not
with the data-loss fix.
