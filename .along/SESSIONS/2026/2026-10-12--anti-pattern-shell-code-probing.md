---
protocol: along
protocol_version: "4.4.11"
date: 2026-10-12
slug: anti-pattern-shell-code-probing
agent: antigravity
branch: main
commit: 6560c18
summary: Document anti-pattern shell code probing in AGENTS.md, along-team skill, and troubleshooting topic
milestone: v4.5.0-multi-user-merge-automation
issues_advanced: []
issues_completed: [docs--anti-pattern-shell-code-probing]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Anti pattern shell code probing

## Summary
Document anti-pattern shell code probing in AGENTS.md, along-team skill, and troubleshooting topic

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `AGENTS.md` | docs | 1 | 2026-10-12T09:37:24Z | antigravity--cf6fed8f-0098-49a3-b801-81486fd90d33 |
| `docs/topic--troubleshooting.md` | docs | 1 | 2026-10-12T09:38:31Z | antigravity--cf6fed8f-0098-49a3-b801-81486fd90d33 |
| `skills/along-init/protocol.md` | source | 1 | 2026-10-12T09:37:15Z | antigravity--cf6fed8f-0098-49a3-b801-81486fd90d33 |
| `skills/along-team/SKILL.md` | source | 2 | 2026-10-12T09:38:10Z | antigravity--cf6fed8f-0098-49a3-b801-81486fd90d33 |
| `tests/test_docs.py` | source | 1 | 2026-10-12T09:38:56Z | antigravity--cf6fed8f-0098-49a3-b801-81486fd90d33 |

### Plan

#### Living Plan: anti-pattern-shell-code-probing

##### Problem Statement
Document prohibition of ad-hoc python -c shell code probing across AGENTS.md, along-team skill, and docs/topic--troubleshooting.md.

##### Execution Mode
Direct

##### Steps
- [x] Step 1: Add protocol rule in AGENTS.md and skills/along-init/protocol.md prohibiting python -c symbol probing.
- [x] Step 2: Document anti-pattern prohibition in skills/along-team/SKILL.md.
- [x] Step 3: Author docs/topic--troubleshooting.md explaining packaging architecture and API discovery workflows.
- [x] Step 4: Recompile Knowledge Base and index in docs/INDEX.md via along_kb_sync.py.
- [x] Step 5: Add tests in tests/test_docs.py and run test suite.

### Execution Trace

#### Execution Trace: anti-pattern-shell-code-probing
- 2026-10-12T09:34:33Z plan approved (along start --approved; approved_via: cli-unverified)
- 2026-10-12T09:37:15Z edit skills/along-init/protocol.md
- 2026-10-12T09:37:24Z edit AGENTS.md
- 2026-10-12T09:38:10Z edit skills/along-team/SKILL.md (x2)
- 2026-10-12T09:38:31Z edit docs/topic--troubleshooting.md
- 2026-10-12T09:38:56Z edit tests/test_docs.py
- 2026-10-12T09:39:39Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: e2059889e775
- 2026-10-12T09:43:19Z test pass (Wrap Quality Gate)
