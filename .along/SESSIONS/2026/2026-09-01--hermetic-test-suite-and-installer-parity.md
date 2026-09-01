---
protocol: along
date: 2026-09-01
slug: hermetic-test-suite-and-installer-parity
agent: claude-code
branch: main
commit: pending
summary: 'Made the test suite hermetic: every engine invocation targets a tests/hermetic.py fixture instead of the repository root, two meta-gates prove the suite leaves the working tree clean, and the installer test now compares artifact sets rather than skill names.'
milestone: v3.0.0-global-quality-revision
issues_advanced: [protocol-quality-audit-remediation]
issues_completed: [tests-mutate-working-tree]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Hermetic Test Suite and Installer Parity

## Summary

Closed `[bug--tests-mutate-working-tree]`. Three tests ran real engines with `REPO_ROOT` as
the target, including `migrate_protocol.py`, which normalizes front-matter, sanitizes
typography, and rewrites Markdown links across the whole tree with no `--dry-run`. Running
the suite could therefore edit files a developer was working on, and once did.

## Work Completed

- **`tests/hermetic.py` (new)**: `make_repo_fixture()` / `repo_fixture()` build a throwaway
  repository that looks like a current Along project (managed protocol block, one valid
  entity, one ADR, the board, a small `docs/` Knowledge Base). Deliberately not a git
  repository, so nothing a test runs can reach a real index or history. Writing goes through
  the shared `alongkit.textio.write_text`, not a local copy.
- **Retargeted engine tests** in `tests/test_skills_and_scripts.py`: `test_06` (dashboard),
  `test_07` (migration), `test_08` (update check-only) and `test_12` (`along_exec` entity
  lifecycle). `test_12` receives the fixture as `cwd`, because `along_exec` resolves its
  target from the working directory rather than from an argument.
- **`test_06` corrected, not just moved**: its two assertions that `.along/DASHBOARD.md` and
  `.along/dashboard.html` existed in `REPO_ROOT` were vacuous. `--cli` writes nothing, so
  they only proved that two committed artifacts were still checked in. The writer is
  `--export`, which is what the test now exercises, into the fixture. Consequence for the
  issue text: the committed-dashboard churn is not caused by the suite; it stays with
  `[debt--generated-dashboard-artifact-committed]`.
- **`test_09` replaced by an artifact-parity contract** plus `test_09b`: eleven artifacts
  (skill folders, legacy purge, rule packs, engines in `~/.along/bin`, `__pycache__`
  stripping, default config, OpenCode commands, `protocol.md` helper, short-alias cleanup,
  MCP registration, closing migration) each with a probe for both installers, and an exact
  set comparison of the two legacy purge lists.
- **`install.sh` brought to parity**: it never installed `rules/` at all, and never removed
  the un-namespaced OpenCode command aliases. Both added. The rules copy writes over the
  destination instead of deleting it first, so a user's own rule files survive; the
  destructive `Remove-Item -Recurse -Force` in `install.ps1` is untouched and remains with
  `[bug--installer-parity-and-destructive-rules-overwrite]`.
- **`tests/test_zz_hermetic_suite.py` (new)**: named to sort last under `unittest discover`.
  `test_01` compares `git status --porcelain -u` from import time against the end of the
  suite (the baseline is read twice, so a stale-index "racily clean" flip is not reported as
  a mutation). `test_02` parses every `tests/*.py` and rejects a command-shaped list literal
  built with `REPO_ROOT` as an argument, so the regression is caught when it is written
  rather than when it happens to do damage.
- **Documentation**: hermetic-test rule added to the managed protocol block
  (`skills/along-init/protocol.md` and the projection in `AGENTS.md`), a test-suite bullet in
  `AGENTS.md` Project specifics, section 6 of `docs/topic--setup-and-workflow.md` with a
  worked example, and the structural-guards section of `docs/topic--architecture.md`.

## Code Review & Blast Radius

- **Tests**: 129 -> 132, zero failures, via `python .along/scripts/test.py`. The bare
  interpreter lacks `ruamel.yaml`; the documented runner resolves it through `uv`.
- **Gates verified rather than assumed**: with an emptied baseline the porcelain gate fails
  and names every entry; the AST gate flags `[sys.executable, mig_script, REPO_ROOT]` and
  leaves `os.path.join(REPO_ROOT, ...)` and plain data lists alone. Each new installer probe
  matches exactly one place in the source, so removing that code fails the test.
- **Diff audit**: `git diff --numstat` shows no unexpected reductions; every deletion in
  `tests/test_skills_and_scripts.py` is a line replaced by its hermetic equivalent.
- **Blast radius**: `tests/hermetic.py` is new and imported only by the test suite. The
  `install.sh` change alters what an installation puts on disk (adds `~/.<tool>/rules/`,
  deletes legacy OpenCode alias commands) and mirrors behavior `install.ps1` already had.
  `bash -n install.sh` and `python -m compileall` pass. `code-review-graph` MCP was
  unavailable this session (connection closed), so impact was traced by search.
- **Link integrity**: 54 links checked repository-wide, zero broken, read-only.
- **Entity metadata note**: this log was written directly rather than through
  `along_exec.py session create`, whose template hardcodes `agent: antigravity` and
  `milestone: v2.2.0-along` (`[bug--issue-create-stamps-wrong-agent-and-milestone]`).
- **Front-matter repair**: the issue file carried `protocol_version: 2.2.8` unquoted, the
  exact corruption it documents, inflicted by `test_07` in an earlier session. Quotes
  restored before closing.

## Follow-ups (not in scope, already tracked)

- `[bug--migration-deletes-destination-without-backup]`: the migration engine still has no
  `--dry-run`.
- `[bug--installer-parity-and-destructive-rules-overwrite]`: the destructive rules overwrite
  in `install.ps1`.
- `[debt--generated-dashboard-artifact-committed]`: the 205 KB `.along/dashboard.html` is
  still committed and stale.
- The remaining test modules (`test_feedback`, `test_kb_search`, `test_issue_lifecycle`,
  `test_scan_deps`, `test_alongkit`) are already hermetic or read-only; they can adopt
  `tests/hermetic.py` opportunistically instead of building fixtures inline.
