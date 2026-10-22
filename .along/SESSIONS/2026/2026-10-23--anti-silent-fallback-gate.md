---
protocol: along
protocol_version: "4.5.1"
date: 2026-10-23
slug: anti-silent-fallback-gate
agent: claude-code
branch: main
commit: ba99f0b
summary: 'Anti-silent-fallback gate: gate denials are ledger events settled by retry, plan approval or a user-verified ack; Stop gate unresolved_gate_denial; along gates denials/ack; closeout, wrap and issue done refuse unsettled denials (--force-reason under bypass rules).'
milestone: v4.5.2-anti-silent-fallback-gate
issues_advanced: []
issues_completed: [feat--anti-silent-fallback-gate]
decisions: [ADR-2026-10-23--gate-denials-are-ledger-events]
files: [.along/ISSUES/feat--anti-silent-fallback-gate.md, docs/topic--cli-reference.md, docs/topic--runtime-hooks-and-gates.md, docs/topic--session-lifecycle.md, scripts/alongkit/closeout.py, scripts/alongkit/commands/gates.py, scripts/alongkit/commands/issue.py, scripts/alongkit/hooks/default_gates.yaml, scripts/alongkit/hooks/engine.py, scripts/alongkit/hooks/predicates.py, scripts/alongkit/lifecycle.py, scripts/alongkit/session.py, skills/along-init/protocol-reference.md, skills/along-init/protocol.md, tests/test_anti_silent_fallback.py]
---

# Session: Anti silent fallback gate

## Summary
Anti-silent-fallback gate: gate denials are ledger events settled by retry, plan approval or a user-verified ack; Stop gate unresolved_gate_denial; along gates denials/ack; closeout, wrap and issue done refuse unsettled denials (--force-reason under bypass rules).

## Decisions
- [ADR-2026-10-23--gate-denials-are-ledger-events]

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Execution Trace

#### Execution Trace: anti-silent-fallback-gate
- 2026-10-22T22:08:08Z phase: planning -> execution
- 2026-10-22T22:08:08Z plan approved (ExitPlanMode) approved_via: exit-plan-mode
- 2026-10-22T22:11:30Z edit scripts/alongkit/session.py (x4)
- 2026-10-22T22:12:21Z edit scripts/alongkit/hooks/predicates.py (x2)
- 2026-10-22T22:12:38Z edit scripts/alongkit/hooks/engine.py (x2)
- 2026-10-22T22:12:39Z edit scripts/alongkit/hooks/default_gates.yaml (x2)
- 2026-10-22T22:12:55Z edit scripts/alongkit/hooks/predicates.py
- 2026-10-22T22:12:56Z edit scripts/alongkit/hooks/default_gates.yaml
- 2026-10-22T22:13:40Z edit scripts/alongkit/commands/gates.py (x3)
- 2026-10-22T22:13:45Z edit scripts/alongkit/closeout.py
- 2026-10-22T22:14:01Z edit scripts/alongkit/session.py
- 2026-10-22T22:14:24Z edit scripts/alongkit/lifecycle.py (x2)
- 2026-10-22T22:15:37Z edit scripts/alongkit/commands/issue.py (x4)
- 2026-10-22T22:16:04Z edit tests/test_anti_silent_fallback.py (x3)
- 2026-10-22T22:16:31Z edit skills/along-init/protocol.md
- 2026-10-22T22:16:32Z edit skills/along-init/protocol-reference.md (x2)
- 2026-10-22T22:16:49Z edit docs/topic--cli-reference.md (x2)
- 2026-10-22T22:17:08Z edit docs/topic--runtime-hooks-and-gates.md (x3)
- 2026-10-22T22:17:09Z edit docs/topic--session-lifecycle.md
- 2026-10-22T22:17:34Z edit .along/ISSUES/feat--anti-silent-fallback-gate.md
- 2026-10-22T22:18:08Z denied [projection_protection] replace_file_content: Projection Protection Violation: Direct manual edits to 'D:\Src\my\actdim\public\along\.along\ISSUES.md' are forbidden. The Single Source of Truth (SSOT) is ...
- 2026-10-22T22:22:47Z test FAIL (along test)
- 2026-10-22T22:27:58Z test pass (along test)
- 2026-10-22T22:28:07Z edit .along/ISSUES/feat--anti-silent-fallback-gate.md
