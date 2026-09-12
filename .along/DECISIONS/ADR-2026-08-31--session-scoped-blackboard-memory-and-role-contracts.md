---
protocol: along
slug: session-scoped-blackboard-memory-and-role-contracts
title: "Session-Scoped Blackboard Memory, Strict Multi-Agent Role Contracts, and Mandatory Architectural Rationale Standards"
date: 2026-08-31
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-08-31--session-scoped-blackboard-memory-and-role-contracts - Session-Scoped Blackboard Memory, Strict Multi-Agent Role Contracts, and Mandatory Architectural Rationale Standards

- Date: 2026-08-31
- Status: accepted
- Context:
  1. Decision #013 introduced multi-agent roles (`Supervisor`, `Scout`, `Architect`, `Implementer`, `Reviewer`), but lacked an explicit ephemeral memory storage model, causing in-flight data (AST findings, living plans, reviewer verdicts) to either clutter conversation context or leak across sessions.
  2. Relying on default LLM role naming without explicit boundary contracts, input/output schemas, and verification rubrics led to prompt drift, out-of-scope code changes, and sycophantic reviews.
  3. Repository documentation and skill definitions frequently documented *how* features work while omitting *why* specific patterns were chosen, what trade-offs were made, and what concrete benefits they provide.
- Decision:
  1. **Session-Scoped Blackboard Architecture**:
     - Store in-flight multi-agent coordination data in an isolated, task-bound ephemeral directory: `.along/.session/<issue-slug>/` (auto-ignored in `.gitignore`).
     - Standardize in-flight artifacts: `plan.md` (Living Plan), `scout_findings.json` (target symbols and constraints), `step_reviews/` (Reviewer verdicts per step), `blackboard.json` (shared in-session state and mocks).
     - **Lifecycle & Automated GC**: Allocate on session start -> Update during step loops -> Distill into `.along/SESSIONS/<YYYY>/<YYYY-MM-DD>--<slug>.md` -> Purge `.along/.session/<slug>/` completely during `/along-wrap`.
  2. **Context Pruning & Typed Handoff Gatekeeping**:
     - The Supervisor strictly strips raw search logs and tool output from the Scout, injecting only distilled facts (target files, constraints, AST symbols) into the Implementer prompt.
     - The Implementer passes only touched files, diff summary, and local test results to the Reviewer.
     - Point-to-point correction loops (`send_message`) must contain concrete failure details and actionable fixes, capped at 2 retries per step.
  3. **Strict Multi-Agent Role Contracts**:
     - Formulate explicit System Prompt Templates, Boundary Contracts (prohibited actions), Input Payloads, and Output Schemas for Scout, Implementer, and Reviewer in `skills/along-team/SKILL.md`.
     - Standardize a mandatory 5-point verification rubric for Reviewer (Automated Tests, Diff Scope, ADR Compliance, Error Handling, ASCII cleanliness).
  4. **Mandatory Architectural Rationale Standard ("Why & Value Proposition")**:
     - Institutionalize a core protocol rule across `AGENTS.md` and `docs/`: every architectural topic, skill, and feature documentation must explicitly explain *why* this architecture was selected, why naive alternatives fail, trade-offs made, and the concrete value proposition to developers.
- Consequences:
  - Eliminates state leakage and context token bloat across multi-agent runs.
  - Guarantees deterministic, reproducible subagent execution with zero out-of-scope edits.
  - Ensures clean repository hygiene with automatic temp file garbage collection upon stage wrap-up.
  - Elevates documentation quality to provide clear engineering rationale and user value across the entire codebase.
