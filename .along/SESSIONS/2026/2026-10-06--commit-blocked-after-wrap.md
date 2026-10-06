---
protocol: along
protocol_version: "4.4.6"
date: 2026-10-06
slug: commit-blocked-after-wrap
agent: claude-code
branch: main
commit: 01984aa
summary: 'Commit gate narrowed to completion tokens: along wrap leaves a token to the session that had the plan approved; along commit -i <slug> passes only on it and consumes it; orphan blackboard approval no longer inherited by unbound sessions'
issues_advanced: []
issues_completed: [bug--commit-blocked-after-wrap]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Commit blocked after wrap

## Summary
Commit gate narrowed to completion tokens: along wrap leaves a token to the session that had the plan approved; along commit -i <slug> passes only on it and consumes it; orphan blackboard approval no longer inherited by unbound sessions

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: role-based; plan revision 2; approved: true.

| Step | Title | Status | Retries | Review |
| --- | --- | --- | --- | --- |
| 1 | Completion tokens in session.py | passed | 0 | yes |
| 2 | Narrow the shell gate | passed | 0 | yes |
| 3 | Consume the token in along_commit.py | passed | 0 | yes |
| 4 | Tests REQ-1..REQ-7 | passed | 0 | yes |
| 5 | Docs, review, end-to-end | passed | 0 | yes |
| 6 | Orphan approval is not inherited (Rev 2) | passed | 0 | yes |

### Plan

#### Living Plan: commit-blocked-after-wrap

Title: Narrow the commit gate after wrap with completion tokens
Revision: 1 - Baseline

##### Execution Mode
Role-Based (along-team). Workspace: inherit. Size: M (4 source files, 2 test files, 2 docs).

##### Requirement Traceability
| REQ | Covered by step |
| --- | --- |
| REQ-1 commit right after wrap, same session, no new approval | 1, 2, 3 |
| REQ-2 `--fix-typography`, raw git commit/push, chained mutation, redirect stay held | 2, 4 |
| REQ-3 source edits after wrap still held | 4 |
| REQ-4 wrap leaves a completion token | 1 |
| REQ-5 commit passes only with `-i <slug>` in this session's tokens | 2, 3 |
| REQ-6 token consumed by commit, expires with binding, survives `along start` | 1, 3 |
| REQ-7 gate message says why and what to run | 2 |

##### Steps
- [ ] Step 1: Completion tokens in `scripts/alongkit/session.py` (REQ-4, REQ-6)
  - `record_completion_token(repo_root, key, slug) -> bool`: if the binding of `key` has
    `plan_approved` and `approved_slug == slug`, append `{slug, approved_at, wrapped_at}` to
    `binding["completed"]` (dedupe by slug), clear `slug`, `plan_approved`, `approved_slug`,
    keep the file. False (no change) otherwise.
  - `completion_tokens(repo_root, key) -> List[str]`: slugs of this session's tokens; tokens
    with `wrapped_at` older than `BINDING_MAX_AGE_HOURS` are ignored (a later `along start`
    refreshes `updated`, so binding age alone would let a token live forever).
  - `consume_completion_token(repo_root, key, slug) -> bool`; drops the binding file when it is
    left with no slug and no tokens.
  - `completion_token_owners(repo_root, slug) -> List[str]`: keys of sessions holding a
    token for `slug` (for the REQ-7 message).
  - `purge_session(repo_root, slug, key=None, complete=False)`: with `complete=True`, call
    `record_completion_token` for `key or current_session_key()` before `unbind_slug`;
    `unbind_slug` only removes files still bound to `slug`, so the token binding stays.
    `along scratch purge` keeps the default (no token).
  - `lifecycle.execute_wrap`: `session.purge_session(repo_root, clean_slug, complete=True)`.
  - Check: `bind_session` keeps `completed` on `along start <other>`; `gc_bindings` ages out a
    slug-less binding, never flags it orphan; `resolve_active_session`/`is_unbound` treat it as
    unbound.
- [ ] Step 2: Narrow the shell gate (REQ-2, REQ-5, REQ-7)
  - `shellparse.py`: remove `_ALONG_COMPLETION`, `_is_completion_subcommand` and the commit
    branch of `is_along_state_command`. Add `along_commit_issue(command) -> Optional[str]`:
    the `-i x` / `--issue x` / `--issue=x` value when exactly one segment is `along commit`
    (CLI or `along_exec.py commit`), it has no `--fix-typography` and no write redirect, and
    every other segment is a state or read-only command; `""` for such a commit without `-i`;
    None otherwise.
  - `predicates.check_mutation_authorization`: in the shell branch, before the unbound
    short-circuit: if `along_commit_issue(cmd)` is non-empty and `parse_key(issue)[1]` is in
    `session.completion_tokens(repo_root, key)`, return None. Otherwise the normal approval
    check; when it holds an `along commit`, the reason names the cause (no `-i`; no token in
    this session; token held by another session) and what to run. The closeout branch
    (`feat--parallel-session-closeout` REQ-6) is added by that ticket, no stub here.
- [ ] Step 3: Consume the token in `scripts/along_commit.py` (REQ-6)
  - After a successful `git commit`, `session.consume_completion_token(repo_root,
    session.current_session_key(), active_issue["slug"])` when an issue was resolved.
- [ ] Step 4: Tests (REQ-1..REQ-7, positive and negative)
  - `tests/test_hook_activation.py::TestPlanGate` (replace the three b7d1379 tests): same-session
    commit after wrap passes; other session held (message names it); `-i <other>` held; no `-i`
    held; unapproved wrap gives no token; `bug--<slug>` form accepted; REQ-2 cases held; source
    edit after wrap held; `complete=False` purge mints nothing.
  - `tests/test_session_bindings.py`: token survives `along start other`, consumed once, aged
    token ignored, gc removes an aged slug-less binding; restore
    `test_along_state_commands_pass_the_plan_gate` (`along commit -m x` is NOT a state command).
  - Commit consumes the token (hermetic git fixture).
- [ ] Step 5: Docs, review, end-to-end
  - `docs/topic--runtime-hooks-and-gates.md` "Completion commands" bullet -> token rule;
    `docs/topic--cli-reference.md` (`along wrap`, `along commit`). `/along-kb-sync`.
  - Full suite, typography, `git diff --stat`, blast radius (static search, code-review-graph
    offline).
  - Reinstall globally (`install.ps1 -Target all`, writes under `~/.along`) and verify end to
    end: wrap -> commit passes in this session; commit from another session key is held.

##### Revision 2 (2026-10-06, re-plan after the step 5 end-to-end finding, approved by the user)
Finding: an unbound session with a known id resolves ('single') to the one in-progress
blackboard no other session is bound to and inherits that blackboard's `plan_approved` and
phase. An orphan blackboard (its session ended) thus approves every fresh session, so REQ-5
("every other unapproved commit is held") fails end to end.
- [ ] Step 6: Orphan approval is not inherited (REQ-5)
  - `session.is_plan_approved`: when the session id is known, a blackboard's `plan_approved`
    counts only for the session bound to that slug (binding `slug`, or `ALONG_ISSUE_SLUG` from a
    runner). Sessions without an id keep the repository-level behavior. The binding's own
    approval (ExitPlanMode before `along start`) is unchanged.
  - Tests: fresh session with an orphan approved blackboard is held for `touch` and
    `along commit -i <orphan>`; bound session approved via its blackboard still passes; key-less
    runtime keeps the single-blackboard approval.
- Step 5 (docs, review, end to end) is finished after step 6; docs note the rule in 2.8.

##### Commit scope
Only this ticket's files, via `along commit --paths ... -i commit-blocked-after-wrap`.

### Research

#### Research: commit-blocked-after-wrap

Verified against the code on 2026-10-05.

##### Symbols
- `scripts/alongkit/session.py`
  - `bind_session` (226): loads the existing binding and keeps unknown keys, so a `completed`
    list survives `along start <other>`; it resets `plan_approved`/`approved_slug` when the slug
    changes.
  - `record_plan_approval` (253): sets `plan_approved`, `approved_slug`, `approved_at`.
  - `unbind_slug` (269): deletes every binding file whose `slug` matches (any session).
  - `gc_bindings` (302): age by `updated` (72 h) or orphan (`slug` set, no blackboard). A binding
    with no `slug` is never an orphan, only aged out.
  - `resolve_active_session` (344): a binding without `slug` falls through to the
    in-progress candidates ('single' / 'ambiguous' / 'none'), so `is_unbound` stays True.
  - `is_plan_approved` (411): `plan_approved` false -> not approved. OK for a token-only binding.
  - `purge_session` (768): `unbind_slug` + rmtree. Called by `lifecycle.execute_wrap` (541) and
    `along scratch purge` (`along_exec.py:1661`).
- `scripts/alongkit/hooks/shellparse.py`: `_ALONG_COMPLETION`, `_COMPLETION_REWRITE_FLAGS`,
  `_is_completion_subcommand`, `is_along_state_command` (b7d1379 blanket allow, 503-551).
  `_along_subcommand` lower-cases the words (slugs are lower-case kebab, so harmless).
- `scripts/alongkit/hooks/predicates.py::check_mutation_authorization` (583): shell commands pass
  when read-only / state / verification; then `is_unbound` short-circuit unless
  `enforce_unbound`; then approval + phase.
- `scripts/alongkit/lifecycle.py::execute_wrap`: `clean_slug` from `entities.parse_key` (bare
  slug), session log written, then `session.purge_session(repo_root, clean_slug)`.
- `scripts/along_commit.py::main`: `-i/--issue`, `--all`, `--paths`, `--push`; issue resolved by
  `entities.resolve_active_issue` (accepts `slug` and `<type>--<slug>`). Commit at 192, push at 203.
- `entities.parse_key(key) -> (type|None, slug)` normalizes `bug--x` and `x`.

##### Tests touching the gate
- `tests/test_hook_activation.py::TestPlanGate`: `test_along_commit_passes_for_an_unbound_session`,
  `test_rewriting_commit_and_raw_git_commit_stay_held`, `test_commit_right_after_wrap_purge`.
- `tests/test_session_bindings.py::test_along_state_commands_pass_the_plan_gate` (commit in the
  allowed list since b7d1379), `TestBindingLifecycle::test_purge_removes_bindings_and_matching_pointer`
  (unapproved binding: still removed, no token).

##### Docs
- `docs/topic--runtime-hooks-and-gates.md:153` "Completion commands" bullet.
- `docs/topic--cli-reference.md`: `### along wrap` (331), `### along commit` (398).
- Skills `along-wrap` / `along-commit`: no mention of bindings; no change needed.

##### Constraints / risks
- The closeout approval set (REQ-5 second branch) belongs to `feat--parallel-session-closeout`
  REQ-6; this ticket leaves the gate ready for it but adds no stub.
- PowerShell cmdlets are not classified read-only by the plan gate (F7); use the file tools.
- `scratch purge` must not mint tokens: only wrap records completion.
- code-review-graph MCP failed to connect this session: blast radius by static search.

### Execution Trace

#### Execution Trace: commit-blocked-after-wrap

- 2026-10-05 type: incident: circuit breaker tripped (`.git/index: bad signature`) while writing
  plan.md; user rebuilt the index and reset the breaker.
- 2026-10-06 type: incident: `along scratch init --help` created a `--help` blackboard (known
  `bug--subcommand-help-as-argument`); removed, case added to that issue.
- 2026-10-06 step 1-4 passed; full suite 980 OK; global reinstall done (`install.ps1 -Target all`).
- 2026-10-06 type: finding (step 5 end-to-end): a fresh session id is NOT held by the installed
  plan gate for `touch x` or `along commit -i ...`. Cause predates this ticket:
  `resolve_active_session` gives an unbound session the single in-progress blackboard not bound
  to another session (`release-tags-not-pushed`, orphaned: its session's binding is gone, state
  `plan_approved: true, phase: execution`), and `is_plan_approved` / `get_session_phase` then read
  that blackboard's approval. Any unbound session inherits an orphan's approval. Escalated to the
  user: fix here (Rev 2) or separate bug.

### Review step-1

#### Review: Step 1 - Completion tokens in session.py

VERDICT: PASS

- `session.py`: `record_completion_token`, `completion_tokens` (tokens older than
  `BINDING_MAX_AGE_HOURS` by `wrapped_at` are ignored), `completion_token_owners`,
  `consume_completion_token` (removes a binding left with no slug and no tokens);
  `purge_session(..., key=None, complete=False)` records the token before `unbind_slug`.
- `lifecycle.execute_wrap` passes `complete=True`; `along scratch purge` keeps the default.
- Checked by reading: `unbind_slug` only removes bindings whose `slug` matches (token binding has
  `slug: None`); `gc_bindings` never flags a slug-less binding orphan, ages it out by `updated`;
  `resolve_active_session` treats it as unbound; `bind_session` keeps `completed` (unknown keys
  preserved) and finds no pending approval.

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [test_session_bindings, test_hook_activation: 44 OK; full suite at step 4]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-4, REQ-6]
- Blast Radius: DEGRADED (PASS) [static search: purge_session callers lifecycle.py:541, along_exec.py:1661; code-review-graph offline]
- Documentation Parity: SKIPPED (docs in step 5)
- Clean Typography: EXECUTED (PASS)

### Review step-2

#### Review: Step 2 - Narrow the shell gate

VERDICT: PASS

- `shellparse.py`: blanket `_ALONG_COMPLETION` allow removed; `is_along_state_command` accepts
  state subcommands only. New `_along_words` (token list; `_along_subcommand` built on it),
  `along_commit_issue` (works on tokens, so a quoted message containing `-i` is not read as the
  flag), `is_along_commit`, `_commit_issue_value` (`-i x`, `--issue x`, `--issue=x`).
- `predicates.check_mutation_authorization`: passes an `along commit` whose issue
  (`parse_key` normalizes `bug--x`) is in this session's `completion_tokens`; a held commit
  gets `_held_commit_reason` (rewrite/redirect/chain, no `-i`, other session's token, no token).
- Expected failures (5): the three b7d1379 tests in `test_hook_activation.py` and the commit
  line of `test_along_state_commands_pass_the_plan_gate`, all asserting the blanket allow this
  step removes. They are replaced in step 4.

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [44 run; 5 expected failures of the removed behavior, replaced in step 4]
- Diff Scope Audit: EXECUTED (PASS) [predicates.py diff is this step only]
- Requirement Traceability: EXECUTED (PASS) [REQ-2, REQ-5, REQ-7]
- Blast Radius: DEGRADED (PASS) [static search: is_along_state_command callers predicates.py only; along_subcommand callers unchanged; code-review-graph offline]
- Documentation Parity: SKIPPED (docs in step 5)
- Clean Typography: EXECUTED (PASS)

### Review step-3

#### Review: Step 3 - Consume the token in along_commit.py

VERDICT: PASS

- `scripts/along_commit.py`: after a successful `git commit`, `session.consume_completion_token`
  for the resolved issue slug and this process's session key; prints when a token was used.
  Placed before the optional push: the commit is what the token authorizes.
- No-op when no issue was resolved or the session holds no token (`consume` returns False).
- Test of the consumption is part of step 4 (`tests/test_commit.py`, hermetic git fixture).

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [compileall; behavior test in step 4]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-6]
- Blast Radius: DEGRADED (PASS) [static search: along_commit.main callers tests/test_commit.py, along_exec dispatch; code-review-graph offline]
- Documentation Parity: SKIPPED (docs in step 5)
- Clean Typography: EXECUTED (PASS)

### Review step-4

#### Review: Step 4 - Tests REQ-1..REQ-7

VERDICT: PASS

- `tests/test_hook_activation.py`: the three b7d1379 tests replaced by `TestCommitAfterWrap`
  (10 tests): wrapping session commits (`-i`, `--issue=`, `bug--` key, `along_exec.py`, chained
  with a state command); other session held, message names the wrapping session; other issue
  held; no `-i` held; quoted message containing `-i` is not the flag; unapproved wrap and
  `scratch purge` leave no token; `--fix-typography`, raw git commit/push, chained mutation,
  redirect and a double commit held; source edit after wrap held; consumed token holds the
  second commit and removes the empty binding.
- `tests/test_session_bindings.py`: `test_along_state_commands_pass_the_plan_gate` restored
  (`along commit -m x` is not a state command); `TestCompletionTokens` (5 tests): token and
  unbind, other sessions' bindings of the slug removed, token survives `along start`, consume
  once (binding with a slug kept), expiry by age and gc.
- `tests/test_commit.py::test_14_commit_consumes_completion_token`: hermetic git fixture,
  `along_commit.main` consumes the token and binds `refs #work`.

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [python .along/scripts/test.py -q: 980 OK]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-1..REQ-7]
- Blast Radius: DEGRADED (PASS) [static search; code-review-graph offline]
- Documentation Parity: SKIPPED (docs in step 5)
- Clean Typography: EXECUTED (PASS)

### Review step-5

#### Review: Step 5 - Docs, review, end-to-end

VERDICT: PASS

- Docs: `docs/topic--runtime-hooks-and-gates.md` (2.8: "Completion tokens" replaces "Completion
  commands"; state-command line; orphan approval rule in Resolution; housekeeping line);
  `docs/topic--cli-reference.md` (`along wrap` completion token, `along commit` after wrap,
  `--all`/`--paths`/`--push`). `along kb-sync`: links OK; `llms-full.txt` and `docs/INDEX.md`
  regenerated. Skills and README: no binding/commit-gate text to change.
- Typography: `along sanitize` 752 files, clean.
- Global reinstall (`install.ps1 -Target all`, user approved) three times (after step 4, after
  step 6, after the message tweak).
- End to end, installed hook, fresh session id `fresh-e2e-probe`:
  - before Rev 2: `touch x.txt` and `along commit -i commit-blocked-after-wrap` passed (orphan
    approval, see trace) -> re-plan to Rev 2;
  - after Rev 2: both held (exit 2); the commit message explains "no completion token for
    'commit-blocked-after-wrap'". Message for an unbound session no longer names another
    session's issue as its own.
  - Same-session wrap -> commit is exercised by the real completion of this ticket
    (`along wrap` then `along commit -i commit-blocked-after-wrap --paths ...`).

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [983 OK after step 6; targeted 71 OK after the message tweak]
- Diff Scope Audit: EXECUTED (PASS) [other sessions' files untouched, not staged]
- Requirement Traceability: EXECUTED (PASS) [REQ-1..REQ-7]
- Blast Radius: DEGRADED (PASS) [static search; code-review-graph offline]
- Documentation Parity: EXECUTED (PASS)
- Clean Typography: EXECUTED (PASS)

### Review step-6

#### Review: Step 6 - Orphan approval is not inherited (Rev 2)

VERDICT: PASS

- `session.is_plan_approved`: with a known session id, a blackboard's `plan_approved` counts only
  when the session's binding `slug` (or `ALONG_ISSUE_SLUG` from a runner) is that slug. The
  binding's own approval path is unchanged; key-less runtimes keep the single-blackboard rule.
- Tests: `TestCommitAfterWrap.test_fresh_session_does_not_inherit_an_orphan_approval` (held for
  `touch` and `along commit -i orphan`; passes once bound), `TestOrphanApproval` (2 tests).
- Blast radius: `is_plan_approved` callers (static search): `predicates.check_mutation_authorization`,
  `along plan status` (`along_exec.py:969`), `along start` (`along_exec.py:847`). Behavior change
  at `along start`: a session starting an issue whose blackboard another session approved no
  longer inherits that approval (consistent with the rule; the same session restarting keeps it
  through its binding; `--approved` stays for scripted runs). Full suite green.

Gate Execution Manifest:
- Workspace Isolation: EXECUTED (PASS) [mode: inherit (default)]
- File Integrity: EXECUTED (PASS)
- Automated Tests: EXECUTED (PASS) [python .along/scripts/test.py -q: 983 OK]
- Diff Scope Audit: EXECUTED (PASS)
- Requirement Traceability: EXECUTED (PASS) [REQ-5]
- Blast Radius: DEGRADED (PASS) [static search; code-review-graph offline]
- Documentation Parity: EXECUTED (PASS) [docs/topic--runtime-hooks-and-gates.md 2.8 Resolution]
- Clean Typography: EXECUTED (PASS)
