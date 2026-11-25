# Plan: bug--changelog-deduplicator-priority-and-rebuild

Execution Mode: Direct (`scripts/along_version_bump.py`, `CHANGELOG.md`, `tests/test_version_bump.py`)

## Context
`deduplicate_log_entries()` in `scripts/along_version_bump.py` currently prefers any scoped `type(scope):` entry over an unscoped `type:` entry when two commits share the same `(refs #<slug>)`, without ranking commit type priority first. As a result, `docs(adr):` or `chore(sync):` commits overwrite primary `feat:` or `fix:` commits. Additionally, `CHANGELOG.md` still contains duplicate `(refs #<slug>)` entries across `v4.9.1`, `v4.9.0`, `v4.8.1`, `v4.8.0`, `v4.7.0`, `v4.6.1`, `v4.6.0`, `v4.5.x`, and earlier sections.

## Planned Modifications
1. `scripts/along_version_bump.py`:
   - Update `deduplicate_log_entries()` to preserve double-prefix normalization (`fix: fix(scope): ...` -> `fix(scope): ...`).
   - Extract a helper `_entry_priority(line)` returning `(tier, has_scope, length)`:
     - Tier 3: `feat`, `fix`, `perf`, `refactor`, `debt`
     - Tier 2: `docs`
     - Tier 1: `test`, `chore`, `style`, `ci`, `build`
     - Tier 0: other or non-conventional prefixes
     - Within the same tier: scoped `type(scope):` > unscoped `type:`
     - Within the same tier and scope presence: longer subject string.
   - Support multi-ref formats cleanly (`(refs #slug)`, `(refs #slug1 #slug2)`, `(refs #slug1, #slug2)`).
2. `CHANGELOG.md`:
   - Regenerate all tagged release sections from `v4.4.5` through `v4.9.2` from `git log <prev_tag>..<tag>` passed through `deduplicate_log_entries()`, keeping exact tag dates (`## vX.Y.Z - YYYY-MM-DD`).
   - Deduplicate older historical sections (`<= v4.4.4`) via `deduplicate_log_entries()`.
   - Verify pure ASCII (`along sanitize`) and zero duplicate primary `(refs #<slug>)` entries in any section.
3. `tests/test_version_bump.py`:
   - Preserve `TestDeduplicateLogEntries.test_deduplicates_by_issue_reference_and_prefers_scope`.
   - Add tests verifying commit type tier priority (`feat:`/`fix:` beat `docs(adr):` and `chore(scope):`; `docs:` beats `chore(scope):`; same-tier scope preference and length tie-breaker; double-prefix normalization across types).
   - Add a test verifying `CHANGELOG.md` sections (`v4.6.0` through current) have zero duplicate `(refs #<slug>)` entries.

## Verification
- Run `tests/test_version_bump.py -q` and full suite via `.along/scripts/test.py -q`.
- Run `along sanitize`, `along hook verify --strict`, and `along kb-sync --check --strict`.
