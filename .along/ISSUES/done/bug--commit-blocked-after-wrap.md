---
protocol: along
protocol_version: "4.4.5"
slug: commit-blocked-after-wrap
type: bug
status: done
completed: 2026-10-05
priority: high
created: 2026-10-05
updated: 2026-10-05
agent: claude-code
tags: [hooks, gates, wrap, commit]
blocked_by: []
related: [bug--session-records-not-captured, bug--hook-activation-and-gate-deadlock]
---

# along commit is blocked after along wrap: the plan gate holds the completion checklist

The completion checklist runs `along wrap` and then commits. `along wrap` ends with
`session.purge_session`, whose `unbind_slug` removes the session binding together with its plan
approval. In a repository with `enforce_unbound: true` (this one) the require-plan-approval gate
then treats the session as unbound and unapproved and rejects `along commit`: the protocol blocks
its own last step. Observed right after wrapping `task--along-update-dev-repo`; the commit needed
a fresh `along plan approve`.

`shellparse.is_along_state_command` (the plan gate's allow-list for Along CLI calls) excluded
`commit` on purpose since the session-binding work, without a recorded reason.

## Requirements
- REQ-1: `along commit` passes require-plan-approval in every phase, bound or not: it records work
  already in the tree, and its own gates bind the issue, run the tests, check typography and
  conflict markers.
- REQ-2: `along commit --fix-typography` (rewrites files), raw `git commit` / `git push`, and
  commits chained with a mutation or a write redirect stay held.
- REQ-3: Source edits after a wrap still need a new binding and approval.

## Acceptance Criteria
- [x] Hermetic tests (`tests/test_hook_activation.py`): unbound session under `enforce_unbound`: `along commit ... --all --push` passes (plain, via `along_exec.py`, chained with `along issue sync`); `--fix-typography`, `git commit`, `git push`, `&& rm`, `> out` are held; bind -> approve -> purge -> commit passes while a source edit is held.
- [x] `tests/test_session_bindings.py` allow-list assertion updated to the new rule.
- [x] Docs: `docs/topic--runtime-hooks-and-gates.md` (plan approval exemptions, completion commands).
- [x] Automated tests passing (967)
- [ ] End to end: after reinstalling globally, the commit that follows this issue's wrap goes through without a new approval.
