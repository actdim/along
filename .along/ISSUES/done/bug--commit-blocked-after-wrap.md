---
protocol: along
protocol_version: "4.4.5"
slug: commit-blocked-after-wrap
type: bug
status: done
completed: 2026-10-06
priority: high
created: 2026-10-05
updated: 2026-10-06
agent: claude-code
tags: [hooks, gates, wrap, commit, reopened]
blocked_by: []
related: [feat--parallel-session-closeout, bug--session-records-not-captured, bug--hook-activation-and-gate-deadlock]
---

# along commit is blocked after along wrap: the plan gate holds the completion checklist

**Reopened 2026-10-05.** The first fix (commit b7d1379) is too broad: it must be narrowed.
Start with "Implementation plan (reopened)" below.

## Background
The completion checklist runs `along wrap` and then commits. `along wrap` ends with
`session.purge_session`, whose `unbind_slug` removes the session binding together with its plan
approval. With `enforce_unbound: true` (this repository) the require-plan-approval gate then
rejects `along commit`: the protocol blocks its own last step.

## What b7d1379 did (current state on main)
- `scripts/alongkit/hooks/shellparse.py`: `_ALONG_COMPLETION = ("commit",)`,
  `_COMPLETION_REWRITE_FLAGS = ("--fix-typography",)`, `_is_completion_subcommand()`;
  `is_along_state_command()` returns True for `along commit ...` (any session, any slug).
- `tests/test_hook_activation.py` (`TestPlanGate`): `test_along_commit_passes_for_an_unbound_session`,
  `test_rewriting_commit_and_raw_git_commit_stay_held`, `test_commit_right_after_wrap_purge`.
- `tests/test_session_bindings.py::test_along_state_commands_pass_the_plan_gate`: `along commit -m x`
  moved to the allowed list (it used to assert the opposite, since 696da92, no recorded reason).
- `docs/topic--runtime-hooks-and-gates.md`: "Completion commands" bullet.

## Why it is wrong
Any session, with no approval at all, can now run `along commit --all --push`:
- it commits whatever is in the working tree, including another parallel session's unfinished
  edits or the user's manual work (this happened today: 23 files of a parallel session sat in the
  tree);
- `--push` publishes without any approval;
- `-i <slug>` accepts any existing slug, even a long-closed one, so the issue binding restricts
  nothing.

## Requirements
- REQ-1 (kept): the session that wrapped an approved issue can commit it right after the wrap,
  without a new approval.
- REQ-2 (kept): `along commit --fix-typography`, raw `git commit` / `git push`, and commits chained
  with a mutation or a write redirect stay held.
- REQ-3 (kept): source edits after a wrap still need a new binding and approval.
- REQ-4: `along wrap` leaves a completion token instead of erasing every trace of the approval:
  before `unbind_slug`, if this session's binding has `plan_approved` for the wrapped slug, the
  binding keeps `completed: [{slug, approved_at, wrapped_at}]` (binding stays, `slug` cleared,
  `plan_approved` false).
- REQ-5: The plan gate lets `along commit` through without approval only when its issue
  (`-i/--issue <slug>`, required for this path) is in this session's `completed` tokens, or is
  covered by a closeout approval (`feat--parallel-session-closeout` REQ-6). Every other
  unapproved commit is held as before b7d1379. A bound, approved session commits as before.
- REQ-6: Token lifetime: removed by a successful `along commit` that references the slug, and
  expires with the binding (`gc_bindings`, `BINDING_MAX_AGE_HOURS`). A new `along start` does not
  drop tokens (parallel issues in one session are normal).
- REQ-7: The gate message for a held commit says why (no token, other session's issue, closeout
  not approved) and what to run.

## Implementation plan (reopened)
1. `scripts/alongkit/session.py`: helpers `record_completion_token(repo_root, key, slug)`,
   `completion_tokens(repo_root, key) -> List[str]`, `consume_completion_token(repo_root, key, slug)`.
   Call `record_completion_token` from `purge_session` (or from `lifecycle.execute_wrap` right before
   `session.purge_session`, with `current_session_key()`), only when the binding's
   `approved_slug == slug`; then clear `slug`/`plan_approved` instead of deleting the file.
   Check `unbind_slug`, `gc_bindings`, `resolve_active_session` and `is_unbound` against a
   binding that has tokens but no slug.
2. `scripts/alongkit/hooks/shellparse.py`: replace the blanket `_ALONG_COMPLETION` allow with a
   parser `along_commit_issue(command) -> Optional[str]` (the `-i/--issue` value of an
   `along commit` segment, None if absent or if `--fix-typography`/redirect/chained mutation).
   `is_along_state_command` no longer accepts `commit`.
3. `scripts/alongkit/hooks/predicates.py::check_mutation_authorization`: for shell commands, if
   `along_commit_issue(cmd)` is in `session.completion_tokens(repo_root, key)` or in the closeout
   approval set, return None; otherwise continue to the normal approval check.
4. `scripts/along_commit.py`: after a successful commit, `consume_completion_token` for the
   referenced slug (current session key).
5. Tests (`tests/test_hook_activation.py`, `tests/test_session_bindings.py`):
   - bind, approve, wrap/purge, `along commit -i <slug> --all --push` passes;
   - the same commit from another session key is held;
   - `along commit -i <other-slug>` from the wrapping session is held;
   - `along commit` without `-i` from an unbound session is held;
   - an unapproved bound session that wraps gets no token;
   - token consumed after commit (second commit held); token survives `along start <other>`;
   - REQ-2 cases stay held; source edit after wrap held;
   - restore `test_along_state_commands_pass_the_plan_gate` to "commit is not a state command".
6. Docs: replace the "Completion commands" bullet in `docs/topic--runtime-hooks-and-gates.md`
   with the token rule; `docs/topic--cli-reference.md` (`along commit`, `along wrap`).
7. Reinstall globally (`install.ps1 -Target all`) and verify end to end: wrap -> commit passes in
   the same session; a fresh unbound session cannot commit.

## Acceptance Criteria
- [x] REQ-1..REQ-7 covered by hermetic tests, positive and negative.
- [x] b7d1379 blanket allow removed; old allow-list assertion restored.
- [x] Docs updated.
- [x] Automated tests passing.
- [x] End to end after reinstall: commit right after wrap passes in the wrapping session only.

## Resolution (2026-10-06)
- Completion tokens in the session binding (`session.record_completion_token`,
  `completion_tokens`, `consume_completion_token`, `completion_token_owners`;
  `purge_session(..., complete=True)` from `along wrap` only).
- Plan gate: `shellparse.along_commit_issue` + token check in
  `predicates.check_mutation_authorization`; held commits explain why (`_held_commit_reason`).
- `along commit` consumes the token after a successful commit.
- Plan revision 2 (end-to-end finding, approved by the user): an unbound session with a known id
  resolved to the single unbound in-progress blackboard and inherited its approval (an orphan of
  `release-tags-not-pushed` approved every fresh session). `session.is_plan_approved` now counts a
  blackboard's approval only for the session bound to it. Side effect: `along start` of an issue
  another session approved starts unapproved.
- The closeout approval branch of REQ-5 is left to `feat--parallel-session-closeout` REQ-6.

## Notes
- Verified on 2026-10-05 that b7d1379 lets the commit after wrap through (commit b7d1379 itself
  was made that way); this verification is what showed the rule is too broad.
- Execution order with the related tickets: this one first (it closes a loosened gate), then
  `bug--session-records-not-captured`, then `feat--parallel-session-closeout`.
