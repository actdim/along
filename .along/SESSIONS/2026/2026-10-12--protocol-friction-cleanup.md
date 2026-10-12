---
protocol: along
protocol_version: "4.4.11"
date: 2026-10-12
slug: protocol-friction-cleanup
agent: antigravity
branch: main
commit: 1e7ecb6
summary: 'Protocol friction cleanup: plan approval wording, literal kb-search, quiet test noise'
milestone: v4.5.0-multi-user-merge-automation
issues_advanced: []
issues_completed: [debt--protocol-friction-cleanup]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Protocol friction cleanup

## Summary
Protocol friction cleanup: plan approval wording, literal kb-search, quiet test noise

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/debt--protocol-friction-cleanup.md` | state | 1 | 2026-10-12T08:00:42Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `.along/scripts/test.py` | state | 1 | 2026-10-12T07:57:46Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `AGENTS.md` | docs | 1 | 2026-10-12T07:52:42Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/along_exec.py` | source | 2 | 2026-10-12T07:52:20Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/along_kb_search.py` | source | 2 | 2026-10-12T07:57:12Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/alongkit/gates.py` | source | 2 | 2026-10-12T07:57:32Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/alongkit/hooks/predicates.py` | source | 1 | 2026-10-12T07:52:01Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `skills/along-init/protocol.md` | source | 1 | 2026-10-12T07:52:31Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `tests/test_kb_search.py` | source | 2 | 2026-10-12T08:00:15Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `tests/test_lifecycle_test_evidence.py` | source | 3 | 2026-10-12T07:59:38Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `tests/test_update_and_hooks_hardening.py` | source | 4 | 2026-10-12T07:59:18Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |

### Plan

#### Plan: debt--protocol-friction-cleanup

##### Goal
Resolve protocol friction items: plan approval wording fallback, literal kb-search mode, and quiet test runner output.

##### Steps
1. REQ-1: Update plan approval wording in protocol.md, AGENTS.md, predicates.py, and along_exec.py to state the fallback: outside plan mode, write the plan to a file and run `along plan approve --plan-file <path>` after the user's explicit yes.
2. REQ-2: Implement `--literal` in `scripts/along_kb_search.py` (case-insensitive substring search across all scopes including session logs and archived issues).
3. REQ-3: Quiet test noise: in `.along/scripts/test.py` and `tests/test_update_and_hooks_hardening.py`, silence verbose syntax gate lines, slowest tests output, and migration noise when `-q` / `--quiet` is passed.
4. Verify tests pass and wrap issue.

### Execution Trace

#### Execution Trace: protocol-friction-cleanup
- 2026-10-12T07:51:45Z plan approved (along start --approved; approved_via: cli-unverified)
- 2026-10-12T07:52:01Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-12T07:52:20Z edit scripts/along_exec.py (x2)
- 2026-10-12T07:52:31Z edit skills/along-init/protocol.md
- 2026-10-12T07:52:42Z edit AGENTS.md
- 2026-10-12T07:57:12Z edit scripts/along_kb_search.py (x2)
- 2026-10-12T07:57:32Z edit scripts/alongkit/gates.py (x2)
- 2026-10-12T07:57:46Z edit .along/scripts/test.py
- 2026-10-12T07:58:13Z edit tests/test_update_and_hooks_hardening.py (x3)
- 2026-10-12T07:58:35Z edit tests/test_lifecycle_test_evidence.py (x2)
- 2026-10-12T07:59:18Z edit tests/test_update_and_hooks_hardening.py
- 2026-10-12T07:59:38Z edit tests/test_lifecycle_test_evidence.py
- 2026-10-12T08:00:15Z edit tests/test_kb_search.py (x2)
- 2026-10-12T08:00:42Z edit .along/ISSUES/debt--protocol-friction-cleanup.md
- 2026-10-12T08:04:27Z test pass (Wrap Quality Gate)
