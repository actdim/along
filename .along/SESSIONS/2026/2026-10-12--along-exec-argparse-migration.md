---
protocol: along
protocol_version: "4.4.11"
date: 2026-10-12
slug: along-exec-argparse-migration
agent: antigravity
branch: main
commit: 9bd8592
summary: Migrate hand-rolled CLI parsing in along_exec to modular argparse subparsers
milestone: v4.5.0-multi-user-merge-automation
issues_advanced: []
issues_completed: [debt--along-exec-argparse-migration]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Along exec argparse migration

## Summary
Migrate hand-rolled CLI parsing in along_exec to modular argparse subparsers

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `scripts/alongkit/commands/__init__.py` | source | 1 | 2026-10-12T08:23:55Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/alongkit/commands/common.py` | source | 1 | 2026-10-12T08:24:16Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/alongkit/commands/decision.py` | source | 1 | 2026-10-12T08:24:35Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |
| `scripts/alongkit/commands/milestone.py` | source | 1 | 2026-10-12T08:25:08Z | antigravity--568a4191-e5cf-4667-8d6d-138c497344d7 |

### Plan

#### Living Plan: along-exec-argparse-migration

Title: Migrate hand-rolled CLI parsing in along_exec to modular argparse subparsers

##### Steps
- [x] Step 1: Implement alongkit.commands.common with execution guard, require_entity_name, check_unknown_args, and flag_value
- [x] Step 2: Implement modular command modules (decision.py, milestone.py, scratch.py, worktree.py, session.py, issue.py) with allow_abbrev=False
- [x] Step 3: Wire along_exec.py router to modular commands and remove redundant hand-rolled parsing logic
- [x] Step 4: Add test_cli_argparse.py testing misspelled flags exit 2, module execution guards, documented commands in CLI reference and skills
- [x] Step 5: Verify all test suites, typography hygiene, and session wrap

### Execution Trace

#### Execution Trace: along-exec-argparse-migration
- 2026-10-12T08:23:49Z plan approved (along start --approved; approved_via: cli-unverified)
- 2026-10-12T08:23:55Z edit scripts/alongkit/commands/__init__.py
- 2026-10-12T08:24:16Z edit scripts/alongkit/commands/common.py
- 2026-10-12T08:24:35Z edit scripts/alongkit/commands/decision.py
- 2026-10-12T08:25:08Z edit scripts/alongkit/commands/milestone.py
