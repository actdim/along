---
protocol: along
protocol_version: "4.4.16"
date: 2026-10-17
slug: gate-simplification
agent: claude-code
branch: main
commit: af0c91f
summary: 'Gates judge results, not commands: removed tool-nature classifier, circuit breaker and fast_retrieval; plan gate checks file targets and end-of-turn git status; narrow destructive_command gate; content rules commit-time via along lint; audit target and loop stats'
issues_advanced: []
issues_completed: [debt--gate-simplification]
decisions: [gates-judge-results-not-commands]
risks_logged: []
spikes_conducted: []
---

# Session: Gate simplification

## Summary
Gates judge results, not commands: removed tool-nature classifier, circuit breaker and fast_retrieval; plan gate checks file targets and end-of-turn git status; narrow destructive_command gate; content rules commit-time via along lint; audit target and loop stats

## Decisions
- [gates-judge-results-not-commands]

## Blackboard Record

Execution mode: role-based; plan revision 1; approved: true.

| Step | Title | Status | Retries | Review |
| --- | --- | --- | --- | --- |
| 1 | Step 1 | passed | 0 | yes |

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/DECISIONS/ADR-2026-10-17--gates-judge-results-not-commands.md` | state | 1 | 2026-10-17T17:54:12Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `.along/ISSUES/debt--gate-config-layers.md` | state | 1 | 2026-10-17T17:54:39Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `.along/ISSUES/debt--gate-simplification.md` | state | 1 | 2026-10-17T17:55:08Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `.along/ISSUES/task--gate-event-remeasure.md` | state | 1 | 2026-10-17T17:54:40Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `AGENTS.md` | docs | 7 | 2026-10-17T17:46:48Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `docs/topic--agent-run-protocol.md` | docs | 3 | 2026-10-17T17:58:17Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `docs/topic--cli-reference.md` | docs | 8 | 2026-10-17T17:58:30Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `docs/topic--declarative-gates-and-traceability.md` | docs | 11 | 2026-10-17T17:57:09Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `docs/topic--migrations.md` | docs | 1 | 2026-10-17T17:58:34Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `docs/topic--runtime-hooks-and-gates.md` | docs | 27 | 2026-10-17T17:56:14Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `docs/topic--skills-reference.md` | docs | 1 | 2026-10-17T17:58:06Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `docs/topic--troubleshooting.md` | docs | 3 | 2026-10-17T17:57:58Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/along_exec.py` | source | 9 | 2026-10-17T17:51:03Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/__init__.py` | source | 2 | 2026-10-17T17:32:53Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/closeout.py` | source | 3 | 2026-10-17T17:31:01Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/commands/__init__.py` | source | 5 | 2026-10-17T17:51:01Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/commands/doctor.py` | source | 2 | 2026-10-17T17:32:51Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/commands/gates.py` | source | 3 | 2026-10-17T17:51:37Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/commands/lifecycle.py` | source | 4 | 2026-10-17T17:35:52Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/commands/ops.py` | source | 4 | 2026-10-17T17:32:37Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/entities/mutation.py` | source | 1 | 2026-10-17T17:31:03Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/gates.py` | source | 1 | 2026-10-17T17:31:02Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/gatestats.py` | source | 2 | 2026-10-17T17:51:36Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/gitgates.py` | source | 5 | 2026-10-17T17:31:20Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/hooks/config.py` | source | 6 | 2026-10-17T17:52:49Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/hooks/containment.py` | source | 1 | 2026-10-17T17:49:50Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/hooks/declarative.py` | source | 6 | 2026-10-17T17:34:57Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/hooks/default_gates.yaml` | source | 6 | 2026-10-17T17:50:34Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/hooks/deletion.py` | source | 4 | 2026-10-17T17:52:21Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/hooks/engine.py` | source | 2 | 2026-10-17T17:50:44Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/hooks/predicates.py` | source | 17 | 2026-10-17T17:55:24Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/hooks/shellparse.py` | source | 1 | 2026-10-17T17:36:18Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/hooks/turnstate.py` | source | 1 | 2026-10-17T17:33:59Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/lifecycle.py` | source | 2 | 2026-10-17T17:31:03Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/merge.py` | source | 4 | 2026-10-17T17:31:26Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/proc.py` | source | 5 | 2026-10-17T17:31:47Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/session.py` | source | 1 | 2026-10-17T17:35:49Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/testruns.py` | source | 1 | 2026-10-17T17:31:04Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `scripts/alongkit/verify.py` | source | 1 | 2026-10-17T17:31:05Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `skills/along-init/protocol.md` | source | 7 | 2026-10-17T17:46:32Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `skills/along-kb-search/SKILL.md` | source | 1 | 2026-10-17T17:46:59Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_ai_coauthor_attribution.py` | source | 1 | 2026-10-17T18:00:43Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_alongkit.py` | source | 1 | 2026-10-17T17:30:43Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_cli_safety_patterns.py` | source | 1 | 2026-10-17T18:00:43Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_conflict_marker_gate.py` | source | 1 | 2026-10-17T17:30:42Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_declarative_gates.py` | source | 3 | 2026-10-17T17:43:21Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_destructive_command.py` | source | 5 | 2026-10-17T18:00:47Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_error_handling_and_io.py` | source | 1 | 2026-10-17T17:45:48Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_git_gate_enforcement.py` | source | 1 | 2026-10-17T18:00:44Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_hook_activation.py` | source | 7 | 2026-10-17T18:02:29Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_hooks_audit_scrubbing.py` | source | 5 | 2026-10-17T17:52:52Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_hooks_claude.py` | source | 1 | 2026-10-17T18:01:21Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_hooks_codex.py` | source | 1 | 2026-10-17T18:01:40Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_hooks_core.py` | source | 5 | 2026-10-17T18:02:22Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_hooks_generic.py` | source | 1 | 2026-10-17T18:02:22Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_hooks_tool_coverage.py` | source | 1 | 2026-10-17T17:45:32Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_inquiry_gate.py` | source | 1 | 2026-10-17T17:46:01Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_lifecycle_wrap.py` | source | 1 | 2026-10-17T17:45:16Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_output_distillation.py` | source | 2 | 2026-10-17T17:30:44Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_parallel_closeout.py` | source | 1 | 2026-10-17T17:46:00Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_repo_state_gates.py` | source | 1 | 2026-10-17T18:00:45Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_rule_pack_protection.py` | source | 1 | 2026-10-17T17:45:31Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_runtime_detection.py` | source | 1 | 2026-10-17T17:30:45Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_session_bindings.py` | source | 3 | 2026-10-17T17:45:06Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_session_create.py` | source | 3 | 2026-10-17T17:30:47Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_shell_classification.py` | source | 9 | 2026-10-17T18:00:56Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_subcommand_help.py` | source | 1 | 2026-10-17T17:45:36Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_update_maintenance_friction.py` | source | 3 | 2026-10-17T17:45:15Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |
| `tests/test_workspace_containment.py` | source | 1 | 2026-10-17T18:00:46Z | claude--9d7ca833-45a1-4de5-bb24-0d65e05e8c19 |

### Plan

#### Living Plan: gate-simplification

Title: Gate simplification

Approved by the user via ExitPlanMode on 2026-10-17 (copied here from the plan-mode file;
the ExitPlanMode capture did not reach the blackboard because the installed global hook is
the pre-change version).

##### Steps
- [x] Step 1: Gate simplification, plan phases 1-6 below (review: reviews/step-1.md)

##### Approved plan

Execution Mode: Role-Based (along-team step loop; one step covering the phases below, review record per step).

###### Context

86% of gate events are `require_plan_approval`, 77% of all events are "Inquiry Read-Only" blocks on
read-only shell commands (`git`, `python`, `findstr`...). Root cause: gates predict harm from command
text via a 1700-line tool-nature classifier, which is undecidable. Target: gates decide only by facts
known exactly (write-tool target path, a short list of explicit dangerous commands, `git status` at
end of turn / commit). Isolation belongs to the container (ADR docker-isolation-now-gvisor-later).

Already true (verified, no work): projection sync runs automatically at Stop; `count_docs` is opt-in
by default; typography, anti-stub, AI co-author are already checked at commit time by
`alongkit/gitgates.py`. The 63 `wrapped_work_uncommitted` "deny" decisions are shadow-mode records.

###### Phase 1 - Remove the classifier, circuit breaker, fast_retrieval
- Delete `hooks/toolnature.py`, `along tool`, `tests/test_tool_nature.py`.
- `shellparse.py`: drop the read-only/verification command lists and classification.
- Remove `circuit_breaker`, `alongkit/circuit.py`, `along circuit`, `trip_on_anomaly`, the doctor
  check, `tests/test_circuit_breaker.py`.
- Remove `fast_retrieval` gate, predicate and tests.
- Remove destructive/external confirmation and `along plan approve --confirm-destructive`.
- Close `feat--tool-class-model` as superseded.

###### Phase 2 - require_plan_approval by result
- Write tools: path check. Shell: never checked at PreToolUse.
- Snapshot `git status` + hashes at UserPromptSubmit; at Stop hold once when the turn changed
  files outside Along state and planning artifacts without an approved plan.
- `rule_pack_protection`: write tools only at runtime; shell edits caught at commit.

###### Phase 3 - Narrow destructive-command gate (`hooks/deletion.py`)
- Explicit forms only; hold when a target is outside the repo, empty, unexpandable or holds
  uncommitted work; `git reset --hard` / `git clean -f` by git state; `push --force` always.
  ASK interactive / DENY autonomous. `cli_safety` warns.

###### Phase 4 - Smaller gate fixes
- `require_active_issue` ignores `.along/` state; typography, anti_stub_injection,
  commit_no_ai_coauthor commit-time only; `along lint`; gate tags removed from AGENTS.md.

###### Phase 5 - Observability
- Audit `target` (redacted, 200 chars), `warn` for shadow records; `along gates stats` loops.

###### Phase 6 - Docs, ADR, wrap
- ADR, docs updates.

###### Out of scope
- debt--gate-config-layers, task--gate-event-remeasure.

### Execution Trace

#### Execution Trace: gate-simplification
- 2026-10-17T17:15:59Z phase: planning -> execution
- 2026-10-17T17:15:59Z plan approved (ExitPlanMode) approved_via: exit-plan-mode
- 2026-10-17T17:16:09Z step 1: pending -> in-progress
- 2026-10-17T17:30:26Z denied [require_plan_approval] run_command: Destructive Action [gate: require-plan-approval]: Tool or command 'python C:/Users/Admin/AppData/Local/Temp/claude/D--Src-my-actdim-public-along/9d7ca833-45a...
- 2026-10-17T17:30:42Z edit tests/test_conflict_marker_gate.py
- 2026-10-17T17:30:43Z edit tests/test_alongkit.py
- 2026-10-17T17:30:44Z edit tests/test_output_distillation.py (x2)
- 2026-10-17T17:30:45Z edit tests/test_runtime_detection.py
- 2026-10-17T17:30:47Z edit tests/test_session_create.py (x3)
- 2026-10-17T17:31:01Z edit scripts/alongkit/closeout.py (x3)
- 2026-10-17T17:31:02Z edit scripts/alongkit/gates.py
- 2026-10-17T17:31:03Z edit scripts/alongkit/lifecycle.py (x2)
- 2026-10-17T17:31:03Z edit scripts/alongkit/entities/mutation.py
- 2026-10-17T17:31:04Z edit scripts/alongkit/testruns.py
- 2026-10-17T17:31:05Z edit scripts/alongkit/verify.py
- 2026-10-17T17:31:06Z edit scripts/alongkit/hooks/predicates.py (x2)
- 2026-10-17T17:31:20Z edit scripts/alongkit/gitgates.py (x5)
- 2026-10-17T17:31:26Z edit scripts/alongkit/merge.py (x4)
- 2026-10-17T17:31:47Z edit scripts/alongkit/proc.py (x5)
- 2026-10-17T17:32:37Z edit scripts/alongkit/commands/ops.py (x4)
- 2026-10-17T17:32:39Z edit scripts/alongkit/commands/__init__.py (x3)
- 2026-10-17T17:32:42Z edit scripts/along_exec.py (x6)
- 2026-10-17T17:32:51Z edit scripts/alongkit/commands/doctor.py (x2)
- 2026-10-17T17:32:53Z edit scripts/alongkit/__init__.py (x2)
- 2026-10-17T17:33:01Z edit scripts/alongkit/hooks/declarative.py
- 2026-10-17T17:33:32Z edit scripts/alongkit/hooks/predicates.py (x5)
- 2026-10-17T17:33:59Z edit scripts/alongkit/hooks/turnstate.py
- 2026-10-17T17:34:36Z edit scripts/alongkit/hooks/predicates.py (x2)
- 2026-10-17T17:34:57Z edit scripts/alongkit/hooks/declarative.py (x5)
- 2026-10-17T17:35:14Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-17T17:35:15Z edit scripts/alongkit/hooks/default_gates.yaml (x2)
- 2026-10-17T17:35:16Z edit scripts/alongkit/hooks/config.py
- 2026-10-17T17:35:49Z edit scripts/alongkit/session.py
- 2026-10-17T17:35:52Z edit scripts/alongkit/commands/lifecycle.py (x4)
- 2026-10-17T17:35:58Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-17T17:36:18Z edit scripts/alongkit/hooks/shellparse.py
- 2026-10-17T17:36:23Z denied [require_plan_approval] run_command: Destructive Action [gate: require-plan-approval]: Tool or command 'python -m compileall -q scripts tests >/dev/null && echo COMPILED; python -m pyflakes --ve...
- 2026-10-17T17:36:28Z denied [require_plan_approval] run_command: Unclassified Tool Nature [gate: require-plan-approval]: Tool or command 'sort' has unclassified nature. Ask the user for its nature (read-only, verification,...
- 2026-10-17T17:42:51Z edit tests/test_shell_classification.py (x6)
- 2026-10-17T17:43:21Z edit tests/test_declarative_gates.py (x3)
- 2026-10-17T17:44:10Z edit tests/test_hook_activation.py (x6)
- 2026-10-17T17:44:34Z edit tests/test_hooks_audit_scrubbing.py (x3)
- 2026-10-17T17:45:06Z edit tests/test_session_bindings.py (x3)
- 2026-10-17T17:45:15Z edit tests/test_update_maintenance_friction.py (x3)
- 2026-10-17T17:45:16Z edit tests/test_lifecycle_wrap.py
- 2026-10-17T17:45:31Z edit tests/test_rule_pack_protection.py
- 2026-10-17T17:45:32Z edit tests/test_hooks_tool_coverage.py
- 2026-10-17T17:45:36Z edit tests/test_subcommand_help.py
- 2026-10-17T17:45:43Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-17T17:45:48Z edit tests/test_error_handling_and_io.py
- 2026-10-17T17:46:00Z edit tests/test_parallel_closeout.py
- 2026-10-17T17:46:01Z edit tests/test_inquiry_gate.py
- 2026-10-17T17:46:32Z edit skills/along-init/protocol.md (x7)
- 2026-10-17T17:46:48Z edit AGENTS.md (x7)
- 2026-10-17T17:46:59Z edit skills/along-kb-search/SKILL.md
- 2026-10-17T17:49:41Z edit scripts/alongkit/hooks/deletion.py (x3)
- 2026-10-17T17:49:50Z edit scripts/alongkit/hooks/containment.py
- 2026-10-17T17:49:51Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-17T17:50:06Z edit scripts/alongkit/hooks/default_gates.yaml
- 2026-10-17T17:50:07Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-17T17:50:07Z edit scripts/alongkit/hooks/config.py
- 2026-10-17T17:50:34Z edit scripts/alongkit/hooks/default_gates.yaml (x3)
- 2026-10-17T17:50:35Z edit scripts/alongkit/hooks/predicates.py (x2)
- 2026-10-17T17:50:44Z edit scripts/alongkit/hooks/engine.py (x2)
- 2026-10-17T17:51:00Z edit scripts/alongkit/commands/gates.py
- 2026-10-17T17:51:01Z edit scripts/alongkit/commands/__init__.py (x2)
- 2026-10-17T17:51:03Z edit scripts/along_exec.py (x3)
- 2026-10-17T17:51:15Z edit scripts/alongkit/hooks/config.py (x2)
- 2026-10-17T17:51:36Z edit scripts/alongkit/gatestats.py (x2)
- 2026-10-17T17:51:37Z edit scripts/alongkit/commands/gates.py (x2)
- 2026-10-17T17:52:11Z edit tests/test_destructive_command.py (x3)
- 2026-10-17T17:52:21Z edit scripts/alongkit/hooks/deletion.py
- 2026-10-17T17:52:41Z edit tests/test_hooks_audit_scrubbing.py
- 2026-10-17T17:52:49Z edit scripts/alongkit/hooks/config.py (x2)
- 2026-10-17T17:52:52Z edit tests/test_hooks_audit_scrubbing.py
- 2026-10-17T17:54:00Z denied [cli_safety] run_command: CLI Safety Gate Violation: Destructive unstaged Git wipe (git reset --hard) detected in command: along decision create gates-judge-results-not-commands --tit...
- 2026-10-17T17:54:11Z edit docs/topic--runtime-hooks-and-gates.md (x4)
- 2026-10-17T17:54:12Z edit .along/DECISIONS/ADR-2026-10-17--gates-judge-results-not-commands.md
- 2026-10-17T17:54:22Z edit docs/topic--runtime-hooks-and-gates.md (x2)
- 2026-10-17T17:54:39Z edit .along/ISSUES/debt--gate-config-layers.md
- 2026-10-17T17:54:40Z edit .along/ISSUES/task--gate-event-remeasure.md
- 2026-10-17T17:54:42Z edit docs/topic--runtime-hooks-and-gates.md (x3)
- 2026-10-17T17:55:08Z edit .along/ISSUES/debt--gate-simplification.md
- 2026-10-17T17:55:24Z edit docs/topic--runtime-hooks-and-gates.md (x7)
- 2026-10-17T17:55:24Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-17T17:55:25Z edit tests/test_shell_classification.py
- 2026-10-17T17:56:14Z edit docs/topic--runtime-hooks-and-gates.md (x11)
- 2026-10-17T17:57:09Z edit docs/topic--declarative-gates-and-traceability.md (x11)
- 2026-10-17T17:57:42Z edit docs/topic--cli-reference.md (x7)
- 2026-10-17T17:57:58Z edit docs/topic--troubleshooting.md (x3)
- 2026-10-17T17:58:06Z edit docs/topic--skills-reference.md
- 2026-10-17T17:58:17Z edit docs/topic--agent-run-protocol.md (x3)
- 2026-10-17T17:58:21Z denied [fast_retrieval] grep_search: Manual Search Rejected [gate: fast-retrieval]: Manual directory search across 'D:\Src\my\actdim\public\along\docs' is forbidden to prevent latency and LLM to...
- 2026-10-17T17:58:30Z edit docs/topic--cli-reference.md
- 2026-10-17T17:58:34Z edit docs/topic--migrations.md
- 2026-10-17T18:00:43Z edit tests/test_ai_coauthor_attribution.py
- 2026-10-17T18:00:43Z edit tests/test_cli_safety_patterns.py
- 2026-10-17T18:00:44Z edit tests/test_git_gate_enforcement.py
- 2026-10-17T18:00:45Z edit tests/test_repo_state_gates.py
- 2026-10-17T18:00:46Z edit tests/test_workspace_containment.py
- 2026-10-17T18:00:47Z edit tests/test_destructive_command.py (x2)
- 2026-10-17T18:00:56Z edit tests/test_shell_classification.py (x2)
- 2026-10-17T18:01:21Z edit tests/test_hooks_claude.py
- 2026-10-17T18:01:40Z edit tests/test_hooks_codex.py
- 2026-10-17T18:02:22Z edit tests/test_hooks_core.py (x5)
- 2026-10-17T18:02:22Z edit tests/test_hooks_generic.py
- 2026-10-17T18:02:29Z edit tests/test_hook_activation.py
- 2026-10-17T18:07:42Z step 1: in-progress -> passed
- 2026-10-17T18:29:47Z test FAIL (Wrap Quality Gate)
- 2026-10-17T18:29:55Z bypass [tests] (verified): Pre-existing failure test_live_repo_projection_size_budget (DECISIONS.md over 8 KB before this change; tracked by debt--constraints-superseded-adr-filtering); user approved the bypass

### Review step-1

#### Review: step 1 (gate simplification, all plan phases)

Verdict: pass, with one open item outside this issue.

##### Checked
- Plan steps 1-6 implemented: classifier, circuit breaker, fast_retrieval and confirmations
  removed; require_plan_approval by path (file tools) and by turn result at Stop (turnstate);
  destructive_command (deletion.py); content gates commit-time only plus `along lint`;
  audit `target` and `warn`; `along gates stats` loops; docs, ADR, follow-up issues.
- Blast radius: every importer of toolnature, circuit, removed shellparse functions and
  trip_on_anomaly updated (grep clean); `alongkit.__init__`, commands, along_exec routers.
- Tests: full suite 1405 run, 1 failure: test_live_repo_projection_size_budget
  (.along/DECISIONS.md 8421 B > 8192 B). Pre-existing before this change (8320 B at the
  baseline run); tracked by debt--constraints-superseded-adr-filtering.
- New hermetic tests: test_shell_classification (shell never held up front, Stop attribution,
  baseline, state/projection exemptions, stop_hook_active), test_destructive_command (form
  matrix, inside/outside/untracked/empty variable/substitution/temp, git reset/clean/push,
  ASK vs DENY), audit target/warn/loops.
- Typography: `along sanitize --check` clean (996 files).

##### Notes
- The globally installed hook (~/.along/bin) still runs the old gates until `along update`
  reinstalls it; this session's false positives (python scripts, quoted "git reset --hard",
  grep over docs/) were the old code.
- docs/topic--system-comparisons.md (write_policy: manual) still names CircuitBreaker; needs a
  docs-- issue.
