# Plan: warn when a raw test runner starts, not at Stop

## Execution Mode
Direct

Target executor: a fast model.

## Scope decisions vs the ticket
- REQ-1: implemented.
- REQ-2 (count a raw run when `test.py` delegates to the package script): REJECTED.
  Record in the ticket: "The lifecycle hook can add setup the raw script lacks (this
  repo's `test.py` adds the project env, the syntax gate and `ALONG_TEST_RUNNER`).
  Detecting 'delegates to' needs parsing arbitrary hook code; a false positive lets
  untested edits through. The early notice (REQ-1) removes the wasted second run."
  This closes the second acceptance criterion.

## Facts verified in code
- `scripts/alongkit/hooks/predicates.py`, `record_tool_activity` (around line 566):
  on PreToolUse of a shell tool, a command matching `TEST_COMMAND_PATTERNS` while
  `has_lifecycle_test_hook(repo_root)` is true sets `trace["last_raw_test_time"]`. That
  is the exact spot where the notice belongs.
- `scripts/alongkit/hooks/engine.py`: `record_tool_activity(event, effective_root)` is
  called right before `return GateResult(decision=GateDecision.ALLOW, exit_code=0)`.
- There is no non-blocking notice channel yet. `GateResult` has `decision`, `reason`,
  `gate_name`, `exit_code` (`hooks/models.py`).
- `hooks/adapters/claude.py` `format_response` returns `(0, "")` for allow.

## Step 1: `record_tool_activity` returns an optional notice
Change it to return `Optional[str]`. In the raw-runner branch return:
```python
return ("[Along] This raw test run will not satisfy test_before_stop: this repository "
        "has a lifecycle test hook. Run 'python .along/scripts/test.py' (or /along-test) instead.")
```
All other paths return `None`. Use the lifecycle command name the Stop hint already
uses; if `has_lifecycle_test_hook` can tell which hook file exists, name that file.

## Step 2: carry it to the adapter
- `hooks/models.py`: add `notice: Optional[str] = None` to `GateResult`.
- `engine.py`: `notice = record_tool_activity(...)`, then
  `return GateResult(decision=GateDecision.ALLOW, exit_code=0, notice=notice)`.
- `adapters/claude.py` `format_response`: for an allowed PreToolUse with a notice return
  ```python
  0, json.dumps({"systemMessage": result.notice,
                 "hookSpecificOutput": {"hookEventName": "PreToolUse",
                                        "additionalContext": result.notice}})
  ```
  Do NOT set `permissionDecision` (that would override the user's permission flow).
- Other adapters: if they have an allow path that writes text, write the notice to
  stderr with exit 0; otherwise leave them unchanged (fail open).

## Step 3: tests
In `tests/test_hook_activation.py` (it already covers `last_raw_test_time`):
1. Repo with `.along/scripts/test.py`; PreToolUse Bash `pnpm run test` -> allowed, exit 0,
   output JSON has `systemMessage` with "test_before_stop".
2. Repo without a lifecycle hook -> no notice (and the run counts, as today).
3. `python .along/scripts/test.py` -> no notice.

## Verification
```bash
python .along/scripts/test.py tests/test_hook_activation.py
```
```bash
python .along/scripts/test.py -q
```
