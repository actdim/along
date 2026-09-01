---
protocol: along
date: 2026-09-01
slug: shared-engine-package-and-frontmatter-on-ruamel
agent: claude-code
branch: main
commit: pending
summary: 'Extracted scripts/alongkit/ as the single implementation behind the engines, moved front-matter onto ruamel.yaml round-trip, and collapsed the subprocess encoding defect from 25+ call sites into one shared helper.'
milestone: v3.0.0-global-quality-revision
issues_advanced: [protocol-quality-audit-remediation]
issues_completed: [extract-shared-python-library, handrolled-yaml-loses-block-lists, subprocess-encoding-breaks-on-non-utf8-locale]
decisions: [ADR-2026-09-01--shared-engine-package, ADR-2026-09-01--frontmatter-on-ruamel-yaml]
risks_logged: []
spikes_conducted: []
---

# Session: Shared Engine Package and Front-matter on ruamel.yaml

## Summary

Step 1 of `[debt--protocol-quality-audit-remediation]`, the foundation step. Three issues
closed together because they own the same code: the shared package, the front-matter
implementation, and the subprocess conventions.

## Work Completed

### 1. `scripts/alongkit/` - the shared implementation

Twelve modules, one per shared concern: `repo`, `frontmatter`, `entities`, `proc`, `textio`,
`markdown`, `typography`, `gates`, `semver`, `version`, `bootstrap`, `cli`. Every engine and
`dashboard/core/collector.py` converted; all duplicate helper definitions deleted:

| Helper | Copies before | After |
| :--- | :--- | :--- |
| `find_repo_root` | 5, disagreeing on root markers | `repo.find_repo_root` |
| Front-matter parse and dump | 4 (kb_search, kb_sync, migrate, dashboard) | `frontmatter` |
| `parse_semver` | 2 | `semver.parse` |
| `safe_relpath` | 2 | `repo.safe_relpath` |
| `run_precommit_tests` | 2 | `gates.run_repository_tests` |
| `sanitize_typography` | 2 | `gates.run_sanitizer` |
| Forbidden-character table | 2 (sanitizer, test gate) | `typography.REPLACEMENTS` |
| Protocol version constant | 4, one drifted to 2.1.6 | `version.CURRENT_PROTOCOL_VERSION` |
| Ignore-directory set | 2 | `repo.IGNORED_DIRS` |
| ADR header format | 3 (writer, validator, reader) | `entities` |

`pyproject.toml` added: hatchling, the `ruamel.yaml` dependency, the `dash` extra, a `dev`
dependency group, and the `along` console entry point delegating to the `along_exec.py`
router rather than duplicating its dispatch table. Both installers now carry the package
next to the engines, which is what makes the flat `~/.along/bin/` install work.

### 2. Front-matter on ruamel.yaml

Reads are strict and refuse a block they cannot parse. Edits name individual keys and leave
every other line byte-identical: comments, key order, block sequences, quoting style, and
line endings all survive. Measured over this repository: a no-op read-and-write is
byte-identical for 123 of 123 entity files.

Six committed files were unreadable by any strict YAML reader (unquoted `title:` or
`summary:` containing a colon): four milestones, two session logs. Repaired, one line each.
While measuring, `migrate_protocol.py` was caught reverting that repair on every test run,
because the old writer re-emitted those values unquoted and the test suite runs the
migration against the live working tree.

### 3. Subprocess encoding

Every capturing call goes through `proc.run_capture`, which fixes `encoding="utf-8"`,
`errors="replace"`, and a UTF-8 child environment. Zero `capture_output` sites remain
outside that module. Verified on the machine that reported the defect (Windows 11, cp1251
locale): the full suite passes with no locale override, and a child process emitting
Cyrillic, accented Latin, and CJK text plus an em dash decodes intact.

### 4. Defects found in passing

None of these had an issue; each was a real fault in code being converted:

- `along_commit.py` called `json.load` without importing `json`, inside a bare
  `except Exception: pass`. The npm test gate was therefore a silent no-op in any
  repository without a `tests/` directory.
- `along_feedback.py` hardcoded `CURRENT_VERSION = "2.1.6"`, so every bug report submitted
  through `/along-feedback` carried a version three releases stale.
- `migrate_protocol.py`'s entity graph builder crashed on a file whose front-matter does
  not parse.
- `tests/test_skills_and_scripts.py` asked uv for a package named `httpx2` and invoked `uv`
  unconditionally, so the dashboard fallback path had never worked and raised
  FileNotFoundError instead of skipping.

## Code Review and Impact

- Suite: 57 tests before, 125 after. `tests/test_alongkit.py` covers each module directly;
  previous coverage was end-to-end engine tests only.
- Structural guards: two AST scans fail if a name is defined at module level in two
  engines, or if an engine shadows a package helper. A third runs an engine from a
  temporary flat directory copy against a consumer repository. A fourth asserts both
  installers carry the package, a fifth that the wheel manifest lists every engine, a
  sixth that the runtime dependency list has exactly one home.
- Idempotency verified by running `migrate_protocol.py`, `along_kb_sync.py`, and
  `along_dep_scan.py` against the live repository twice each: no file changes after the
  first run.
- Blast radius: the `code-review-graph` MCP server failed to connect this session
  (`CONNECTION_CLOSED`), so impact analysis was done by AST scan and grep instead. That
  server is `[debt--unpinned-mcp-and-ghost-wiki-query-tool]`.
- Behaviour changes a reader should know about: `find_repo_root` in `along_commit.py` now
  also recognizes `AGENTS.md` as a root marker, matching the other four former copies;
  front-matter values are quoted by the writer, so callers no longer pre-quote; an unset
  key reads as the empty string and an ISO date stays a string, both deliberate deviations
  from PyYAML recorded in the ADR.

## Documentation

- `docs/topic--architecture.md`: new section 5, the engine implementation layer, with the
  module ownership table, the three invocation paths, and the structural guards.
- `docs/topic--setup-and-workflow.md`: new section 2, Python runtime and dependencies.
- `AGENTS.md`: engine source and the single-definition rule under Project specifics.
- `skills/along-kb-sync/SKILL.md` and `docs/topic--skills-reference.md`: the "zero external
  dependencies" claim was no longer true and now states the single dependency.

## Deliberately Not Done

Each belongs to an open issue and would have widened this diff without its own tests:

- Rewriting the eighteen `SKILL.md` usage blocks onto the `along` entry point
  (`[bug--skill-commands-reference-missing-script-paths]`).
- Making the gates scan hidden directories. `repo.iter_files` takes `include_hidden`, and
  the current default reproduces today's behaviour: the gates see 43 of 163 markdown files
  (`[bug--quality-gates-skip-hidden-directories]`, `[bug--link-gates-skip-along-directory]`).
- Sanitizer policy: `--check` and `--dry-run` modes, scope limits, and refusing to rewrite
  unattended (`[bug--typography-sanitizer-destroys-non-utf8-files]`).
- Tests still run engines against the live working tree. Now idempotent, so harmless, but
  still wrong (`[bug--tests-mutate-working-tree]`).
