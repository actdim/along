---
protocol: along
protocol_version: "3.6.0"
slug: cli-and-documentation-traceability-reconciliation
type: docs
status: in-progress
priority: medium
created: 2026-09-16
updated: 2026-09-19
agent: antigravity
tags: [documentation, cli, mkdocs, traceability, versioning, skills]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: []
related: []
---

# CLI Hook Interface Reconciliation, Navigation Completeness, and Version Traceability

## Problem
Several documentation, CLI specification, and release metadata files have drifted out of synchronization:
1. Documented but unimplemented CLI command:
   - `docs/topic--cli-reference.md:413` specifies `along hook eval <event> [--runtime ...]`, but `scripts/along_hook.py` only implements `install`, `verify`, and `run` subcommands. Running `eval` fails with an argparse unrecognized argument error.
2. CLI help gaps:
   - `LIFECYCLE_ACTIONS["debug"]` in `scripts/along_exec.py:82` is not documented in the CLI help text.
3. Missing documentation pages in MkDocs navigation:
   - `mkdocs.yml:48-60` omits three existing topic articles:
     - `docs/topic--cli-reference.md`
     - `docs/topic--declarative-gates-and-traceability.md`
     - `docs/topic--runtime-hooks-and-gates.md`
4. Malformed documentation header:
   - `docs/topic--cli-reference.md:1-17` contains duplicate YAML frontmatter delimiters, causing parsing anomalies.
5. Out-of-sync skill counter across documentation:
   - Active skills count is 19 (in `skills/`), but `README.md:103` states 18, `llms.txt:27` states 17, and `scripts/alongkit/cli.py:13` references 18.
6. Version and hash drift in documentation:
   - Stale protocol version mentions: `docs/topic--setup-and-workflow.md:168` (v2.6.0), `docs/topic--cli-reference.md:3` (3.1.0), `dashboard/__init__.py:3` (2.1.3).
   - Stale SHA-256 hashes in `docs/topic--skills-reference.md:9-16`.
7. Release history gap:
   - `CHANGELOG.md:14` documents release `v3.4.0`, but no corresponding Git tag `v3.4.0` exists in repository history (jump from v3.3.0 to v3.5.0).
8. Orphaned assets:
   - `site-extra/` directory is not referenced by `mkdocs.yml` or the build pipeline.

## Requirements
- Implement the `along hook eval` subcommand in `scripts/along_hook.py` to evaluate incoming event JSON payloads against configured gates, matching documentation.
- Document the `debug` action in CLI help.
- Update `mkdocs.yml` nav to include all 13 topic documents.
- Clean up duplicate frontmatter in `docs/topic--cli-reference.md`.
- Synchronize skill counters across `README.md`, `llms.txt`, `llms-full.txt`, and `alongkit/cli.py` to 19.
- Update stale version strings in documentation and regenerate skill SHA-256 hashes.
- Clarify or reconcile `v3.4.0` changelog entry against release history.
- Clean up or link `site-extra/` assets in `mkdocs.yml`.

## Acceptance Criteria
- [ ] `along hook eval` executes and evaluates event payloads passed via stdin or args.
- [ ] All 13 topic docs are discoverable in `mkdocs.yml` navigation.
- [ ] `docs/topic--cli-reference.md` has a single valid YAML frontmatter block.
- [ ] Skill count consistently states 19 across all docs and CLI docstrings.
- [ ] `python scripts/along_kb_sync.py --check` passes without broken links.
