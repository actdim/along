---
protocol: along
slug: provider-agnostic-subagent-abstraction
title: "Provider-Agnostic Subagent Primitives and Single-Agent Degradation in along-team"
date: 2026-09-06
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-09-06--provider-agnostic-subagent-abstraction - Provider-Agnostic Subagent Primitives and Single-Agent Degradation in along-team

- Date: 2026-09-06
- Status: accepted
- Context: `skills/along-team/SKILL.md` was hardcoded to Google Antigravity's proprietary subagent tool call `invoke_subagent` (`TypeName: "research"`, `TypeName: "self"`), breaking provider portability across Claude Code, OpenAI Codex, and OpenCode. Furthermore, it lacked a Single-Agent fallback path for environments without subagents, lacked concrete contracts for git worktree isolation (`Workspace: "branch"`), and hardcoded unavailable MCP and script paths in the Reviewer rubric. See `[bug--team-skill-uses-provider-specific-subagent-api]`.
- Decision:
  1. **Abstract Orchestration Primitives**: Define orchestration around three abstract primitives (`spawn_readonly_researcher`, `spawn_worker`, `spawn_reviewer`) backed by a concrete capability mapping table for Google Antigravity (`invoke_subagent`), Claude Code (`Task` tool), OpenAI Codex (inline single-agent fallback), and OpenCode (inline single-agent fallback).
  2. **Deterministic Single-Agent Degradation (Ralph-Style Loop)**: When subagent tools are unavailable, disabled, or running in autonomous loop mode, the state machine executes sequentially within a single agent context. The agent announces explicit phase boundaries (`=== PHASE N ===`), externalizes working state to `.along/.session/<slug>/` (`blackboard.md`, `living_plan.md`, `step_review_<N>.md`) to prevent context rot, emits explicit review verdict blocks (`VERDICT: PASS` / `VERDICT: FAIL`), and tracks retry limits (maximum 2 retries per step).
  3. **Resilient & Observable Reviewer Rubric**: Make Reviewer rubric gates conditional and observable. If `code-review-graph` MCP is offline, fall back to static AST / text search and mark the gate as `DEGRADED`. Make test runner resolution canonical (`along test` / `<resolved>/along_exec.py test` or native package runners). Require an explicit Gate Execution Manifest in the reviewer output and session log.
  4. **Workspace Isolation Contract**: Default to `Workspace: "inherit"` across all providers to avoid branch management overhead. Where worktrees are supported, standardize branch naming (`along/<slug>/step-<N>`), squash/merge on `PASS`, and mandatory prune/cleanup on abort or failure.
- Consequences: All future orchestration skills must target abstract role primitives rather than provider-specific APIs. Skills run reliably across all four supported providers with zero modification, degrading gracefully to single-agent sequential execution where subagents are absent.
