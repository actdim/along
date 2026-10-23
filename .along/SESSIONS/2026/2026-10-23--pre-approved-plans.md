---
protocol: along
protocol_version: "4.5.2"
date: 2026-10-23
slug: pre-approved-plans
agent: claude-code
branch: main
commit: 7addeaf
summary: Issue plans live in .along/ISSUES/<key>/plan.md and can be approved ahead of along start; plan_status approved is set only by along plan approve (machine-local approval log, file-tool guard, Stop check); along plan revise/rework; the orchestrator runs an approved plan instead of its architect.
issues_advanced: []
issues_completed: [feat--pre-approved-plans]
decisions: [ADR-2026-10-23--issue-plans-approved-ahead]
files: [.along/ISSUES/feat--pre-approved-plans.md, .along/ISSUES/feat--pre-approved-plans/plan.md, docs/topic--cli-reference.md, docs/topic--domain-model.md, docs/topic--runtime-hooks-and-gates.md, scripts/along_commit.py, scripts/along_exec.py, scripts/alongkit/closeout.py, scripts/alongkit/commands/issue.py, scripts/alongkit/commands/lifecycle.py, scripts/alongkit/commands/scratch.py, scripts/alongkit/daemon.py, scripts/alongkit/entities/__init__.py, scripts/alongkit/entities/mutation.py, scripts/alongkit/entities/projections.py, scripts/alongkit/entities/query.py, scripts/alongkit/entities/vocabulary.py, scripts/alongkit/handoff.py, scripts/alongkit/hooks/predicates.py, scripts/alongkit/lifecycle.py, scripts/alongkit/orchestrator.py, scripts/alongkit/session.py, skills/along-init/protocol-reference.md, skills/along-team/SKILL.md, tests/test_issue_plans.py]
---

# Session: Pre approved plans

## Summary
Issue plans live in .along/ISSUES/<key>/plan.md and can be approved ahead of along start; plan_status approved is set only by along plan approve (machine-local approval log, file-tool guard, Stop check); along plan revise/rework; the orchestrator runs an approved plan instead of its architect.

## Decisions
- [ADR-2026-10-23--issue-plans-approved-ahead]

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Disclosed Gate Denials

- d-0f10c0 [doc_manual_lock] D:\Src\my\actdim\public\along\docs\topic--along-protocol.md (acknowledged): Direct Edit of docs/topic--along-protocol.md denied by doc-manual-lock. Not retried by hand: the file is the rendered copy of skills/along-init/protocol-reference.md, so the template was edited and the doc regenerated with 'along init' (only that doc changed; diff = the new section).

Plan: kept with the issue (`plan/plan.md`, 2 revision(s)).

### Execution Trace

#### Execution Trace: pre-approved-plans
- 2026-10-23T15:59:05Z phase: planning -> execution
- 2026-10-23T15:59:05Z plan approved (ExitPlanMode) approved_via: exit-plan-mode
- 2026-10-23T16:01:46Z edit tests/test_issue_plans.py
- 2026-10-23T16:03:16Z edit scripts/alongkit/session.py (x4)
- 2026-10-23T16:03:37Z edit scripts/alongkit/entities/mutation.py (x4)
- 2026-10-23T16:03:50Z edit scripts/alongkit/entities/__init__.py (x2)
- 2026-10-23T16:03:51Z edit scripts/alongkit/commands/issue.py (x2)
- 2026-10-23T16:03:52Z edit scripts/alongkit/lifecycle.py
- 2026-10-23T16:04:05Z edit scripts/alongkit/entities/projections.py (x2)
- 2026-10-23T16:04:42Z edit scripts/alongkit/session.py
- 2026-10-23T16:04:49Z edit scripts/alongkit/commands/lifecycle.py (x3)
- 2026-10-23T16:04:55Z edit scripts/alongkit/commands/scratch.py
- 2026-10-23T16:05:31Z edit scripts/alongkit/commands/lifecycle.py (x4)
- 2026-10-23T16:06:26Z edit scripts/alongkit/hooks/predicates.py (x10)
- 2026-10-23T16:07:01Z edit scripts/alongkit/handoff.py (x2)
- 2026-10-23T16:07:34Z edit scripts/alongkit/orchestrator.py (x4)
- 2026-10-23T16:07:35Z edit scripts/alongkit/daemon.py
- 2026-10-23T16:07:35Z edit tests/test_issue_plans.py
- 2026-10-23T16:16:12Z edit scripts/alongkit/entities/vocabulary.py
- 2026-10-23T16:16:13Z edit scripts/alongkit/entities/__init__.py (x2)
- 2026-10-23T16:16:14Z edit scripts/along_commit.py
- 2026-10-23T16:16:32Z edit scripts/alongkit/entities/mutation.py (x2)
- 2026-10-23T16:16:33Z edit scripts/alongkit/entities/query.py (x2)
- 2026-10-23T16:16:35Z edit scripts/alongkit/entities/mutation.py (x2)
- 2026-10-23T16:16:35Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-23T16:16:52Z edit scripts/alongkit/closeout.py (x3)
- 2026-10-23T16:18:01Z edit scripts/alongkit/session.py
- 2026-10-23T16:19:02Z edit skills/along-init/protocol-reference.md
- 2026-10-23T16:19:03Z denied [doc_manual_lock] replace_file_content: Manual Document Lock Violation [gate: doc-manual-lock]: Document 'docs/topic--along-protocol.md' is governed by 'write_policy: manual'. Automated modificatio...
- 2026-10-23T16:20:01Z edit docs/topic--domain-model.md (x2)
- 2026-10-23T16:20:18Z edit skills/along-team/SKILL.md (x3)
- 2026-10-23T16:20:28Z edit scripts/along_exec.py
- 2026-10-23T16:20:42Z edit docs/topic--cli-reference.md (x3)
- 2026-10-23T16:21:27Z edit .along/ISSUES/feat--pre-approved-plans.md
- 2026-10-23T16:21:51Z edit docs/topic--runtime-hooks-and-gates.md (x2)
- 2026-10-23T16:22:45Z edit .along/ISSUES/feat--pre-approved-plans/plan.md
- 2026-10-23T16:22:59Z denied [test_before_stop] : Turn Completion Rejected [gate: test-before-stop]: Source files were modified in this session, but automated tests have not been executed afterward. Run test...
- 2026-10-23T16:29:12Z edit .along/ISSUES/feat--pre-approved-plans.md
- 2026-10-23T16:29:24Z acknowledged denial d-0f10c0 [doc_manual_lock]: Direct Edit of docs/topic--along-protocol.md denied by doc-manual-lock. Not retried by hand: the file is the rendered copy of skills/along-init/protocol-reference.md, so the template was edited and the doc regenerated with 'along init' (only that doc changed; diff = the new section).
