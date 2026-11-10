# Plan: Cross-issue denial resolution and ack in rebound sessions

## Execution Mode
Direct

Target executor: a fast model. Follow the steps in order. Do not add helpers, flags or
files that are not listed here.

## Review notes (why this plan differs from the first draft)
- The first draft added `find_all_blackboards` / `find_session_denials` /
  `find_denial_by_id`, which scan every `.along/.session/*/events.jsonl` of every context.
  The Stop gate would then read every ledger of a 12-root monorepo on every turn. Not
  needed: the per-session activity trace (`trace["open_denials"]`, written in
  `_record_denial_event`) already lists this session's open denials. It only lacks the
  originating `(ctx, slug)`. Storing those two fields makes the trace the index.
- `--issue` alias for `--slug`: dropped (not in the ticket's requirements).
- The tool-compatibility check on retry is dropped. Today a retry matches by target
  digest only; that is what the ticket asks for ("same tool, same target path" is
  already implied by the digest of the audit target). Keep current matching.

## Facts verified in code
- `scripts/alongkit/hooks/predicates.py`
  - `_record_denial_event` (around line 386): writes the `deny` ledger event via
    `session.record_event` (bound issue), then appends
    `{"id", "gate", "digest", "ts", ...}` to `trace["open_denials"]`. Procedural denials
    are NOT added to the trace (they settle on `approve`).
  - `_resolve_retried_denials` (around line 432): writes `resolve` via
    `session.record_event(repo_root, key, ...)`, i.e. into the CURRENTLY bound issue.
    Bug: after a rebind the resolve lands in the wrong ledger.
  - `check_unresolved_denials` (around line 1543): reads only
    `session.denial_status(ctx, slug)` of the bound issue.
- `scripts/alongkit/session.py`
  - `append_event(ctx, slug, key, kind, path, ok, extra)` writes into any ledger.
  - `denial_status(ctx, slug)`: `resolve` events do not keep `note`.
- `scripts/alongkit/commands/gates.py` `_handle_denials`: works on one `(ctx, slug)`.
- Bindings live under `session.binding_root(repo_root)`; the activity trace lives under
  `repo.diagnostics_dir(repo_root)` (see `get_activity_trace_path`).

## Steps

### Step 1: store provenance in trace entries (`predicates.py`, `_record_denial_event`)
Get `(ctx, slug)` once at the top: `ctx, slug = session.bound_blackboard(repo_root, key)`
(the function already calls it; reuse the result instead of calling twice). Add to
`denial_entry`:
```python
denial_entry = {"id": did, "gate": gate, "digest": digest, "ts": now,
                "ctx": ctx, "slug": slug}
```
`ctx` is an absolute path; that is fine (the trace is machine-local, under diagnostics).

### Step 2: resolve in the originating ledger (`_resolve_retried_denials`)
Replace the `session.record_event(...)` call with:
```python
d_ctx, d_slug = denial.get("ctx"), denial.get("slug")
if not d_ctx or not d_slug:  # entries written before this fix
    d_ctx, d_slug = session.bound_blackboard(repo_root, key)
if d_ctx and d_slug:
    _cur_ctx, cur_slug = session.bound_blackboard(repo_root, key)
    note = f"redone successfully by {event.tool_name}"
    if cur_slug and cur_slug != d_slug:
        note += f" under '{cur_slug}'"
    session.append_event(d_ctx, d_slug, key, "resolve",
                         extra={"id": denial.get("id"), "via": "retry", "note": note})
```
Call `bound_blackboard` once before the loop, not per denial.

### Step 3: keep the resolve note (`session.py`, `denial_status`)
In the `resolve` branch:
```python
denials[did].update(state=DENIAL_RESOLVED, via=event.get("via") or "retry",
                    note=event.get("note"))
```

### Step 4: one helper for "this session's denials" (`predicates.py`)
Add next to `_resolve_retried_denials` (hooks and the CLI both import predicates):
```python
def session_denials(repo_root: str, key: Optional[str]) -> List[Dict[str, Any]]:
    """denial_status items of every issue this session has open denials in (from the
    activity trace), plus the bound issue; each item carries `ctx` and `slug`."""
```
Logic:
1. `boards` = ordered set of `(ctx, slug)` from `load_activity_trace(repo_root, key)
   ["open_denials"]` entries that have both fields, plus `session.bound_blackboard(...)`
   when it is not `(None, None)`.
2. For each board: `for d in session.denial_status(ctx, slug): d["ctx"], d["slug"] = ctx, slug`.
3. Return the concatenation. No dedup needed (ids are unique per ledger).

### Step 5: Stop gate (`check_unresolved_denials`)
Replace the `ctx, slug = ...; held = [... denial_status(ctx, slug) ...]` block with:
```python
held = [d for d in session_denials(repo_root, key)
        if d["state"] == session.DENIAL_OPEN and (turn_start is None or str(d["ts"]) >= turn_start)]
```
Keep the early return when the session is unbound. Message: unchanged, but
`format_denials` output should name the issue when more than one slug is involved:
append ` (issue: <slug>)` per item only when `len({d["slug"] for d in held}) > 1`.

### Step 6: `along gates ack` (`commands/gates.py`, `_handle_denials`)
Only the `ack` path changes; `denials` (listing) stays as is.
- When `--slug` is given: today's behavior (one board).
- When `--slug` is NOT given: `items = predicates.session_denials(repo_root, key)` with
  `key = session.current_session_key()`. If the session is unbound AND the trace is
  empty, keep today's error (exit 2).
- `--all`: every item with state open.
- `<id>...`: look up ids in `items`; unknown ids keep today's error.
- Write each ack into the item's own ledger:
  `session.append_event(d["ctx"], d["slug"], key, "ack", extra={"id": d["id"], "note": note})`.
- Output: group by slug:
  `-> Acknowledged N gate denial(s) of '<slug>': <format_denials(...)>` one line per slug.
- Import: `from ..hooks import predicates` inside the function (avoid import cycles).

Root note (verified): the CLI's `repo_root` comes from `repo.find_repo_root()` (the nearest
`.along/`, i.e. a subproject when run from there), while the hooks write the trace under
the workspace root (`repo.diagnostics_dir(root)` -> `<root>/.along/diagnostics/activity/<key>.json`).
So in `session_denials` read the trace entries from BOTH `repo_root` and
`session.binding_root(repo_root)` (skip the second when both resolve to the same path) and
merge them. Do not change where the hooks write the trace.

### Step 7: tests (`tests/test_anti_silent_fallback.py`, reuse its fixtures)
1. `test_retry_after_rebind_resolves_in_originating_ledger`: deny under A, bind B,
   retry the same target; A's `denial_status` shows `resolved`, `note` names B; B's
   ledger has no `resolve` event.
2. `test_ack_by_id_recorded_under_other_issue`: deny under A, bind B,
   `along gates ack <idA> --note x`; ack lands in A, output names A.
3. `test_ack_all_across_issues`: deny under A, bind B, deny under B, `ack --all`;
   both acked, output has one line per issue. Run once from a subproject cwd if the
   fixture supports subprojects (otherwise skip that variant with a comment).
4. `test_stop_gate_holds_denial_from_previous_issue_in_turn`: deny under A, bind B,
   Stop is denied; after `ack --all` and a user prompt, Stop passes.
5. Existing single-issue tests must pass unchanged.

## Verification
```bash
python .along/scripts/test.py tests/test_anti_silent_fallback.py tests/test_subagent_denials.py
```
```bash
python .along/scripts/test.py -q
```
```bash
along sanitize
```

## Out of scope
- Listing (`along gates denials`) across issues.
- Any ledger scanning outside the trace index.
