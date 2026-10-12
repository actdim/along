---
protocol: along
protocol_version: "4.4.11"
date: 2026-10-12
slug: uncommitted-issue-deleted-without-trace
agent: antigravity
branch: main
commit: ec9d180
summary: Prevent uncommitted entity file deletion and support multi-issue supersede
milestone: v4.5.0-multi-user-merge-automation
issues_advanced: []
issues_completed: [bug--uncommitted-issue-deleted-without-trace]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Uncommitted issue deleted without trace

## Summary
Prevent uncommitted entity file deletion and support multi-issue supersede

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/bug--uncommitted-issue-deleted-without-trace.md` | state | 2 | 2026-10-12T01:42:53Z | antigravity--d15f9b02-a010-4db6-be02-f5486e920f2d |
| `scripts/along_exec.py` | source | 1 | 2026-10-12T01:35:49Z | antigravity--d15f9b02-a010-4db6-be02-f5486e920f2d |
| `scripts/alongkit/entities.py` | source | 3 | 2026-10-12T01:35:36Z | antigravity--d15f9b02-a010-4db6-be02-f5486e920f2d |
| `scripts/alongkit/hooks/adapters/codex.py` | source | 1 | 2026-10-12T01:32:53Z | antigravity--d15f9b02-a010-4db6-be02-f5486e920f2d |
| `scripts/alongkit/hooks/adapters/generic.py` | source | 1 | 2026-10-12T01:32:46Z | antigravity--d15f9b02-a010-4db6-be02-f5486e920f2d |
| `scripts/alongkit/hooks/adapters/normalize.py` | source | 1 | 2026-10-12T01:32:38Z | antigravity--d15f9b02-a010-4db6-be02-f5486e920f2d |
| `scripts/alongkit/hooks/default_gates.yaml` | source | 2 | 2026-10-12T01:34:01Z | antigravity--d15f9b02-a010-4db6-be02-f5486e920f2d |
| `scripts/alongkit/hooks/predicates.py` | source | 2 | 2026-10-12T01:41:21Z | antigravity--d15f9b02-a010-4db6-be02-f5486e920f2d |
| `scripts/alongkit/lifecycle.py` | source | 1 | 2026-10-12T01:36:11Z | antigravity--d15f9b02-a010-4db6-be02-f5486e920f2d |
| `tests/test_declarative_gates.py` | source | 2 | 2026-10-12T01:40:57Z | antigravity--d15f9b02-a010-4db6-be02-f5486e920f2d |
| `tests/test_entity_reference_integrity.py` | source | 1 | 2026-10-12T01:41:44Z | antigravity--d15f9b02-a010-4db6-be02-f5486e920f2d |
| `tests/test_session_records.py` | source | 1 | 2026-10-12T01:42:13Z | antigravity--d15f9b02-a010-4db6-be02-f5486e920f2d |

### Plan

#### Living Plan: uncommitted-issue-deleted-without-trace

Title: Uncommitted issue deleted without trace

##### Requirements
- REQ-1: Deleting an issue / ADR / milestone / risk / spike file (tracked or not) through the agent's tools is rejected; the remediation names along issue supersede / along issue rename (split: supersede into several keys).
- REQ-2: along issue supersede <slug> --by a,b,c supports a split into several issues.
- REQ-3: A blackboard whose issue file is missing is reported with the last trace entry that touched the file (along doctor).

##### Steps
- [x] Step 1: Implement check_entity_deletion_protection predicate and register PreToolUse entity_reference_integrity gate in default_gates.yaml.
- [x] Step 2: Implement multi-issue supersede support in entities.py and along_exec.py CLI, updating validate_entities and rewrite_inbound_references.
- [x] Step 3: Implement last_issue_trace_entry and update orphan_blackboards in lifecycle.py.
- [x] Step 4: Add hermetic unit and CLI tests in test_declarative_gates.py, test_entity_reference_integrity.py, and test_session_records.py.
- [x] Step 5: Verify all automated tests pass and wrap the session.

### Execution Trace

#### Execution Trace: uncommitted-issue-deleted-without-trace
- 2026-10-12T01:23:02Z plan approved (along start --approved; approved_via: cli-unverified)
- 2026-10-12T01:32:38Z edit scripts/alongkit/hooks/adapters/normalize.py
- 2026-10-12T01:32:46Z edit scripts/alongkit/hooks/adapters/generic.py
- 2026-10-12T01:32:53Z edit scripts/alongkit/hooks/adapters/codex.py
- 2026-10-12T01:33:41Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-12T01:34:01Z edit scripts/alongkit/hooks/default_gates.yaml (x2)
- 2026-10-12T01:35:36Z edit scripts/alongkit/entities.py (x3)
- 2026-10-12T01:35:49Z edit scripts/along_exec.py
- 2026-10-12T01:36:11Z edit scripts/alongkit/lifecycle.py
- 2026-10-12T01:40:57Z edit tests/test_declarative_gates.py (x2)
- 2026-10-12T01:41:21Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-12T01:41:44Z edit tests/test_entity_reference_integrity.py
- 2026-10-12T01:42:13Z edit tests/test_session_records.py
- 2026-10-12T01:42:53Z edit .along/ISSUES/bug--uncommitted-issue-deleted-without-trace.md (x2)
- 2026-10-12T01:43:42Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: 132618b8342f
- 2026-10-12T01:47:16Z test pass (Wrap Quality Gate)
