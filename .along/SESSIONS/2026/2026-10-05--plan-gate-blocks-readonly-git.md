---
protocol: along
protocol_version: "4.4.5"
date: 2026-10-05
slug: plan-gate-blocks-readonly-git
agent: claude-code
branch: main
commit: b7d1379
summary: Wrapped bug--plan-gate-blocks-readonly-git
milestone: v4.5.0-multi-user-merge-automation
issues_advanced: []
issues_completed: [bug--plan-gate-blocks-readonly-git]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Plan gate blocks readonly git

## Summary
The plan gate held `git tag -l` and `git ls-remote` in the inquiry phase, so "is the v4.4.5
tag pushed?" could not be answered. The read-only classifier (`alongkit/hooks/shellparse.py`)
now accepts pure-read git subcommands and the listing forms of `branch`, `tag`, `remote`,
`stash`, `config`, `reflog`, `worktree` and `notes`; git words are classified in their original
case so `-C <dir>` passes while `-c` (pager/alias injection) stays held. 38 read and 29 write
cases added to `tests/test_shell_classification.py`; hooks doc updated.

Same session: found `v4.4.5` local but not on `origin`, pushed it by hand, filed
`bug--release-tags-not-pushed` (open, v4.5.0).

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

| Step | Title | Status | Retries | Review |
| --- | --- | --- | --- | --- |
| 1 | Step 1 | pending | 0 | no |

### Plan

#### Living Plan: plan-gate-blocks-readonly-git

Title: Plan gate blocks readonly git

##### Steps
- [ ] Step 1: Step 1

### Research

#### Research & Findings: plan-gate-blocks-readonly-git

##### Target Symbols and Files

##### Constraints & Risks

##### Architectural Patterns
