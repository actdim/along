# Plan: Fix OpenCode Node plugin contract test hermeticity on dirty working tree

## Execution Mode
Direct

## Context and Scope
In `tests/test_opencode_runtime.py`, `TestOpenCodeNodePluginContract.test_node_plugin_module_contract` passes `process.cwd()` to `mockCtx.location.directory` and `event.cwd`.
When `session.idle` or `session.stop` is invoked for dummy `sessionID: 'ses-1'`, `handleStop` evaluates the along hook against `process.cwd()`.
If the developer or agent has any uncommitted modified files in the repository working tree, the hook denies `ses-1`, causing `test_node_plugin_module_contract` to fail during pre-commit checks.

Target Issue: `bug--opencode-plugin-test-hermeticity`
Milestone: `v5.0.0-agent-run-protocol-and-observability`

## Step-by-Step Implementation Plan

### Step 1: Use Isolated Temp Directory in Node Contract Test
- In `tests/test_opencode_runtime.py`:
  - In `eval_script`:
    - Import `os` and `fs` from node standard library.
    - Create a clean temporary directory `testTmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'opencode-test-'))`.
    - Pass `testTmpDir` to `mockCtx.location.directory`, `v2Event.cwd`, and `handlers['shell.env']`.
    - In a `finally` block or after test completion, clean up `testTmpDir` (`fs.rmSync(testTmpDir, { recursive: true, force: true })`).

### Step 2: Defensive Handling in `opencode_plugin.js`
- Ensure `opencode_plugin.js` handles non-Along and temporary directories without throwing unhandled exceptions.

### Step 3: Verification
- Verify that `test_opencode_runtime.py` passes cleanly even when arbitrary dirty files exist in the working tree.
- Run `python .along/scripts/test.py tests/test_opencode_runtime.py`.
