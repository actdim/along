# Plan: Fix Engine Wrap Atomicity, Gate Reference Integrity, and Multi-Subproject Session Friction

## Execution Mode
Direct

## Context and Scope
Remediate the critical engine atomicity bugs, false-positive gate denials, test-gate friction, and session issues identified during multi-subproject operations (Mempart session 2026-11-22, including items 12a and 12b).

Target Issue: `bug--engine-atomicity-and-gate-resilience`
Milestone: `v5.0.0-agent-run-protocol-and-observability`

## Step-by-Step Implementation Plan

### Step 1: Wrap Fail-Fast and Commit Atomicity (Items 1, 12a)
- In `scripts/alongkit/lifecycle.py`:
  - Enforce acceptance criteria validation BEFORE `tx.commit()`. If unchecked checkboxes (- [ ]) exist in the issue body, abort wrap with an error listing all unchecked items. Do not let `--force-reason` leave open checkboxes in `done/`.
  - In `_auto_commit_wrapped_work`: if auto-commit fails or is rejected by pre-commit gates, ensure clean diagnostic reporting with the exact failure reason and instructions. Unstage any staged files (`git restore --staged`) so the working tree is not left in an uncommittable half-done state.
  - Print an explicit final wrap line: `wrap: committed <sha>` or `wrap: failed to commit (<reason>); unstaged all files. Next: <command>`.
- In `scripts/along_wrap.py`:
  - Ensure CLI flags and exit codes reflect atomic completion or full rollback.

### Step 2: Entity Reference Integrity for Untracked Files (Item 2)
- In `scripts/alongkit/gitgates.py` (`check_entity_references`):
  - When an entity reference is missing from the index/tree snapshot, inspect the physical disk path at `<repo_root>/.along/ISSUES/<key>.md`.
  - If the file exists on disk, report: `Entity '<key>' exists on disk but is not staged/tracked in git. Stage it via 'git add' in this commit.`
  - Only suggest `along issue rename` or `along issue supersede` when the file does not exist on disk either.

### Step 3: Complete Stub Reporting in One Pass (Item 3)
- In `scripts/alongkit/entities/stubs.py` and `scripts/alongkit/gitgates.py`:
  - Ensure stub detection scans all candidate staged files and aggregates every violation before returning.
  - Eliminate early returns that report only a subset of stubs.

### Step 4: Subprojects Without Tests & Docs-Only Test Skipping (Items 7, 12b)
- In `scripts/alongkit/verify.py` and `scripts/alongkit/lifecycle.py`:
  - Distinguish between "0 tests executed due to failure" and "no tests discovered/configured in subproject". Treat as `tests: none (subproject has no tests)`.
  - Implement docs-only path filter: when all staged paths match documentation, markdown, or metadata globs (`.along/**`, `docs/**`, `*.md`, `AGENTS.md`, `CLAUDE.md`, `llms*.txt`), treat tests as skipped: `tests: skipped (docs-only change)`.
  - In `along_commit.py` and `lifecycle.py`, bypass running the test suite when the docs-only condition is met.

### Step 5: Lifecycle CLI Help Interception (Item 12b)
- In `scripts/along_exec.py`:
  - In `LIFECYCLE_ACTIONS` handling (`test`, `build`, `dev`, `debug`), check for `-h` / `--help` before dispatching to the underlying hook.
  - Print descriptive command help and options (`--full`, `--affected`, `--scope`) and exit 0 immediately without executing the hook script.

### Step 6: User Gate Approvals and Auto-Settlement (Items 6, 12a)
- In `scripts/alongkit/commands/gates.py` and `scripts/alongkit/session.py`:
  - Add `along gates approve <id>|--issue <slug>|--all` command for user-driven denial clearance.
  - Associate denials with `slug` in addition to session key.
  - Implement auto-settle logic: when a projection (e.g., `docs/INDEX.md`) is regenerated via its canonical tool (`along kb sync`), automatically mark related `projection_protection` denials as resolved (`superseded`).
  - Print the user approval command in wrap refusal messages.

### Step 7: Submodule CWD Resilience and Workspace Containment (Items 11, 12)
- In `scripts/alongkit/repo.py`: Ensure `find_repo_root` resolves the top repository root correctly even if cwd is inside a submodule.
- In `scripts/alongkit/gates.py`: Ensure `workspace-containment` allows paths declared in session extra working directories.

### Step 8: Automated Tests
- Add unit tests in `tests/test_wrap_atomicity.py` and `tests/test_gitgates.py`:
  - Test wrap aborts when unchecked checkboxes exist.
  - Test entity reference integrity reports untracked files as "stage in git" instead of "dangling reference".
  - Test stub detector reports all stubs simultaneously.
  - Test `along test --help` prints help and exits 0 without running tests.
  - Test pure docs commit skips test execution.
  - Test `along gates approve` resolves issue denials.

## Verification
```bash
python .along/scripts/test.py tests/test_alongkit.py
```
