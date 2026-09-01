---
protocol: along
protocol_version: "2.2.10"
date: 2026-09-01
slug: migration-merges-instead-of-overwriting
agent: claude-code
branch: main
commit: 4fd4573
summary: The migration engine can no longer delete a destination, migrate unasked, or run without a plan and a backup.
milestone: v3.0.0-global-quality-revision
issues_advanced: [protocol-quality-audit-remediation]
issues_completed: [migration-deletes-destination-without-backup]
decisions: [ADR-2026-09-01--migration-never-deletes-a-destination]
risks_logged: []
spikes_conducted: []
---

# Migration merges instead of overwriting

Third of the four destructive engines in step 2 of the audit remediation, after the
typography sanitizer and the release engine. `[bug--migration-deletes-destination-without-backup]`
is closed.

## What was wrong

`migrate_protocol.py` moved legacy `.agents/` content into `.along/` by calling
`os.remove(dst)` and then `shutil.move`, repeated per file when merging directories. A
repository holding both directories - a partial migration, or two developers migrating on
separate branches - lost the newer `DECISIONS.md`, `HISTORY.md` and issue files to the
stale legacy copies. The first two are append-only by protocol, and `.gitattributes`
already declares `merge=union` for precisely the case the engine settled by deletion.

Four things kept it from being survivable: no dry run, no backup, `errors="ignore"` on
reads that preceded a rewrite, and no migration state, so eight steps re-ran on every
invocation. Two of the ways it ran were invocations nobody had asked for - `install.ps1`
against `$PSScriptRoot`, and the test suite against `REPO_ROOT`.

## What changed

- **`scripts/alongkit/migration.py`** (new). `Migration` records every intention and either
  performs it or, in dry-run mode, only prints it; `classify` and `adopt` implement the
  collision policy; `union_merge` merges append-only files section-wise or line-wise;
  `ensure_backup` copies the state directories to `.along/.migration-backup/<timestamp>/`
  before the first modification. It is not `alongkit.transaction`: a release needs an
  in-memory snapshot to undo everything at once, a migration needs a durable copy that
  outlives the process, because it is run, inspected, and re-run.
- **`scripts/migrate_protocol.py`**. Every step takes the `Migration` context; the engine
  now contains no `shutil` or `os.remove` call of its own. Argument parsing added
  (`--dry-run` / `--apply` / `--force` / `--no-backup`), with dry run the default whenever
  stdin and stdout are not both a TTY. All reads strict. `.along/.protocol-version`
  written last, so a run that died halfway is not recorded as complete.
- **`install.ps1` / `install.sh`**. Migration behind `-Migrate` / `--migrate`; without it
  both print the two commands and touch nothing.
- **`scripts/along_update.py`**. Passes `--apply` or `--dry-run` explicitly, matching its
  own flag.
- **`tests/test_migration.py`** (new, 24 cases) and three existing tests moved onto
  `--apply`.

## Code review and impact

Reviewed the diff for the failure modes this issue is about. Two finds, neither with an
issue of its own:

- The protocol-injection walk in step 4 would have descended into the backup it had just
  written and rewritten front-matter inside the copy meant to preserve it. `os.walk` now
  prunes `.migration-backup`.
- Running the finished engine against this repository, the plan announced an `AGENTS.md`
  rewrite in a repository with nothing to migrate. The marker-dedup substitutions used `+`
  and a hardcoded `\n`, and their `\s*` swallows the marker's own line ending, so each run
  converted two CRLF lines to LF. Now `{2,}` and the file's own newline. A dry run that
  reports an operation nobody can justify is exactly what the plan is for, and it paid for
  itself the first time it ran.

Blast radius, checked by call site rather than by graph (the `code-review-graph` MCP
server fails to connect in this session, `CONNECTION_CLOSED`):

- `migrate_protocol.run_migrations` gained keyword parameters and now returns an exit code;
  its only callers are `main`, `along_update.py` and `along_exec.py migrate`, all as a
  subprocess. Every step function's signature changed, and all of them are private to the
  module.
- The mode change is the one behavioural break for existing callers: an unflagged
  invocation from a script now inspects instead of writing. That is the fix, and the two
  in-repository callers were updated with it.
- `alongkit/__init__.py` exports the new module; the duplicate-name guard passes, so
  nothing outside the package redefines any of its helpers.

Suite: 185 -> 209 tests, all passing under `uv run`. The hermetic meta-test confirms the run left
the working tree clean. Typography gate clean over 233 files.

## Documentation

`docs/topic--migrations.md` gained the policy section and the corrected invocation, and no
longer calls the steps non-destructive without saying what makes them so.
`docs/topic--architecture.md` gained "A migration merges; it does not choose a winner",
placed after the release-engine section because the two are the same defect in different
shapes. `AGENTS.md` gained the Migration Path bullet beside the Typography Gate and
Release Path ones. `skills/along-init/SKILL.md` step 4 now shows both commands.
