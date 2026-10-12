---
protocol: along
protocol_version: "4.4.11"
date: 2026-10-12
slug: tool-nature-classification
agent: antigravity
branch: main
commit: ef2fafd
summary: Classify tools by nature with versioned layered rules
milestone: v4.5.0-multi-user-merge-automation
issues_advanced: []
issues_completed: [feat--tool-nature-classification]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Tool nature classification

## Summary
Classify tools by nature with versioned layered rules

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/feat--tool-nature-classification.md` | state | 1 | 2026-10-12T03:04:01Z | antigravity--7acd53c4-5bf0-420c-aeb2-c02315ddb768 |
| `docs/topic--cli-reference.md` | docs | 1 | 2026-10-12T03:01:59Z | antigravity--7acd53c4-5bf0-420c-aeb2-c02315ddb768 |
| `docs/topic--runtime-hooks-and-gates.md` | docs | 2 | 2026-10-12T03:03:28Z | antigravity--7acd53c4-5bf0-420c-aeb2-c02315ddb768 |
| `scripts/along_exec.py` | source | 4 | 2026-10-12T02:58:59Z | antigravity--7acd53c4-5bf0-420c-aeb2-c02315ddb768 |
| `scripts/alongkit/hooks/default_gates.yaml` | source | 1 | 2026-10-12T02:56:09Z | antigravity--7acd53c4-5bf0-420c-aeb2-c02315ddb768 |
| `scripts/alongkit/hooks/predicates.py` | source | 3 | 2026-10-12T03:11:59Z | antigravity--7acd53c4-5bf0-420c-aeb2-c02315ddb768 |
| `scripts/alongkit/hooks/toolnature.py` | source | 9 | 2026-10-12T03:11:45Z | antigravity--7acd53c4-5bf0-420c-aeb2-c02315ddb768 |
| `tests/test_tool_nature.py` | source | 2 | 2026-10-12T03:00:40Z | antigravity--7acd53c4-5bf0-420c-aeb2-c02315ddb768 |

### Plan

#### Living Plan: tool-nature-classification

Title: Tool nature classification: unified rule model, layered resolution, and gate integration

##### Objectives
Implement five operational natures (read-only, verification, workspace-write, external, destructive) plus unknown for agent and shell tools with unified declarative match conditions, code classifiers, versioned layered resolution, and mechanical gate enforcement.

##### Steps
- [x] Step 1: Design and implement core classification engine (`alongkit.hooks.toolnature`) with call normalization, danger hierarchy, built-in rules, and code classifiers.
- [x] Step 2: Implement layered configuration resolution (repository -> global user pack -> rule packs -> built-in defaults) and CLI operations (`along tool classify`, `list`, `explain`).
- [x] Step 3: Integrate tool nature classification into `predicates.check_mutation_authorization` and update gate definitions in `default_gates.yaml`.
- [x] Step 4: Add comprehensive unit tests in `tests/test_tool_nature.py` verifying all classes, compound commands, layered overrides, and gate holds.
- [x] Step 5: Update documentation in `docs/topic--runtime-hooks-and-gates.md` and `docs/topic--cli-reference.md`.
- [x] Step 6: Verify full test suite and clean ASCII typography.

### Execution Trace

#### Execution Trace: tool-nature-classification
- 2026-10-12T02:44:03Z plan approved (along start --approved; approved_via: cli-unverified)
- 2026-10-12T02:54:38Z edit scripts/alongkit/hooks/toolnature.py
- 2026-10-12T02:55:57Z edit scripts/alongkit/hooks/predicates.py (x2)
- 2026-10-12T02:56:09Z edit scripts/alongkit/hooks/default_gates.yaml
- 2026-10-12T02:56:59Z denied [cli_safety] run_command: CLI Safety Gate Violation: Ad-hoc internal module probe via python -c [gate: cli_safety] (use Along CLI, code search tools, or a scratch/ script) detected in...
- 2026-10-12T02:57:27Z edit scripts/alongkit/hooks/toolnature.py
- 2026-10-12T02:58:59Z edit scripts/along_exec.py (x4)
- 2026-10-12T02:59:28Z edit scripts/alongkit/hooks/toolnature.py
- 2026-10-12T03:00:09Z edit tests/test_tool_nature.py
- 2026-10-12T03:00:36Z edit scripts/alongkit/hooks/toolnature.py (x2)
- 2026-10-12T03:00:40Z edit tests/test_tool_nature.py
- 2026-10-12T03:01:59Z edit docs/topic--cli-reference.md
- 2026-10-12T03:03:28Z edit docs/topic--runtime-hooks-and-gates.md (x2)
- 2026-10-12T03:04:01Z edit .along/ISSUES/feat--tool-nature-classification.md
- 2026-10-12T03:11:45Z edit scripts/alongkit/hooks/toolnature.py (x4)
- 2026-10-12T03:11:59Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-12T03:16:42Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: 13a5a31f9ed4
