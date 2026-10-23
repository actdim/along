# Living Plan: exit-plan-text-not-captured

## Revision 1 (2026-10-23T17:42:25Z, ExitPlanMode)

# Fix: ExitPlanMode approval records no plan text (`bug--exit-plan-text-not-captured`)

Execution Mode: Direct (one hook branch plus its regression tests)

## Context
Accepting a plan through Claude Code's `ExitPlanMode` records the approval but not the plan
text, so `.along/ISSUES/<key>/plan.md` stays the scaffold (traces of `feat--pre-approved-plans`
and `bug--wrap-misses-moved-issue-folder`: `plan approved (ExitPlanMode)`, no `plan recorded`).

`hooks/predicates.record_tool_activity` reads only `tool_input.plan`. Transcripts (31d67282,
d526bdff) show current Claude Code calls `ExitPlanMode` with `input: {}`; the plan is written
to `~/.claude/plans/<name>.md` and the tool result is
`{"plan": "<text>", "isAgent": false, "filePath": "<plan file>"}`. A normalized input may also
carry `{"plan", "planFilePath"}`. The Claude adapter keeps the whole hook payload in
`event.raw_payload`, so `tool_response` is available there.

## Change
1. `scripts/alongkit/hooks/predicates.py`: replace the inline lookup with a helper
   `_exit_plan_mode_text(event) -> Optional[str]` that returns the first non-blank of:
   `tool_args.plan`, `raw_payload.tool_input.plan`, `raw_payload.tool_response.plan`
   (when `tool_response` is a dict), then the text of the file named by
   `tool_input.planFilePath` / `tool_response.filePath` (read with
   `textio.read_text(strict=False)`, `OSError` ignored). Pass it to
   `session.record_accepted_plan` as today. Update the comment with the issue key.
2. `tests/test_session_records.py` (`TestExitPlanModeCapture`): let `exit_plan_mode` take
   `tool_input` / `tool_response` overrides and add:
   - real payload shape: `tool_input={}`, `tool_response={"plan": ..., "isAgent": False,
     "filePath": ...}` -> plan text in the issue plan, `plan recorded` in the trace;
   - path only: `tool_input={}`, `tool_response={"filePath": <tmp file>}` -> file text recorded;
   - existing tests (input `plan`, no plan still approves) stay green.

No change to `session.record_accepted_plan`: it already writes to the bound slug's plan
(`session.plan_path` -> issue plan) or holds it as `pending_plan`.

## Verification
- `python -m pytest tests/test_session_records.py -q`
- Full suite: `python .along/scripts/test.py -q`
- Commit via `along commit` (only my files), wrap with
  `python scripts/along_exec.py wrap exit-plan-text-not-captured --no-decisions`; check the
  committed issue folder holds this plan.

Note: hooks run the installed `along` (`~/.along/bin`), which predates this fix, so this
session's own approval capture still comes from the old code until `along update`.
