---
protocol: along
protocol_version: 2.2.8
slug: typography-sanitizer-destroys-non-utf8-files
type: bug
status: done
completed: 2026-09-01
priority: critical
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [sanitizer, data-loss, encoding, i18n, line-endings]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [quality-gates-skip-hidden-directories, line-ending-churn-vs-gitattributes]
parent: protocol-quality-audit-remediation
---

# Typography sanitizer silently destroys content and runs unattended before every commit

## Problem

`scripts/sanitize_typography.py` performs a repository-wide read-modify-write over
`**/*.md`, `*.py`, `*.sh`, `*.ps1`, `*.bat`, `*.json`, `*.yaml`, `*.yml`, `*.toml`.

### 1. Lossy read followed by full rewrite

```python
# sanitize_typography.py:76-89
with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()
...
with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.write(cleaned)
```

`errors='ignore'` drops every byte that is not valid UTF-8, and the file is then
overwritten with the truncated result. Any cp1251 / latin-1 / UTF-16 file in the repository
loses data permanently, with no warning and no backup. This directly violates the
protocol's own "Zero Unintended Deletions" and "Anti-Stub & Size Regression Invariant".

### 2. Destroys legitimate non-English content

The replacement map rewrites guillemets (`U+00AB` / `U+00BB`), the typographic apostrophe
(`U+2019`), the ellipsis glyph (`U+2026`), and NBSP (`U+00A0`) inside **any** `.json` /
`.yaml` / `.toml` / `.py` file. That includes i18n resource bundles, test fixtures, and
localized user-facing strings. A French `locales/fr.json` or a Russian message catalog is
corrupted as a side effect of a commit.

(Characters are named by code point here on purpose: the protocol forbids the literal glyphs
in repository text, so documenting them requires the `U+XXXX` notation rather than the
characters themselves. The first version of this issue file violated that rule.)

### 3. Forces LF onto files that `.gitattributes` declares CRLF

`newline='\n'` is applied to `.ps1` and `.bat` too, while `.gitattributes:9-10` declares:

```gitattributes
*.ps1 text eol=crlf
*.bat text eol=crlf
```

The sanitizer and the repository configuration actively fight each other.

### 4. No safety controls

No `--dry-run`, no `--include` / `--exclude`, no ignore file, no diff report, no summary of
what changed. Detection of "did anything change" is done by string-matching the tool's own
stdout:

```python
# along_commit.py:31
if "Total files sanitized: 0" not in res.stdout and res.stdout.strip():
```

### 5. Runs unattended in two automated paths

- `along_commit.py:134` - before every commit.
- `along_version_bump.py:442` - during every release.

So the most destructive engine in the repository is the one with the least human oversight.

## Impact

A single `/along-commit` in a repository containing one non-UTF8 file, or any localized
resource file, silently corrupts user content. There is no undo beyond git, and if the
corruption is staged and committed by the same command (`git add -A`, see
`[bug--commit-stages-all-and-dead-test-detection]`), the damage is committed too.

## Design question to settle

Banning non-ASCII typography inside **all source and data files** is itself questionable
for any project with internationalized content. The rule makes sense for agent-authored
markdown and docstrings; applying it to arbitrary JSON/YAML data is out of scope and
harmful. This issue should decide the boundary and record it as an ADR.

## Requirements

- REQ-1: Never use `errors='ignore'` before a rewrite. Read strictly; on `UnicodeDecodeError`
  skip the file, report it, and continue.
- REQ-2: Preserve the existing line endings of each file; honor `.gitattributes`.
  Never normalize newlines as a side effect of typography cleanup.
- REQ-3: Restrict the default scope to markdown and source comments/docstrings. Data files
  (`.json`, `.yaml`, `.toml`) must be opt-in, and localized resource directories excluded.
- REQ-4: Support `--dry-run` (default in CI-style checks), `--check` (non-zero exit, no
  writes), and a `.alongsanitizeignore` or `--exclude` mechanism.
- REQ-5: Emit a machine-readable summary (JSON) of file, line, and replacement counts.
  Callers must consume that instead of grepping stdout text.
- REQ-6: Automated paths (`along-commit`, `version-bump`) must default to `--check` and
  refuse to rewrite silently. Rewriting requires an explicit flag or user confirmation.
- REQ-7: Record an ADR defining which file classes the ASCII typography rule governs.
- REQ-8: BOM handling is already partly correct and must stay: `REPLACEMENTS` maps `U+FEFF`
  to the empty string, and the file is read with `encoding='utf-8'` rather than `utf-8-sig`,
  so a leading BOM decodes to a U+FEFF character and is stripped on rewrite. Two gaps
  remain: (a) `glob` never reaches hidden directories or dotfiles, so a BOM in `.along/**`
  or in a root dotfile is never stripped, and (b) the strip is silent. The sanitizer must
  report each BOM removal by path, and must not be the mechanism that enforces the rule:
  enforcement belongs to the gate, see `[bug--quality-gates-skip-hidden-directories]` REQ-8.
- REQ-9: Tests: non-UTF8 file is skipped and left byte-identical; CRLF file keeps CRLF;
  a localized JSON fixture is untouched by default; `--check` exits non-zero without writing;
  a BOM-prefixed fixture inside a hidden directory is detected and reported.

## Acceptance Criteria

- [x] A cp1251 fixture survives a sanitizer run byte-for-byte.
- [x] A `.ps1` fixture keeps CRLF after a run.
- [x] `--dry-run` / `--check` implemented; commit path uses check mode by default.
- [x] ADR recorded for the typography rule scope.
- [x] Callers no longer parse stdout strings.

## Resolution

`alongkit/sanitizer.py` is the new home for everything the rule does to a file;
`alongkit/typography.py` keeps only the character table and the pure transformation.
`scripts/sanitize_typography.py` is now a command line over it.

| REQ | Where |
| :--- | :--- |
| REQ-1 strict reads | `sanitizer.inspect_file` reads through `textio.read_text(strict=True)`; a `UnicodeDecodeError` becomes a `SkippedFile` carrying the decode reason, and the file is never opened for writing. |
| REQ-2 line endings | Reads use `newline=""` and writes pass `newline=None`, so the bytes a file uses are the bytes it keeps. Nothing parses `.gitattributes`, because preserving what is there cannot contradict it. |
| REQ-3 scope | `DEFAULT_SUFFIXES` is `.md`, `.py`, `.sh`, `.ps1`, `.bat`; `DATA_SUFFIXES` needs `--include-data`; `LOCALIZED_DIRS` is never scanned in any mode. |
| REQ-4 controls | `Mode.CHECK` (default), `Mode.DRY_RUN`, `Mode.WRITE`; `--exclude` globs and `.alongsanitizeignore`. |
| REQ-5 machine-readable | `sanitizer.Report.as_dict()`, `--json` on stdout, human output on stderr. `tests/test_sanitizer.py` fails if `"Total files sanitized"` reappears in any engine. |
| REQ-6 automated paths | `gates.typography_gate` runs in check mode and returns False; `along_commit.py` and `along_version_bump.py` abort unless `--fix-typography` is passed. |
| REQ-7 ADR | `ADR-2026-09-01--typography-rule-scope`. |
| REQ-8 BOM | The walk uses `repo.iter_files(include_hidden=True)`, so `.along/**` is reachable; every strip is listed in `Report.boms_removed` and named in the printed report. Enforcement stays with `[bug--quality-gates-skip-hidden-directories]`. |
| REQ-9 tests | `tests/test_sanitizer.py`, 34 cases over a temporary fixture tree carrying a cp1251 file, a CRLF `.ps1`, a localized `locales/fr.json`, a data `config.json`, and a BOM inside `.along/`. |

Also fixed in passing: `migrate_protocol.sanitize_markdown_typography` used the same
`errors="ignore"` read before a full rewrite and knew only two dash glyphs; it now runs
the shared implementation in write mode, because a migration is an explicitly requested
mutation. The test helper `run` in `tests/test_skills_and_scripts.py` was renamed
`run_engine`, since `sanitizer.run` now owns that name in the shared package.
