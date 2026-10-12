---
protocol: along
protocol_version: "4.4.11"
date: 2026-10-12
slug: post-audit-regressions-and-alignment
agent: antigravity
branch: main
commit: b62fb4a
summary: Fix external and destructive confirmation regression, rollback bare slug matching, harden deletion and git classifiers
milestone: v4.5.0-multi-user-merge-automation
issues_advanced: []
issues_completed: [bug--post-audit-regressions-and-alignment]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Post audit regressions and alignment

## Summary
Fix external and destructive confirmation regression, rollback bare slug matching, harden deletion and git classifiers

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/bug--post-audit-regressions-and-alignment.md` | state | 1 | 2026-10-12T17:20:27Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/along_exec.py` | source | 2 | 2026-10-12T17:01:17Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/alongkit/bootstrap.py` | source | 1 | 2026-10-12T17:05:24Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/alongkit/hooks/predicates.py` | source | 5 | 2026-10-12T17:19:47Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/alongkit/hooks/shellparse.py` | source | 1 | 2026-10-12T17:02:50Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/alongkit/hooks/toolnature.py` | source | 3 | 2026-10-12T17:05:13Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/alongkit/session.py` | source | 2 | 2026-10-12T17:12:19Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/alongkit/verify.py` | source | 3 | 2026-10-12T17:09:19Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `tests/test_bootstrap.py` | source | 2 | 2026-10-12T17:06:11Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `tests/test_session_bindings.py` | source | 1 | 2026-10-12T17:10:11Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `tests/test_tool_nature.py` | source | 1 | 2026-10-12T17:06:47Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |

### Plan

#### Living Plan: post-audit-regressions-and-alignment

Title: Fix post-audit regressions and alignment

##### Execution Mode
Direct

##### Plan Summary
Fix the confirmation regression on external/destructive commands, rollback loose bare slug comparisons, implement path-normalized deletion classification, expand git -c keys, classify gh api and sudo, fix unbound session early exit, remove unsafe bootstrap fallback, and unify docs-only path classification.

##### Steps
- [ ] Step 1: Rollback `_bare_slug` and `_slugs_equal` in `session.py` to enforce exact slug matching, and add `confirm_destructive` and `confirm_external` helpers.
- [ ] Step 2: Add `--confirm-destructive` and `--confirm-external` flags to `along plan approve` in `along_exec.py`.
- [ ] Step 3: Fix `predicates.py`: allow EXTERNAL commands after plan approval; enforce UNKNOWN and DESTRUCTIVE checks before unbound session early exit; tighten `check_doc_manual_lock` path matching.
- [ ] Step 4: Fix `toolnature.py` and `shellparse.py`: do not strip `sudo` and classify `sudo` as DESTRUCTIVE; implement path-normalized check for `rm`/`del`/`remove-item` against repo root; expand dangerous git -c keys and `--config-env`; classify `gh api` mutations as EXTERNAL; classify `dev.py` as WORKSPACE_WRITE and external scripts as DESTRUCTIVE.
- [ ] Step 5: Remove unsafe fallback in `bootstrap.py` and update `test_bootstrap.py`.
- [ ] Step 6: Unify `is_doc_only_path` (in `verify.py`) and `is_doc_edit` (in `predicates.py`) without divergence.
- [ ] Step 7: Add comprehensive tests covering all scenarios and regression paths.
- [ ] Step 8: Run full test suite and verify 100% clean typography.

### Execution Trace

#### Execution Trace: post-audit-regressions-and-alignment
- 2026-10-12T17:00:34Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: 80317bdeed72
- 2026-10-12T17:00:49Z edit scripts/alongkit/session.py
- 2026-10-12T17:01:17Z edit scripts/along_exec.py (x2)
- 2026-10-12T17:01:56Z edit scripts/alongkit/verify.py
- 2026-10-12T17:02:42Z edit scripts/alongkit/hooks/predicates.py (x3)
- 2026-10-12T17:02:50Z edit scripts/alongkit/hooks/shellparse.py
- 2026-10-12T17:05:13Z edit scripts/alongkit/hooks/toolnature.py (x3)
- 2026-10-12T17:05:24Z edit scripts/alongkit/bootstrap.py
- 2026-10-12T17:06:11Z edit tests/test_bootstrap.py (x2)
- 2026-10-12T17:06:47Z edit tests/test_tool_nature.py
- 2026-10-12T17:08:10Z denied [require_plan_approval] run_command: Unclassified Tool Nature [gate: require-plan-approval]: Tool or command 'findstr /n' has unclassified nature. Ask the user for its nature (read-only, verific...
- 2026-10-12T17:09:19Z edit scripts/alongkit/verify.py (x2)
- 2026-10-12T17:09:36Z denied [require_plan_approval] run_command: Unclassified Tool Nature [gate: require-plan-approval]: Tool or command 'powershell Copy-Item -Path 'scripts\*' -Destination '$HOME\.along\bin\' -Recurse -Fo...
- 2026-10-12T17:10:11Z edit tests/test_session_bindings.py
- 2026-10-12T17:11:39Z denied [require_plan_approval] run_command: Unclassified Tool Nature [gate: require-plan-approval]: Tool or command 'findstr /n' has unclassified nature. Ask the user for its nature (read-only, verific... (x3)
- 2026-10-12T17:12:19Z edit scripts/alongkit/session.py
- 2026-10-12T17:12:21Z denied [require_plan_approval] run_command: Unclassified Tool Nature [gate: require-plan-approval]: Tool or command 'powershell Copy-Item -Path 'scripts\*' -Destination '$HOME\.along\bin\' -Recurse -Fo...
- 2026-10-12T17:16:42Z denied [require_plan_approval] run_command: Unclassified Tool Nature [gate: require-plan-approval]: Tool or command 'findstr /s' has unclassified nature. Ask the user for its nature (read-only, verific...
- 2026-10-12T17:16:57Z denied [require_plan_approval] run_command: Unclassified Tool Nature [gate: require-plan-approval]: Tool or command 'findstr /n' has unclassified nature. Ask the user for its nature (read-only, verific...
- 2026-10-12T17:17:01Z denied [require_plan_approval] run_command: Unclassified Tool Nature [gate: require-plan-approval]: Tool or command 'findstr /s' has unclassified nature. Ask the user for its nature (read-only, verific...
- 2026-10-12T17:18:37Z denied [require_plan_approval] run_command: Unclassified Tool Nature [gate: require-plan-approval]: Tool or command 'findstr /n' has unclassified nature. Ask the user for its nature (read-only, verific... (x2)
- 2026-10-12T17:19:47Z edit scripts/alongkit/hooks/predicates.py (x2)
- 2026-10-12T17:19:50Z denied [require_plan_approval] run_command: Unclassified Tool Nature [gate: require-plan-approval]: Tool or command 'powershell Copy-Item -Path 'scripts\*' -Destination '$HOME\.along\bin\' -Recurse -Fo...
- 2026-10-12T17:20:27Z edit .along/ISSUES/bug--post-audit-regressions-and-alignment.md
- 2026-10-12T17:24:23Z test pass (Wrap Quality Gate)
