# Plan: docs--changelog-deduplication

Execution Mode: Direct (CHANGELOG.md, scripts/along_version_bump.py, tests/test_version_bump.py)

## Context
User requested: "Очистить дубликаты записей - сделай".
In `CHANGELOG.md`, releases v4.9.1, v4.9.0, and v4.8.1 contain redundant duplicate lines where both root and scoped commits for the same issue were appended.
In `scripts/along_version_bump.py`, `release_log_entries` currently performs no deduplication of log lines sharing identical `(refs #slug)`.

## Planned Modifications
1. `CHANGELOG.md`:
   - Clean duplicate entries in v4.9.1, v4.9.0, and v4.8.1.
   - Fix repeated prefix lines (e.g. `fix: fix(opencode):`).
2. `scripts/along_version_bump.py`:
   - Enhance `release_log_entries` to deduplicate lines by issue slug `(refs #<slug>)`, preserving the most descriptive subject (preferring scoped `type(scope):` over generic `type:`).
3. `tests/test_version_bump.py`:
   - Add unit tests for `release_log_entries` deduplication behavior.
4. Verification:
   - Run `python .along/scripts/test.py` to ensure all tests pass.
