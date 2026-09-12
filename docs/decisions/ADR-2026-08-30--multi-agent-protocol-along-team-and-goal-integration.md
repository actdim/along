---
protocol: along
slug: multi-agent-protocol-along-team-and-goal-integration
title: "Multi-Agent Development Protocol (along-team), Sequential State Machine, Living Plan, and /goal Integration"
date: 2026-08-30
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-08-30--multi-agent-protocol-along-team-and-goal-integration - Multi-Agent Development Protocol (along-team), Sequential State Machine, Living Plan, and /goal Integration

- Date: 2026-08-30
- Status: accepted
- Context:
  1. Traditional multi-agent swarms (uncontrolled parallel agents or chat-room style agents) suffer from high token overhead, race conditions in workspace files, lost context across steps, and lack of deterministic verification.
  2. Developers need an autonomous, sequential multi-agent execution pipeline that decomposes complex engineering tasks into verifiable steps without requiring constant human micromanagement.
  3. Integration is needed with autonomous environment commands (such as Antigravity `/goal`) and skill-driven team execution (`/along-team`).
- Decision:
  1. **Adopt Sequential State Machine Protocol**: Base multi-agent development on a sequential, living-plan architecture: `Supervisor -> Research (Scout) -> Architect (Living Plan) -> Step Loop [Implementer -> Reviewer/Tester -> Reassess] -> Wrap`.
  2. **Role Primitives**:
     - `Supervisor`: Orchestration, acceptance criteria verification, routing.
     - `Researcher`: Read-only discovery via `invoke_subagent` (`TypeName: "research"`, `enable_write_tools: false`).
     - `Architect`: Dynamic Living Plan formulation (2 to 5 verifiable steps).
     - `Implementer`: Code execution in isolated workspace branch via `invoke_subagent` (`TypeName: "self"`).
     - `Reviewer`: Unified verification (tests runner, diff audit, blast radius, ADR compliance) via `invoke_subagent` (`TypeName: "self"`).
  3. **Adaptive Complexity Routing**:
     - `S-Size` (1-2 files, clear scope): Fast-path single-agent execution without spawning subagents.
     - `M-Size` (isolated feature): Fast loop (Scout -> Worker -> Reviewer).
     - `L / XL-Size` (complex architecture): Full Step-by-Step Living Plan protocol with Reassess cycles.
  4. **Targeted Feedback Loops & Bounded Retries**: Reviewer rejects are routed back to the minimal relevant stage (Implementer or Architect) with a strict cap of 2 retries per step before human escalation.
  5. **Deploy `/along-team` Skill**: Provide canonical `/along-team` skill across all agent runtimes and wire it with `/goal` semantics.
- Consequences: Eliminates parallel file race conditions, cuts token waste on simple tasks through adaptive routing, guarantees rigorous automated verification per step, and enables true autonomous goal execution.
