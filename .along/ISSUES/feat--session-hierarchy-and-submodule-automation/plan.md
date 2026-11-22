# Plan: Umbrella Session Hierarchy and Automated Submodule Protocol Updates

## Execution Mode
Direct

## Context and Scope
Second phase of the Mempart feedback implementation: support cross-subproject workflows and reduce submodule maintenance friction.

Target Issue: `feat--session-hierarchy-and-submodule-automation`
Milestone: `v5.0.0-agent-run-protocol-and-observability`
Related Issue: `bug--engine-atomicity-and-gate-resilience`

## Step-by-Step Implementation Plan

### Step 1: Umbrella Session Hierarchy (Item 5)
- In `scripts/alongkit/session.py` and `scripts/alongkit/gates.py`:
  - When binding a session to an issue (`along start <slug>`), read the issue's `children:` field.
  - If the issue is an umbrella issue declaring child issues across subprojects, register the child slugs and subproject roots into the active session context.
  - In `check_subproject_boundary` and related gates, allow edits to files belonging to declared child issues without requiring manual rebinding.

### Step 2: Intelligent Dirty Tree Detection for `along start` (Item 5)
- In `scripts/alongkit/commands/lifecycle.py`:
  - Before failing `along start` on dirty working tree, inspect dirty files against the issue's declared attribution or umbrella tree.
  - If all modified files belong to the issue or its child issues, proceed without requiring `--allow-dirty`.

### Step 3: Submodule Protocol Auto-Commit (Item 8)
- In `scripts/along_update.py` and `scripts/alongkit/commands/`:
  - Add `--commit` flag to `along update`.
  - When `--commit` is supplied, iterate through each dirty submodule where Along protocol files (`AGENTS.md`, `PROTOCOL.md`, `.protocol-version`, `llms-full.txt`) were updated.
  - Commit protocol files in each submodule with commit message `chore(along): protocol v<version>`.
  - Mark this commit type as exempt from `commit-issue-binding` in `gitgates.py`.

### Step 4: Merge Driver Output Transparency (Item 9)
- In `scripts/along_update.py`:
  - Detect changes to `.gitattributes` merge drivers (e.g., transitions from `along-projection` to `-merge`).
  - Print explicit summary notices explaining why the merge driver changed.

### Step 5: Automated Tests
- Unit tests in `tests/test_session_hierarchy.py` and `tests/test_update_submodules.py`:
  - Verify umbrella issue session binding grants access to child subprojects.
  - Verify `along start` permits dirty trees belonging to the target issue.
  - Verify `along update --commit` commits protocol files across submodules.

## Verification
```bash
python .along/scripts/test.py tests/test_alongkit.py
```
