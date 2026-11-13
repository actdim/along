---
protocol: along
protocol_version: "4.8.1"
slug: trivial-fix-lifecycle
type: feat
status: open
priority: medium
created: 2026-11-13
updated: 2026-11-13
agent: claude-code
tags: [issues, wrap, commit, ux]
blocked_by: []
related: [debt--stale-protocol-path-comment, bug--stop-gate-false-positives]
---

# Lighter lifecycle for trivial fixes: filled issue create, verifiable criteria, consistent commit type

## Problem

A one-line comment fix (`debt--stale-protocol-path-comment`, 2026-11-13) took: `along issue create` -> `along start` refused on scaffold placeholders -> hand-edit the issue -> `along start` -> plan mode -> `ExitPlanMode` -> edit -> `along commit` -> `along wrap` refused on unchecked criteria -> hand-tick criteria -> `along wrap`. It produced two commits with different types: `docs(budget): ...` from `along commit` and `refactor: ...` from `wrap`.

Current behavior in code:
- `scripts/alongkit/commands/issue.py` `create` always writes the scaffold body (placeholder problem text, a template REQ-1 line and default acceptance items), which `along start` then rejects; there are no flags to supply the body. Quoting that scaffold text verbatim in any issue also trips the stub detector.
- `scripts/alongkit/entities/stubs.py` rejects closeout while any `- [ ]` remains, including "tests pass" criteria the test ledger already proves.
- The issue-type -> commit-type map (`debt` -> `refactor`, etc.) is duplicated in `scripts/alongkit/closeout.py` (`_COMMIT_TYPES`), `scripts/alongkit/lifecycle.py` and `scripts/along_commit.py`; `wrap` ignores the type the issue's own commits already used.

## Requirements
- REQ-1: `along issue create` MUST accept `--problem "..."`, repeatable `--req "..."` and repeatable `--ac "..."` (or `--body-file <path>`), and MUST write no placeholder text for the sections they fill.
- REQ-2: `along wrap` MUST treat an acceptance criterion that names the test suite as satisfied when the test ledger records a pass on the current tree, and tick it in the issue file it moves to `done/`.
- REQ-3: Unticked criteria that are not machine-verifiable MUST still block `wrap`, with the existing message.
- REQ-4: The issue-type -> commit-type map MUST live in one place (`alongkit`), reused by `along commit`, `wrap` and `lifecycle`.
- REQ-5: `wrap`'s closeout commit MUST use `chore(along):` (closeout touches only Along state and projections), not the issue-type prefix.

## Acceptance Criteria
- [ ] `along issue create bug x --title t --problem p --req r --ac a` followed by `along start x` succeeds without hand edits.
- [ ] `wrap` on an issue whose only unticked criterion is "tests pass", with a recorded pass on the tree, succeeds and the moved file shows `- [x]`.
- [ ] `wrap` still refuses an unticked non-test criterion.
- [ ] Only one commit-type map exists in `scripts/`; `tests/test_alongkit.py` (helpers live in alongkit) passes.
- [ ] Closeout commits are prefixed `chore(along):`.
- [ ] `python .along/scripts/test.py` passes.

## Plan

Execution Mode: Role-Based (issue CLI, closeout validation, commit engine; more than 3 files -> `along-team`).

1. **Filled create (REQ-1).** In `scripts/alongkit/commands/issue.py`, add `--problem`, `--req` (append), `--ac` (append), `--body-file`; build the body from them and fall back to the current scaffold only for sections not supplied. Keep `--draft` behavior. Update `along issue --help` text and `skills/along-issue-sync/SKILL.md` usage.
2. **Verifiable criteria (REQ-2, REQ-3).** In `scripts/alongkit/entities/stubs.py`, classify a criterion as test-verifiable by a small, documented pattern set (mentions `test.py`, "tests pass", "test suite"). In the wrap path (`scripts/alongkit/closeout.py` / `lifecycle.py`), before validation, consult the test ledger already used by `along commit` ("Tests passed on this tree at ...") and tick matching criteria in the file being moved. Other unticked items keep failing with the current reasons.
3. **Single type map (REQ-4).** Add `COMMIT_TYPE_BY_ISSUE_TYPE` to an existing alongkit module (e.g. `alongkit/entities/vocabulary.py`), replace the three local dicts with it.
4. **Closeout prefix (REQ-5).** In `closeout.py`, build the wrap commit subject as `chore(along): <summary> (refs #<slug>)`. Check `tests/test_parallel_closeout.py` and `tests/test_wrap_engine_writes.py` for subject assertions and update them under this issue (the issue is about this behavior).
5. **Tests.** New cases for create flags, wrap auto-tick (pass and refuse), single map import; hermetic temp repos.
6. **Docs.** Update `docs/topic--*` pages covering issue creation and wrap (locate via `/along-kb-search issue create`, `/along-kb-search wrap`).

Verification: targeted modules, full suite, then a scratch-repo walk-through of the trivial-fix flow counting commands and commits.
