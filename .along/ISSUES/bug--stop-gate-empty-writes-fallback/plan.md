# Living Plan: stop-gate-empty-writes-fallback

## Revision 1 (2026-11-15T13:05:57Z, ExitPlanMode)

# Plan: bug--stop-gate-empty-writes-fallback

## Execution Mode
Direct (3 files: one predicate, its tests, one doc paragraph).

## Context
Review of `bug--stop-gate-false-positives` (commit `b4982cc`, v4.9.0) found an inconsistency in
the Stop branch of `require-plan-approval` (`check_mutation_authorization`,
`scripts/alongkit/hooks/predicates.py:1510-1547`). It intersects the turn's working-tree changes
with `trace["turn_writes"]`, but when that set is empty it falls back to "all changes minus other
sessions' recorded writes". Reproduced: a file changed by something with no activity trace (user's
editor, a hookless runtime) is **denied** when the session wrote nothing, and **ignored** when the
session wrote one file. The fallback exists for runtimes that never deliver PostToolUse, but an
empty write set cannot tell that apart from "this session did not write".

Fix: decide by facts the hook already sees.
- Writes happen only through allowed write-tool or shell calls. If the session made none this
  turn, nothing in the tree is its doing.
- If the session made such calls and has ever received a PostToolUse event, its `turn_writes` is
  reliable, even when empty.
- Only "made calls, recorded nothing, never saw PostToolUse" keeps the whole-tree fallback.

## Changes

### 1. `scripts/alongkit/hooks/predicates.py` - `record_tool_activity`
- `USER_PROMPT_SUBMIT` branch (line ~667): next to `trace["turn_writes"] = []` add
  `trace["turn_mutations"] = 0`.
- Write-tool branch (line ~704, uses the same tuple as `WRITE_TOOLS`): before the early
  `return` for non-PostToolUse, on `PRE_TOOL_USE` increment `trace["turn_mutations"]`
  (`int(trace.get("turn_mutations") or 0) + 1`) and save. On `POST_TOOL_USE` set
  `trace["post_tool_seen"] = True` (saved by the existing `save_activity_trace` at the branch end).
- Shell branch (line ~737): on `PRE_TOOL_USE`, increment `turn_mutations` in the same save as
  `shell_pending`. On `POST_TOOL_USE`, set `post_tool_seen = True` and always save (today it
  saves only when `shell_pending` existed).
- `post_tool_seen` is per session and survives turns (not reset at the prompt).
- `record_tool_activity` runs only for events every gate allowed, so a denied call is not counted.

### 2. `predicates.py` - Stop branch of `check_mutation_authorization` (line ~1526)
Replace `if mine_keys: ... else: ...` with:

```python
mutations = trace.get("turn_mutations")
trust_writes = bool(mine_keys) or mutations == 0 or bool(trace.get("post_tool_seen"))
if trust_writes:
    foreign = [p for p in turn_changes if _norm_k(p) not in mine_keys]
    turn_changes = [p for p in turn_changes if _norm_k(p) in mine_keys]
else:
    # current fallback, unchanged: all changes minus other sessions' recorded turn_writes
```
- `mutations == 0` is False for a legacy trace without the key (`None`), so an old trace keeps the
  fallback (REQ-3); the existing "legacy trace" test (no `turn_writes`) is untouched anyway.
- Comment the three cases with `[bug--stop-gate-empty-writes-fallback]`.
- Keep `_unlogged_plan_approvals(turn_changes)` on the full change list (security check, as now).

### 3. Tests - `tests/test_gates_traceability.py`, new class `TestStopEmptyWritesFallback`
Same fixture pattern as `TestStopCountsSessionWrites` (temp git repo, `record_tool_activity` +
`check_mutation_authorization(..., options={"enforce_unbound": True})`, `conversation_id="sess-1"`):
- no tool calls this turn + untraced `src/foreign.py` -> `None` (REQ-1).
- PreToolUse + PostToolUse `run_command` that writes nothing, then untraced foreign file -> `None`
  (REQ-2: PostToolUse seen, empty writes trusted).
- PreToolUse `run_command` only, trace edited to drop `shell_pending` and `post_tool_seen`, then
  untraced file -> denied (fallback kept for runtimes without PostToolUse).
- The repro pair: one own write + foreign, and no own write + foreign, now behave the same for the
  foreign file (not reported).
Existing `TestStopCountsSessionWrites` must pass unchanged.

### 4. Docs - `docs/topic--runtime-hooks-and-gates.md`
In the 2.6 `Stop` bullet, after the `turn_writes` sentence, add one sentence: a session with no
allowed write or shell call in the turn has nothing attributed; the whole-tree fallback (minus
other sessions' recorded writes) applies only when it made such calls, recorded no writes and has
never received PostToolUse. Bump the article's `updated:` to 2026-11-15.

## Out of scope
The other review notes (PreToolUse projection whitelist, unrelated files in `b4982cc`, ADR context
wording, missing "D1: A" note) are not touched here.

## Verification
1. `python .along/scripts/test.py -q tests/test_gates_traceability.py tests/test_anti_silent_fallback.py tests/test_inquiry_gate.py tests/test_hook_activation.py`
2. Re-run the scratch repro (`repro_stop.py` in the session scratchpad): both cases must stop
   reporting `src/foreign.py`.
3. Full suite: `python .along/scripts/test.py -q`.
4. `along sanitize`, then commit only the three files plus the issue via `/along-commit`
   (the working tree also holds unrelated changes from other work: do not stage them), then
   `along wrap stop-gate-empty-writes-fallback --summary "..." --no-decisions`.

## Revision 2 (2026-11-15, user's choice in chat: "Count untraced changes")

Revision 1 broke 4 tests in `tests/test_shell_classification.py` (`TestShellChangesCaughtAtStop`),
which require that an unexplained change during a turn is held. The hook cannot tell the user's
editor from a write through a tool it does not see (an MCP tool), so excusing untraced changes
lets a plan bypass through. The user chose the strict, uniform rule instead:

- Stop branch of `check_mutation_authorization`: a changed path is excused only when another
  session recorded it in its `turn_writes` and this session did not write it. Everything else
  the turn changed counts, whether or not this session recorded any writes.
- The `turn_mutations` / `post_tool_seen` counters of Revision 1 are dropped (not needed).
- Tests: `TestStopUntracedChanges` replaces `TestStopEmptyWritesFallback` (untraced change counts
  with and without own writes; another session's recorded write is excused; a path both sessions
  wrote counts). Existing `test_shell_classification` and `TestStopCountsSessionWrites` unchanged.
- Issue requirements and the doc sentence are rewritten to this rule. Remaining false positive:
  an edit in the user's editor during a turn is held; it can be acked (`along gates ack`).
