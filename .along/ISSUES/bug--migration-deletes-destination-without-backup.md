---
protocol: along
protocol_version: 2.2.8
slug: migration-deletes-destination-without-backup
type: bug
status: open
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

- [ ] Collision fixture test proves zero content loss.
- [ ] `--dry-run` implemented and used by tool-to-tool invocations.
- [ ] Backup directory created before destructive steps.
- [ ] Migration state file honored; second run is a no-op.
- [ ] Installer no longer migrates implicitly.
