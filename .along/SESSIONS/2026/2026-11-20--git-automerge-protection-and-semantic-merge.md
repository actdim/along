---
protocol: along
protocol_version: "4.9.0"
date: 2026-11-20
slug: git-automerge-protection-and-semantic-merge
agent: antigravity
branch: main
commit: 118ca3a
summary: Preventive Git auto-merge protection, update propagation and stage-aware conflict resolution
milestone: v5.0.0-agent-run-protocol-and-observability
issues_advanced: []
issues_completed: [feat--git-automerge-protection-and-semantic-merge]
decisions: [drivers-bound-per-clone-merge-protection-committed]
files: [.along/ISSUES/feat--git-automerge-protection-and-semantic-merge.md, README.md, docs/topic--cli-reference.md, docs/topic--runtime-hooks-and-gates.md, scripts/along_init.py, scripts/along_resolve.py, scripts/along_update.py, scripts/alongkit/commands/doctor.py, scripts/alongkit/commands/gates.py, scripts/alongkit/merge.py, scripts/alongkit/resolve.py, skills/along-init/protocol-reference.md, skills/along-update/SKILL.md, tests/test_merge_driver.py]
---

# Session: Git automerge protection and semantic merge

## Summary
Preventive Git auto-merge protection, update propagation and stage-aware conflict resolution

## Decisions
- [drivers-bound-per-clone-merge-protection-committed]

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Disclosed Gate Denials

- d-c67f75 [require_plan_approval] python -c " with open('.along/.session/git-automerge-protection-and-semantic-merge/events.jsonl', encoding='utf-8') as f: for line in f: print(line.strip()[:100]) " (acknowledged): Switched to standard read_file tool instead of python -c

Plan: kept with the issue (`plan/plan.md`, 1 revision(s)).

### Execution Trace

#### Execution Trace: git-automerge-protection-and-semantic-merge
- 2026-11-14T20:01:52Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: 74af59d520cb
- 2026-11-15T13:06:02Z plan approved (approved issue plan; approved_via: issue-plan)
- 2026-11-15T13:07:19Z plan recorded: revision 2 (along plan revise): Rev 1 relied on -merge fallback that git does not perform for undefined drivers, and would have overridden HISTORY.md merge=union; drivers move to .git/info/attributes, REQ-4 and entity coverage added.
- 2026-11-15T13:08:09Z edit scripts/alongkit/merge.py (x7)
- 2026-11-15T13:08:25Z edit scripts/along_update.py
- 2026-11-15T13:08:36Z edit scripts/along_init.py (x3)
- 2026-11-15T13:08:50Z edit scripts/alongkit/commands/doctor.py (x2)
- 2026-11-15T13:08:52Z edit scripts/alongkit/commands/gates.py (x3)
- 2026-11-15T13:09:13Z edit scripts/alongkit/resolve.py
- 2026-11-15T13:09:25Z edit scripts/along_resolve.py (x2)
- 2026-11-15T13:09:47Z edit scripts/alongkit/resolve.py
- 2026-11-15T13:09:48Z edit scripts/along_resolve.py
- 2026-11-15T13:10:00Z edit scripts/alongkit/commands/gates.py (x3)
- 2026-11-15T13:10:45Z edit tests/test_merge_driver.py (x2)
- 2026-11-15T13:21:21Z edit docs/topic--cli-reference.md (x4)
- 2026-11-15T13:21:33Z edit docs/topic--runtime-hooks-and-gates.md (x2)
- 2026-11-15T13:21:33Z edit README.md
- 2026-11-15T13:21:34Z edit skills/along-init/protocol-reference.md
- 2026-11-15T13:21:44Z edit skills/along-update/SKILL.md
- 2026-11-15T13:22:26Z edit .along/ISSUES/feat--git-automerge-protection-and-semantic-merge.md
- 2026-11-15T13:32:46Z stop: 1 path(s) changed this turn outside this session's tool calls were not counted
- 2026-11-20T22:16:07Z plan approved (approved issue plan; approved_via: issue-plan)
- 2026-11-20T22:21:59Z denied [require_plan_approval] run_command: PLAN_REQUIRED [gate: require-plan-approval]: '
- 2026-11-20T22:22:40Z acknowledged denial d-c67f75 [require_plan_approval]: Switched to standard read_file tool instead of python -c
