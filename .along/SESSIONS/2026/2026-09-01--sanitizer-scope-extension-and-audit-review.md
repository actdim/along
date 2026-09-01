---
protocol: along
date: 2026-09-01
slug: sanitizer-scope-extension-and-audit-review
agent: antigravity
branch: main
commit: b5da793
summary: "Extended migration Step 5 typography sanitizer scope to docs/ and AGENTS.md/README.md; reviewed post-audit fixes"
milestone: v3.0.0-global-quality-revision
issues_advanced: [protocol-quality-audit-remediation]
issues_completed: [extend-sanitizer-scope-to-docs-and-root]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Sanitizer scope extension and audit review

## Summary

Reviewed the post-audit quality fixes (commits e9cca29..b5da793) and implemented
one additional mitigation: extending the typography sanitizer scope in the migration
engine to cover docs/ and the root agent context files.

## Work Completed

- **Analysis**: Reviewed commit e9cca29 (the quality audit commit that created 28
  issues and fixed 2 P0/P1 defects) and the 9 subsequent commits that closed
  additional bugs.
- **`scripts/migrate_protocol.py`**: `sanitize_markdown_typography()` now accepts an
  optional `extra_targets` parameter (list of file or directory paths). Individual
  files are processed via `sanitizer.inspect_file()` directly; directories via
  `sanitizer.run()`. Step 5 in `run_migrations()` passes `docs/`, `AGENTS.md`, and
  `README.md` as extra targets. CLAUDE.md/GEMINI.md excluded by design.
- **`tests/test_migration.py`**: Added `TestTypographySanitizerScope` (3 tests):
  em-dash in docs/ is repaired, em-dash in AGENTS.md is repaired, dry-run writes
  nothing. Tests: 27 -> 30.

## Code Review and Impact

- Blast radius: only `migrate_protocol.py` and `test_migration.py` changed.
  `sanitize_markdown_typography()` is called from one place (Step 5). The new
  parameter is optional with a default of `()`, so all existing callers are
  unaffected.
- Dry-run correctness verified: the function probes in DRY_RUN mode first, writes
  only when `mig.dry_run is False`. Confirmed by `test_dry_run_does_not_write_typography_repairs`.
- All 27 existing migration tests pass, plus 3 new ones.