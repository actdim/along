---
protocol: along
date: 2026-09-01
slug: release-gates-before-mutations-and-transactional-rollback
agent: claude-code
branch: main
commit: pending
summary: 'Closed the release engine bug: every gate now runs on the untouched tree and on every invocation, mutations are recorded by a new FileTransaction and restored byte for byte on failure, the installer call that rewrote machine-global agent config is deleted, milestone reconciliation moved to the front-matter writer with slug matching, and the release finally stages only its own paths, tags annotated, and writes a CHANGELOG.'
milestone: v3.0.0-global-quality-revision
issues_advanced: [protocol-quality-audit-remediation]
issues_completed: [release-engine-mutates-before-tests-and-reinstalls-globals]
decisions: [ADR-2026-09-01--release-gates-before-mutations]
risks_logged: []
spikes_conducted: []
---

# Session: Release Gates Before Mutations, and a Transactional Rollback

## Summary

Closed `[bug--release-engine-mutates-before-tests-and-reinstalls-globals]`, the second of
the four destructive engines in the audit backlog. `along_version_bump.py` wrote the new
version across every manifest, ran the sanitizer over the whole repository, flipped the
matching milestone to `completed`, and regenerated the dashboard - and only then ran the
test suite, and only when `--commit` was passed. A failing gate printed "Release aborted"
and exited 1 over a tree that was already half-released. It then finished by running
`install.ps1 -Target all`, which deletes and recreates `~/.claude/rules`, with the exit
code ignored so the success line printed either way.

The shape of the fix is two phases with a hard boundary: gates on the untouched tree, then
mutations that can be undone. Recorded as
`ADR-2026-09-01--release-gates-before-mutations`.

## Work Completed

- **`scripts/alongkit/transaction.py` (new)**: `FileTransaction` snapshots a file's exact
  bytes, or records its absence, before anything writes to it. `rollback()` restores every
  protected path and returns what it put back; `changed()` reports what actually differs,
  which is also what the release stages; `commit()` gives up the ability to roll back once
  the operation passes the point of no return. Bytes rather than decoded text, so a
  rollback can restore a file the sanitizer would refuse to touch. A mutation it cannot
  see - a project's own `bump_version.py` hook - is recorded with `mark_unrestorable()`
  and named in the abort report rather than assumed away.
- **`scripts/alongkit/gates.py`**: added `link_integrity_gate`, which runs
  `along_kb_sync.py --check --strict` (the engine's read-only mode) and returns False on a
  broken relative link. A repository without the Knowledge Base engine passes, so a
  consumer project is unaffected.
- **`scripts/along_version_bump.py`**: restructured.
  - `release_preflight()` runs the tests, the typography check in check mode, and the link
    gate before the first write, on every invocation. `-n` / `--no-verify` is the single
    documented way past, matching `along_commit.py`. `--fix-typography` now defers the
    repair into the transaction, so an abort restores it too.
  - Nothing calls `sys.exit` past argument parsing; failures raise `ReleaseAborted`, and
    `main` rolls back and prints each restored path. An unexpected exception rolls back and
    re-raises rather than being reported as a tidy release failure.
  - `sync_local_global_install` deleted outright rather than gated behind a flag.
  - `update_along_milestones` uses `frontmatter.update` and matches on the milestone's own
    `slug`, requiring the version as a whole hyphen-separated component, so `v1.4.30`
    survives a release of `1.4.3` and a milestone matched only by filename is left alone.
  - `update_changelog` prepends a `## v<version>` section listing the commit subjects since
    the previous tag; `create_release_commit` stages exactly `tx.changed()`, commits, and
    creates the annotated tag `v<version>`. A tag or push failure exits non-zero.
  - Every child process is now checked. The `along_dash.py --markdown` call is removed:
    that flag has never existed, so the step was dead code whose exit code nobody read.
  - The ten duplicated read-substitute-write blocks in `bump_along_dev_repo` became one
    `rewrite_version_in_file` call each, with a strict UTF-8 read.
- **`tests/test_release_engine.py` (new)**: 19 cases over throwaway fixtures. A test hook
  records the version it saw, which must be the pre-bump one; a failing hook leaves the
  tree byte-identical; a mid-release failure (a CHANGELOG that is not valid UTF-8) rolls
  back and names the files; the milestone body survives while its front-matter changes; the
  decoy and neighbour milestones are untouched; an unrelated dirty file and an untracked
  file stay out of the release commit; the tag is annotated (`cat-file -t` is `tag`) and the
  CHANGELOG lists what git recorded. The installer check is AST-based, excluding
  docstrings, so the engine can still document the defect it no longer has. `FileTransaction`
  is unit-tested for byte-exact restore of a CRLF file, removal of created files and their
  directories, first-snapshot-wins, and `commit()` closing the rollback.
- **Documentation**: `docs/topic--architecture.md` (the `transaction` module row and a new
  "Gates precede mutations, and mutations roll back" section),
  `docs/topic--setup-and-workflow.md` (a "Releasing" section with the step table and the
  flags), `docs/topic--skills-reference.md`, `skills/along-version-bump/SKILL.md` (order of
  operations, `--no-verify`), and the `AGENTS.md` project specifics.

## Code Review and Impact

- **Blast radius**: `alongkit.transaction` is new, so it has no existing callers.
  `gates.py` gained a function and changed no signature; `along_commit.py`, the other
  consumer of `gates`, is untouched. `along_version_bump.py` is not imported by any other
  engine (checked by search), so its internal restructuring is contained. The
  `code-review-graph` MCP server failed to connect again this session
  (`[debt--unpinned-mcp-and-ghost-wiki-query-tool]`), so the radius was traced by symbol
  search.
- **Behavioral changes users will notice**: a plain `along_version_bump.py patch` now runs
  the full gate and can fail where it previously could not; a repository with broken
  relative Markdown links cannot release until they are fixed or `--no-verify` is passed;
  and a version bump no longer reinstalls the machine's skills, which some workflows may
  have been relying on as a side effect. `/along-update` is the replacement, and the skill
  documentation says so.
- **ADR compliance**: respects `ADR-2026-09-01--shared-engine-package` (the rollback
  primitive is one module in the package, not a helper in the engine; both AST duplication
  guards pass), `ADR-2026-09-01--frontmatter-on-ruamel-yaml` (entity edits name keys and
  leave every other line byte-identical; a refusal is the correct outcome for input that
  cannot be parsed), and `ADR-2026-09-01--typography-rule-scope` (the release still
  verifies rather than rewrites by default).
- **Suite**: 166 -> 185 tests, all passing under `uv run python -m unittest discover tests
  -q`. `tests/test_zz_hermetic_suite.py` confirms the suite left the working tree clean,
  and `python scripts/sanitize_typography.py` reports 229 files scanned with no findings.

## Follow-Ups

- `[bug--migration-deletes-destination-without-backup]` and
  `[bug--installer-parity-and-destructive-rules-overwrite]` are the remaining destructive
  engines in step 2 of the epic; both can now build on `alongkit.transaction` instead of
  inventing their own rollback.
- `[debt--generated-dashboard-artifact-committed]` still owns the question of whether
  `.along/DASHBOARD.md` and `dashboard.html` belong in git. This change only removed the
  release path's dead attempt to regenerate them.
- `[bug--link-gates-skip-along-directory]` now also gates releases through
  `link_integrity_gate`, so whatever that issue changes about the walk changes what a
  release refuses.
- `[bug--commit-stages-all-and-dead-test-detection]` still has `along_commit.py` staging
  with `git add -A`; the release path no longer does, and `tx.changed()` is the pattern it
  can adopt.
