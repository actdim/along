---
protocol: along
protocol_version: 2.2.8
slug: quality-gates-skip-hidden-directories
type: bug
status: open
priority: high
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [gates, glob, tests, coverage, false-green]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [typography-sanitizer-destroys-non-utf8-files, protocol-documentation-drift]
parent: protocol-quality-audit-remediation
---

# Typography, zero-byte, and sanitizer gates never inspect .along/ or any dotfile

## Problem

Three gates enumerate files with `glob.glob(os.path.join(root, '**/*.md'), recursive=True)`:

- `sanitize_typography.py:97-100`
- `tests/test_skills_and_scripts.py:33-47` (`test_00_zero_byte_files_forbidden`)
- `tests/test_skills_and_scripts.py:147-166` (`test_05_clean_typography`)

Python's `glob` does not match names beginning with a dot, and `**` does not descend into
hidden directories. Consequently these gates never see:

- `.along/**` - the entire project memory: issues, sessions, decisions, milestones, risks;
- `.github/**`, `.vscode/**`, `.claude/**`;
- every root dotfile: `.mise.toml`, `.gitattributes`, `.code-review-graph-ignore`.

### Proof

`.mise.toml:1` contains an em-dash (U+2014), which the protocol forbids and the sanitizer's
pattern list explicitly covers (`**/*.toml`):

```text
# .mise.toml - Polyglot developer tools configuration
```

A repository-wide scan including hidden paths found exactly one violation, in the one file
the gates cannot reach.

## Problem 2: the zero-byte gate misses files without an extension

`test_00` enumerates only `*.md, *.py, *.sh, *.ps1, *.json, *.yaml, *.yml`. The repository's
single genuinely empty file has no extension:

```text
LICENSE   0 bytes
```

while `README.md:103-105` states "MIT License. See LICENSE for details." The gate designed
to catch empty files does not catch the empty file that matters.

## Problem 3: substring-based exclusions over-match

```python
# tests/test_skills_and_scripts.py:38, 153
if any(x in filepath for x in [".git", "__pycache__", "scratch", "tests", "node_modules", "dist", ".vite", ...]):
```

- `".git"` matches `.gitattributes`, `.gitignore`, `.github/**`.
- `"dist"` matches any path containing the substring, for example a legitimate
  `docs/topic--distributed-tracing.md`.
- `"tests"` excludes every path containing `tests`, including source files under a
  `src/tests-utils/` directory.

The same substring-exclusion pattern appears in `along_kb_sync.py` and
`sanitize_typography.py:102`.

## Impact

The gates report green while the rules they enforce are violated in the very directory the
protocol treats as its source of truth. This is the "meta test" failure mode: the gate
verifies a subset it happens to reach, and the coverage hole is invisible.

## Requirements

- REQ-1: Replace `glob` enumeration with `os.walk` (or `pathlib.Path.rglob` with explicit
  dotfile handling) so hidden directories and dotfiles are included by default.
- REQ-2: Exclude directories by exact path-segment comparison against a named set, never by
  substring match on the full path. Fix all existing occurrences.
- REQ-3: Zero-byte gate must consider all tracked files (`git ls-files`), with an explicit
  allowlist for legitimately empty ones (`.gitkeep`).
- REQ-4: Consolidate the forbidden-character list into one shared constant. Today the
  sanitizer covers about 30 characters and `test_05` checks 10, so they drift: `U+2022`
  bullet and `U+00AB`/`U+00BB` guillemets are sanitized but never tested.
- REQ-5: Populate `LICENSE` with the MIT text the README promises, and add a test asserting
  every file referenced from `README.md` exists and is non-empty.
- REQ-6: Fix the `.mise.toml` em-dash once the gate can see it.
- REQ-7: Tests: a fixture with a violation inside a hidden directory must fail the gate; a
  path containing the substring `dist` must not be skipped.

## Acceptance Criteria

- [ ] Gates detect violations inside `.along/` and in root dotfiles.
- [ ] Zero-byte gate flags an empty extensionless file.
- [ ] One shared forbidden-character constant used by sanitizer and tests.
- [ ] `LICENSE` non-empty; README-referenced files verified by test.
- [ ] No substring-based path exclusions remain.
