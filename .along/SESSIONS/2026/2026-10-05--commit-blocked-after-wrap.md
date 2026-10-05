---
protocol: along
protocol_version: "4.4.5"
date: 2026-10-05
slug: commit-blocked-after-wrap
agent: claude-code
branch: main
commit: 7e51aa7
summary: along commit passes the plan gate as a completion command, so the checklist can commit after wrap unbinds the session; --fix-typography and raw git commit stay held
issues_advanced: []
issues_completed: [bug--commit-blocked-after-wrap]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Commit blocked after wrap

## Summary
along commit passes the plan gate as a completion command, so the checklist can commit after wrap unbinds the session; --fix-typography and raw git commit stay held

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

| Step | Title | Status | Retries | Review |
| --- | --- | --- | --- | --- |
| 1 | Step 1 | passed | 0 | no |

### Plan

#### Living Plan: commit-blocked-after-wrap

Title: along commit is blocked after along wrap: the plan gate holds the completion checklist

User instruction in chat on 2026-10-05: "чини сразу" (fix it right away).

##### Problem
`along wrap` -> `purge_session` -> `unbind_slug` drops the session binding and its plan approval.
With `enforce_unbound: true` the require-plan-approval gate then rejects `along commit`, the next
step of the completion checklist (wrap before commit). Observed in this session after wrapping
`task--along-update-dev-repo`.

##### Steps
- [ ] Step 1: `shellparse`: `along commit` is a completion command that passes the plan gate in
  every phase (it stages and commits the tree; its own gates bind the issue, run tests, check
  typography and conflict markers). Not with `--fix-typography`, which rewrites files.
  Raw `git commit` / `git push` stay held (the protocol routes commits through `along commit`).
- [ ] Step 2: Tests (`tests/test_hook_activation.py`): unbound session under enforce_unbound:
  `along commit ... --all --push` passes; `--fix-typography` and `git commit` are held; a commit
  right after a wrap passes end to end (bind, approve, purge, commit).
- [ ] Step 3: Docs (`docs/topic--runtime-hooks-and-gates.md` plan-gate paragraph).
- [ ] Step 4: Tests, close, wrap, commit, push, reinstall globally.

### Research

#### Research & Findings: commit-blocked-after-wrap

##### Target Symbols and Files
- `scripts/alongkit/hooks/predicates.py`: `check_mutation_authorization` (require-plan-approval); shell commands pass when `is_read_only_command`, `is_along_state_command` or `is_verification_command`.
- `scripts/alongkit/hooks/shellparse.py`: `_ALONG_STATE`, `is_along_state_command`; new `_ALONG_COMPLETION`, `_COMPLETION_REWRITE_FLAGS`, `_is_completion_subcommand`.
- `scripts/alongkit/lifecycle.py`: `execute_wrap` -> `session.purge_session` -> `unbind_slug`.

##### Constraints & Risks
- `tests/test_session_bindings.py::test_along_state_commands_pass_the_plan_gate` asserted `along commit -m x` is NOT allowed (from 696da92, session bindings, no recorded reason). Reversed deliberately; the rewriting form keeps the old behaviour.
- The fix reaches the live hooks only after the global reinstall; until then a commit after wrap still needs `along plan approve`.

##### Architectural Patterns
- Alternative considered: keep the binding after wrap in a "completion" phase. Rejected for now: more state, and the commit already carries its own gates; revisit with bug--session-records-not-captured if wrap should keep a record-only binding.
