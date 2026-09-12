---
protocol: along
slug: shared-engine-package
title: "Shared Implementation Package for the Engines (scripts/alongkit/)"
date: 2026-09-01
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-09-01--shared-engine-package - Shared Implementation Package for the Engines (scripts/alongkit/)

- Date: 2026-09-01
- Status: accepted
- Context: The twelve engines in `scripts/` (about 250 KB) had no shared module. `find_repo_root` existed in five copies that disagreed on what constitutes a repository root, front-matter parsing in four, `parse_semver` in two, and the pre-commit test and sanitizer gates in two each. `subprocess.run` was called at 25+ sites with no shared convention, which is why a single encoding defect (`[bug--subprocess-encoding-breaks-on-non-utf8-locale]`) was present in every engine and in the test suite at once. The demonstrated cost is `[bug--adr-retrieval-blind-to-slug-headers]`: the ADR header format changed in v2.2.0, was updated in the writer and the validator, and was missed in the reader, so ADR search returned zero results in every released version. Fixing such defects one file at a time multiplies the work and guarantees future divergence.
- Decision:
  1. **Package location**: `scripts/alongkit/`, a subpackage next to the engines rather than a top-level directory. Python places the running script's own directory on `sys.path`, and both installers copy `alongkit/` next to the engines, so `from alongkit import ...` resolves in a source checkout, in a flat `~/.along/bin/` file copy, and in an installed wheel, with no `sys.path` manipulation beyond one line per engine and no mandatory install step.
  2. **Module boundary**: one module per shared concern - `repo` (roots, state directory, engine resolution, directory walking), `frontmatter`, `entities` (vocabulary, canonical keys, ADR records), `proc`, `textio`, `markdown`, `typography`, `gates`, `semver`, `version`, `bootstrap`, `cli`. Inside the package a short name may repeat across modules (`frontmatter.parse`, `semver.parse`); the module qualifies it.
  3. **Single-definition rule, enforced**: no name may be defined at module level in two engines, and no engine may redefine a name the package owns. Two AST tests in `tests/test_alongkit.py` fail with the offending file and line otherwise. An engine that needs a shared helper aliases it (`parse_frontmatter = frontmatter.parse_tolerant`).
  4. **Packaging**: `pyproject.toml` (hatchling) declares the package, the `ruamel.yaml` runtime dependency, the `dash` extra for the dashboard stack, and the `along` console entry point, which delegates to the existing `along_exec.py` router rather than duplicating its dispatch table. Engine files are force-included one by one, asserted complete by a test, so the wheel cannot silently ship without them.
  5. **Compatibility**: the documented `python scripts/<engine>.py` invocation keeps working and is not deprecated here; rewriting the eighteen `SKILL.md` files onto the console entry point is tracked as `[bug--skill-commands-reference-missing-script-paths]`.
- Consequences: One place to fix each shared defect, and a test that fails when a copy reappears. The protocol version constant, the forbidden-character table, the ADR header format, and the subprocess conventions each have exactly one definition. Cost: engines carry a one-line `sys.path` insert, and the toolchain is no longer pure standard library (see the front-matter ADR below). Net effect on this change alone: 12 engines converted, about 240 duplicated lines removed, 4 latent defects fixed in passing (a missing `json` import that silenced the npm test gate, a stale version string reported in every bug report, an unparseable-file crash in the dashboard graph builder, and the `httpx2` typo in the dashboard test fallback).
