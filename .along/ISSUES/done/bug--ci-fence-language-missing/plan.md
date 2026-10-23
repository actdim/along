# Living Plan: ci-fence-language-missing

## Revision 1 (2026-10-23T19:18:08Z, ExitPlanMode)

# Fix: CI gate fails on a bare code fence (`bug--ci-fence-language-missing`)

Execution Mode: Direct (one line in one doc)

## Context
CI run 39935722047 fails in `along gates check --ci --no-links`:
`[gate: code-fence-language] docs/topic--autonomous-environment.md:37: code fence without a
language`. The bare fence wraps the plain-text isolation diagram added in ab51db5. The same
check reproduces locally.

## Change
- `docs/topic--autonomous-environment.md:37`: change the opening fence to `text`.
  No other content changes.

## Verification
- `python scripts/along_exec.py gates check --ci --no-links` reports no violations.
- `python .along/scripts/test.py -q` green (run by `along commit`).
- Commit via `along commit` (this doc + issue files only), wrap with
  `python scripts/along_exec.py wrap ci-fence-language-missing --no-decisions`. No push.
