# Living Plan: Domain Exceptions and Error Flow Control Refactoring

## Execution Mode
Role-Based (`along-team`): ~15 production modules plus 11 test modules, crossing the CLI and
hooks subsystems. One commit per phase; phase 5 is a separate issue.

## Revision note (2026-11-08 review)
Measured scope (2026-11-08):
- `sys.exit(` in `scripts/`: 358 total. About 273 are in `scripts/alongkit/commands/`:
  lifecycle 52, issue 49, env 34, ops 32, scratch 31, worktree 15, gates 15, session 13,
  milestone 12, decision 8, telemetry 7, doctor 5. The rest are engine `main()` exits, which are
  legitimate and stay.
- `except ...:` followed by `pass`: 195 across `scripts/`.
- 11 test files use `assertRaises(SystemExit)`: test_along_env, test_along_exec,
  test_autonomous_gate_profile, test_bootstrap, test_commit, test_daemon,
  test_diagnostics_profiles, test_profiles, test_start_guard, test_update_and_hooks_hardening,
  test_worktree.

Corrections to the previous revision:
- The previous plan covered 5 command modules; env, scratch, gates, session, milestone, decision,
  telemetry and doctor were missing.
- Catching `CommandError` in `scripts/alongkit/cli.py` is unnecessary and unreliable. `cli.py`
  runs `along_exec.py` through `runpy.run_path(..., run_name="__main__")`, so
  `along_exec.cli_entry()` is already the boundary and turns everything into `SystemExit`. The
  router can also be resolved from a different install than the `alongkit` copy `cli.py`
  imported, in which case the two `CommandError` classes are different objects. `cli.py` stays
  as is.
- Prefix sniffing (`[Error]`, `Usage:`, `: error:`) is replaced by a convention: exception
  messages carry no prefix; the boundary adds `[Error] `. A separate `usage` field holds the
  usage line.
- `predicates.py:245` already guards with `os.path.isfile`, so splitting out
  `FileNotFoundError` there changes nothing; and recording a diagnostics incident from a hook
  predicate would fire on every tool call while a file stays corrupt. Phase 5 adds dedupe.

## Phase 1: Hierarchy and the single boundary
1. `scripts/alongkit/exceptions.py`:
   `AlongError(Exception)`; `CommandError(AlongError)` with `message`, `exit_code=1`,
   `usage: str | None = None`; `ValidationError(CommandError)` with `exit_code=2`.
   Re-export from `scripts/alongkit/__init__.py`.
2. `scripts/along_exec.py` `cli_entry()`: add `except CommandError` before the generic handler:
   print `[Error] <message>` and, when set, `Usage: <usage>` to stderr; `sys.exit(exc.exit_code)`;
   re-raise when `ALONG_DEBUG` is set. Keep `KeyboardInterrupt -> 130` and the generic handler.
3. Make `along_exec.main()` treat a router's `int` return as the exit code (unchanged contract).
4. Do not inherit existing exceptions (`ProcessError`, `FrontmatterError`, `EnvConfigError`,
   `MissingDependency`) from `AlongError` in this issue; that changes `except` matching for
   callers and is not needed for the goal.

## Phase 2: commands/common.py
`require_entity_name` -> `ValidationError(f"Invalid name '{name}': entity names cannot start with '-'.", usage=usage)`;
`check_unknown_args` -> `ValidationError(f"{prog}: unrecognized arguments: ...")`.
Stderr text and exit codes stay byte-compatible with today; add golden tests that run
`along_exec.py` as a subprocess and compare stderr + exit code before/after.

## Phase 3: command modules, one commit each, largest first
lifecycle, issue, env, ops, scratch, worktree, gates, session, milestone, decision, telemetry,
doctor. For each module:
1. Capture golden stderr/exit code for its error paths (subprocess through `along_exec.py`).
2. Replace `print(...); sys.exit(n)` with `raise CommandError/ValidationError`.
3. Update the tests that call handlers directly: assert the domain exception (or keep asserting
   `SystemExit` when they go through `cli_entry` / `run_cli`).
4. `_cli_approval_or_exit` keeps its name until all callers are migrated, then is renamed
   `_cli_approval_or_raise` with an alias for one release.
Exit codes: 0 success, 1 operational, 2 usage/validation, 130 SIGINT. Unchanged.

## Phase 4: tests
`tests/test_domain_exceptions.py`: hierarchy, default exit codes, boundary formatting (one
`[Error]` prefix, usage line), `ALONG_DEBUG` re-raise, and a structural test that fails if a new
`sys.exit(` appears in `scripts/alongkit/commands/` (allow-list for intentional cases).

## Phase 5 (separate issue): silent `except ...: pass` triage
1. Classify the 195 sites: benign optional state (keep, add a one-line comment), corruption of
   state Along owns (record), or genuine bug (fix).
2. For "record": `DiagnosticsStore.record_incident(component=..., error_message=...,
   event_type="state_corruption", repo_root=...)`, deduped per (component, path, mtime) so a
   corrupt file is reported once, never per hook invocation.
3. Hooks stay fail-open: a recording failure is swallowed.
4. Tests run with the isolated home env so incidents never reach `~/.along/`.

## Verification
- Per phase: `python .along/scripts/test.py` targeted modules, golden stderr tests, then the full
  suite; `python scripts/sanitize_typography.py --check`.

## Sequencing
After `task--refactor-cli-chdir-common` (shared files `along_exec.py`, `cli.py`, `common.py`).
