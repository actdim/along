---
protocol: along
date: 2026-09-01
slug: typography-gate-verifies-instead-of-rewriting
agent: claude-code
branch: main
commit: pending
summary: 'Closed the typography sanitizer data-loss bug: strict UTF-8 reads, preserved line endings, prose-and-source-only scope with data files opt-in and localized directories never, check-by-default modes, a JSON report callers consume instead of grepping stdout, and hidden directories finally in scope.'
milestone: v3.0.0-global-quality-revision
issues_advanced: [protocol-quality-audit-remediation]
issues_completed: [typography-sanitizer-destroys-non-utf8-files]
decisions: [ADR-2026-09-01--typography-rule-scope]
risks_logged: []
spikes_conducted: []
---

# Session: The Typography Gate Verifies Instead of Rewriting

## Summary

Closed `[bug--typography-sanitizer-destroys-non-utf8-files]`, the highest-severity item in
the audit backlog. `scripts/sanitize_typography.py` performed a repository-wide
read-modify-write with `errors="ignore"` and ran that way unattended before every commit
and every release. Any file that was not valid UTF-8 lost its undecodable bytes
permanently, and because `along_commit.py` stages with `git add -A`, the same command
committed the damage.

The underlying question was not how to write files safely but what the ASCII typography
rule governs. That is now settled and recorded as
`ADR-2026-09-01--typography-rule-scope`: agent-authored prose and source text, data files
opt-in, localized resource directories never, and verification rather than rewriting in
every automated path.

## Work Completed

- **`scripts/alongkit/sanitizer.py` (new)**: owns everything the rule does to a file -
  scope, walking, strict reads, the three modes, exclusions, and the report.
  `alongkit/typography.py` keeps only the character table and the pure string
  transformation, and still touches no files.
  - Reads go through `textio.read_text(strict=True)`. A `UnicodeDecodeError` becomes a
    `SkippedFile` with the decode reason and byte offset; that file is never opened for
    writing.
  - Writes pass `newline=None` through `textio.write_text`, so the line endings a file
    already uses survive. Nothing parses `.gitattributes`, because preserving what is
    there cannot contradict it.
  - `DEFAULT_SUFFIXES` = `.md`, `.py`, `.sh`, `.ps1`, `.bat`. `DATA_SUFFIXES` requires
    `include_data`. `LOCALIZED_DIRS` (`locales/`, `locale/`, `i18n/`, `intl/`,
    `_locales/`, `lang/`, `translations/`) is never scanned in any mode.
  - The walk is `repo.iter_files(include_hidden=True)`, not `glob`, so `.along/**` is
    finally reachable. Every byte order mark strip is reported by path.
  - `Report` carries per-file replacement counts, line numbers, BOM removals, skipped
    files, and an exit code, and serializes to JSON.
- **`scripts/sanitize_typography.py`**: rewritten as a command line over the module.
  `--check` (default, exit 1 on findings), `--dry-run`, `--write` / `--fix`,
  `--include-data`, `--include EXT`, `--exclude GLOB`, `--no-ignore-file`, `--json`,
  `-q`. JSON is the data and goes to stdout; findings are logs and go to stderr; exit 2
  is a usage error.
- **`.alongsanitizeignore`**: optional per-repository exclusion list, one glob per line.
- **`scripts/alongkit/gates.py`**: `run_sanitizer` now runs in-process and returns the
  `Report` instead of a `proc.Result` whose stdout the caller grepped. New
  `typography_gate(repo_root, label, allow_fix=False)` reports findings by file and line
  and returns False; `allow_fix` is the only path that writes. Skipped files are named in
  both outcomes, because those are the ones the old tool destroyed silently.
- **`scripts/along_commit.py` / `scripts/along_version_bump.py`**: both call the gate and
  abort. `--fix-typography` opts into the rewrite, per invocation.
- **`scripts/migrate_protocol.py`**: `sanitize_markdown_typography` had the same lossy
  read before a full rewrite and knew only two dash glyphs. It now runs the shared
  implementation in write mode - correct there, because a migration is an explicitly
  requested mutation - and reports what it skipped.
- **`tests/test_sanitizer.py` (new, 34 cases)**: a temporary fixture tree carrying a
  cp1251 `.md`, a CRLF `.ps1`, a localized `locales/fr.json`, a plain `config.json`, and
  a BOM inside `.along/ISSUES/`. Covers scope policy, byte-identical survival of the
  non-UTF8 file, CRLF preservation, the three modes, BOM reporting, exclusions and the
  ignore file, the JSON summary shape, the CLI contract and its exit codes, and the gate
  behaviour. Two structural guards: no engine may contain the old `"Total files
  sanitized"` string, and both automated paths must reference `gates.typography_gate` and
  `--fix-typography`.
- **`tests/test_skills_and_scripts.py`**: the local helper `run` renamed `run_engine`,
  since `sanitizer.run` now owns that name in the shared package and
  `test_no_engine_redefines_a_shared_helper` correctly flagged the shadow.

## Code Review and Impact

- **Blast radius**: `gates.run_sanitizer` changed its return type from
  `Optional[proc.Result]` to `sanitizer.Report`. Callers are `along_commit.py` and
  `along_version_bump.py`, both updated; a repository-wide search found no others. The
  `code-review-graph` MCP server failed to connect this session
  (`[debt--unpinned-mcp-and-ghost-wiki-query-tool]`), so the impact radius was traced by
  symbol search instead.
- **Behavioral change users will notice**: a commit or release in a repository that
  already contains banned characters now fails instead of silently rewriting the tree.
  That is the intended trade - a refusal the human sees beats a rewrite they do not - and
  `--fix-typography` restores the old behaviour on demand. This repository scans clean
  (226 files, zero findings), so nothing here is blocked.
- **Second behavioral change**: `.along/**` and other hidden directories are now in scope,
  which widens what the commit gate can find. Enforcement in the standalone quality gate
  is still `[bug--quality-gates-skip-hidden-directories]`.
- **ADR compliance**: the module split respects
  `ADR-2026-09-01--shared-engine-package` (one concern per module, no engine redefining a
  package name - verified by the two AST guards) and the strict-read discipline of
  `ADR-2026-09-01--frontmatter-on-ruamel-yaml` (a refusal is the correct outcome for input
  that cannot be parsed).
- **Suite**: 132 -> 166 tests, all passing under `uv run python -m unittest discover tests
  -q`. `tests/test_zz_hermetic_suite.py` confirms the suite left the working tree clean.

## Follow-Ups

- `[bug--quality-gates-skip-hidden-directories]` owns making the standalone typography
  gate in `tests/` walk hidden directories the way the sanitizer now does.
- `[bug--commit-stages-all-and-dead-test-detection]` still has `along_commit.py` staging
  with `git add -A`; the typography fix removes the worst thing that could be staged, not
  the staging behaviour itself.
- `[debt--line-ending-churn-vs-gitattributes]` is now partly relieved: the sanitizer no
  longer forces LF onto CRLF files, but the working tree still carries CRLF copies of
  files declared `eol=lf`.
