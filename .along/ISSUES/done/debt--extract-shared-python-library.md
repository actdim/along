---
protocol: along
protocol_version: 2.2.8
slug: extract-shared-python-library
type: debt
status: done
completed: 2026-09-01
priority: high
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [architecture, duplication, refactoring, foundation]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [handrolled-yaml-loses-block-lists, skill-commands-reference-missing-script-paths, subprocess-encoding-breaks-on-non-utf8-locale]
parent: protocol-quality-audit-remediation
---

# No shared library: helpers are copy-pasted across twelve standalone scripts

## Problem

`scripts/` contains twelve independent scripts (about 250 KB) with no shared module. Core
helpers exist in multiple divergent copies:

### `find_repo_root` - five copies

```text
scripts/along_commit.py:17          checks .along, .git
scripts/along_exec.py:59            checks .along, .git, AGENTS.md
scripts/along_dep_scan.py:72        typed signature
scripts/along_history_sync.py:29    typed signature
scripts/along_version_bump.py:22    different signature
```

They disagree on what constitutes a repository root, so different engines can resolve
different roots from the same working directory.

### `parse_frontmatter` - three copies

```text
scripts/along_kb_sync.py:38
scripts/along_kb_search.py:9
dashboard/core/collector.py:33
```

All three share the defects in `[bug--handrolled-yaml-loses-block-lists]`, and fixing them
means fixing three places or accepting divergence between search, sync, and the dashboard.

### Demonstrated consequence

`[bug--adr-retrieval-blind-to-slug-headers]`: the ADR header format changed in protocol
v2.2.0, was updated where ADRs are written (`along_exec.py:535`) and validated
(`along_exec.py:630`), and was missed in the reader (`along_kb_search.py:100`). ADR search
returned zero results in every released version. A single shared entity module would have
made that impossible.

### Other duplicated concerns

- Sanitizer invocation wrappers: `along_commit.py:27-32`, `along_version_bump.py:398-401`.
- Ad-hoc `subprocess.run` calls with no shared conventions, which is why the encoding defect
  in `[bug--subprocess-encoding-breaks-on-non-utf8-locale]` appears at 25+ call sites.
- Path resolution: only `along_exec.py` has `resolve_tool_script`; the other engines
  hardcode `repo_root/scripts/...`, which is the root cause of
  `[bug--skill-commands-reference-missing-script-paths]`.
- Date handling, slug normalization, and markdown link parsing are each reimplemented.

## Impact

This is the structural reason most other issues in this epic exist and recur. Fixing them
one file at a time multiplies the work and guarantees future divergence.

## Requirements

- REQ-1: Create an installable package, for example `along/` with submodules:
  - `along/repo.py` - root discovery, path resolution, tool resolution;
  - `along/frontmatter.py` - the single YAML front-matter reader/writer;
  - `along/entities.py` - issue/session/decision/milestone models, enums, canonical keys,
    ADR header parsing;
  - `along/proc.py` - `run_capture()` with UTF-8 conventions and return-code checking;
  - `along/markdown.py` - link parsing, fenced-code tracking, anchor generation;
  - `along/typography.py` - the single forbidden-character table.
- REQ-2: Add `pyproject.toml` with a console entry point, coordinated with
  `[bug--skill-commands-reference-missing-script-paths]` REQ-2.
- REQ-3: Convert every script in `scripts/` and the dashboard to import from the package;
  delete all duplicate helper definitions.
- REQ-4: Keep the scripts working when invoked directly from `~/.along/bin/` (a directory
  copy, not a package install): either install the package as a dependency or vendor it
  alongside, and cover the scenario with a test.
- REQ-5: Add unit tests for each module. Current coverage is concentrated in end-to-end
  engine tests; the shared primitives need direct tests.
- REQ-6: Record an ADR for the package boundary, the dependency policy (stdlib versus
  pyyaml), and the compatibility story for direct-script invocation.
- REQ-7: Enforce with a test that no helper name is defined more than once across the
  codebase (for example an AST scan for duplicate top-level function names).

## Acceptance Criteria

- [ ] One definition each of `find_repo_root`, front-matter I/O, subprocess capture, ADR
      parsing, typography table.
- [ ] All engines import from the shared package.
- [ ] `pyproject.toml` present; package installable; direct-script invocation still works.
- [ ] Unit tests per module.
- [ ] Duplicate-definition guard test in place.
- [ ] ADR recorded.

## Resolution (2026-09-01)

- REQ-1: `scripts/alongkit/` created with `repo`, `frontmatter`, `entities`, `proc`,
  `textio`, `markdown`, `typography`, `gates`, `semver`, `version`, `bootstrap`, `cli`.
- REQ-2: `pyproject.toml` (hatchling) with `[project.scripts] along = "alongkit.cli:main"`,
  the `ruamel.yaml` dependency, the `dash` extra, and an engine manifest asserted complete
  by `test_engine_manifest_matches_scripts_dir`.
- REQ-3: all twelve engines and `dashboard/core/collector.py` converted; every duplicate
  helper definition deleted (`find_repo_root` x5, front-matter parsing x4, `parse_semver`
  x2, `safe_relpath` x2, `run_precommit_tests` x2, `sanitize_typography` x2, the typography
  table x2, the protocol version constant x4).
- REQ-4: both installers copy `alongkit/` next to the engines; covered by
  `TestFlatInstallInvocation` (an engine runs from a temporary flat copy against a
  consumer repository) and `TestInstallersCarryThePackage`.
- REQ-5: `tests/test_alongkit.py`, 68 unit tests across the modules. Suite grew 57 -> 125.
- REQ-6: `[ADR-2026-09-01--shared-engine-package]` and
  `[ADR-2026-09-01--frontmatter-on-ruamel-yaml]`.
- REQ-7: `TestNoDuplicateHelpers` - two AST scans, one for a name defined in two engines
  and one for an engine shadowing a package helper.

Fixed in passing, each a real defect found while converting: a missing `json` import that
made the npm test gate silently no-op, `along_feedback` reporting version 2.1.6 in every
bug report, the dashboard graph builder crashing on an unparseable entity file, and the
`httpx2` typo in the dashboard test fallback.
