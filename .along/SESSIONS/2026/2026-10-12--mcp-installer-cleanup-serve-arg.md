---
protocol: along
protocol_version: "4.4.10"
date: 2026-10-12
slug: mcp-installer-cleanup-serve-arg
agent: antigravity
branch: main
commit: 7ff7242
summary: Completed bug--mcp-installer-cleanup-serve-arg
issues_advanced: []
issues_completed: [bug--mcp-installer-cleanup-serve-arg]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Mcp installer cleanup serve arg

## Summary
Completed bug--mcp-installer-cleanup-serve-arg

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/ISSUES/bug--mcp-installer-cleanup-serve-arg.md` | state | 2 | 2026-10-12T00:16:01Z | antigravity--39f84277-0acb-4b0e-9418-0ae5322ac93b |
| `install.ps1` | source | 4 | 2026-10-12T00:14:12Z | antigravity--39f84277-0acb-4b0e-9418-0ae5322ac93b |
| `install.sh` | source | 4 | 2026-10-12T00:14:43Z | antigravity--39f84277-0acb-4b0e-9418-0ae5322ac93b |

### Plan

#### Living Plan: mcp-installer-cleanup-serve-arg

Title: Purge default MCP auto-registration from installers

##### Execution Mode: Direct

##### Steps
- [x] Step 1: Update install.ps1 to invoke configure_mcp.py with --clean by default and clean up stale code-review-graph entries
- [x] Step 2: Update install.sh to invoke configure_mcp.py with --clean by default, maintaining cross-platform parity
- [x] Step 3: Verify installer tests and regression test suite
- [ ] Step 4: Reconcile issue and session records

### Execution Trace

#### Execution Trace: mcp-installer-cleanup-serve-arg
- 2026-10-12T00:12:48Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: b74e05d72ff0
- 2026-10-12T00:13:00Z edit .along/ISSUES/bug--mcp-installer-cleanup-serve-arg.md
- 2026-10-12T00:14:12Z edit install.ps1 (x4)
- 2026-10-12T00:14:43Z edit install.sh (x4)
- 2026-10-12T00:16:01Z edit .along/ISSUES/bug--mcp-installer-cleanup-serve-arg.md
- 2026-10-12T00:16:16Z archived by issue done
