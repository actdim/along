---
protocol: along
slug: engineering-provenance-and-dual-track-artifact-loop
title: "Engineering Provenance, Dual-Track UI Projections, and Loop Trace Disambiguation"
date: 2026-09-06
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-09-06--engineering-provenance-and-dual-track-artifact-loop - Engineering Provenance, Dual-Track UI Projections, and Loop Trace Disambiguation

- Date: 2026-09-06
- Status: accepted
- Context:
  1. Autonomous coding loops in IDEs (such as Google Antigravity, Claude Code, OpenAI Codex, OpenCode) navigate multi-step plans with frequent course corrections. However, traditional agent workflows treat session execution as a black box: once a task finishes, only the final code diff survives. Intermediate iterations, micro-fixes, and architectural pivots are lost.
  2. Google Antigravity provides rich visual design cards and test walk-throughs via ephemeral session files (`implementation_plan.md` and `walkthrough.md` in `<appDataDir>/brain/<id>/`). While powerful for human-in-the-loop review, these artifacts vanish after the IDE session closes and do not exist in CLI environments like Claude Code or Codex.
  3. When an execution step fails, agents frequently blur the distinction between a localized defect (a failing unit test or lint syntax error) and a structural architectural defect (a broken assumption or missing dependency). This causes either premature architectural reshuffling for trivial typos or futile infinite retry loops for fundamentally broken plans.
- Decision:
  1. **Dual-Track UI & Memory Projections**:
     - *Track 1 (Host IDE UI Projection)*: When running under Google Antigravity, project the Living Plan to `<appDataDir>/brain/<id>/implementation_plan.md` with `RequestFeedback: true` and `UserFacing: true` (triggering the native design card with "Proceed" button) and project final verification to `walkthrough.md`.
     - *Track 2 (Permanent Along Memory)*: In all environments, maintain portable Markdown on disk at `.along/.session/<slug>/` (`living_plan.md`, `execution_trace.md`).
  2. **Loop Disambiguation (Fix Loop vs Re-plan Loop)**:
     - `[Fix Loop]`: Micro-iterations responding to localized reviewer failures (broken unit test, lint error, null check). The worker is provided the exact failure trace and diff, and is strictly restricted to fixing the defect without altering architectural plans. Hard limit: maximum 2 retries per step.
     - `[Re-plan Loop]`: Macro-iterations triggered by structural obstacles or retry exhaustion. The Architect increments the plan version (`Revision N+1`), updates remaining steps in `living_plan.md` (and updates `implementation_plan.md` in Antigravity), and restarts the step sequence.
  3. **Engineering Provenance Compilation**:
     - In Phase 7 of `along-team` and in `along-wrap`, compile a 3-part Engineering Provenance record directly into the permanent repository session log (`.along/SESSIONS/<YYYY>/<date>--<slug>.md`):
       - `## Initial Implementation Plan (Baseline)`
       - `## Execution & Loop Trace (Fixes & Re-plans)`
       - `## Verification Walkthrough & Gate Manifest`
  4. **Backward-Compatible Schema**: Retain unchanged YAML front-matter in `.along/SESSIONS/` so existing dashboards and parsers continue to function with zero breaking changes.
- Consequences: Full traceability and auditability for all autonomous agent sessions. Human developers can inspect not only what code changed, but why the agent chose the path, how many fix attempts were made, and which gates verified the solution. CLI agents (Claude Code, Codex, OpenCode) retain 100% functionality via file-based memory, while GUI IDE agents gain rich interactive visual controls.
