---
protocol: along
protocol_version: "3.7.0"
slug: inquiry-read-only-and-plan-approval-gate
type: feat
status: done
completed: 2026-09-18
priority: high
created: 2026-09-18
updated: 2026-09-18
agent: antigravity
tags: [hooks, gates, safety, plan-approval, inquiry-mode, pre-tool-use]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: []
related: [feat--runtime-enforcement-of-prose-rules, feat--declarative-gates-and-protocol-traceability]
---

# Mechanical PreToolUse Gate: Inquiry Read-Only Mode and Plan Approval Enforcement

## 1. Problem Statement & Context

Passive prose rules in `AGENTS.md` (specifically the "Inquiry Read-Only Invariance: Zero-Mutation Rule on Questions") state that on interrogative questions ("is X done?", "why did Y fail?"), agents are strictly prohibited from modifying files without explicit permission.
However, in long conversation contexts, probabilistic LLMs suffer from instruction decay and "eager execution bias": when asked to analyze or debug an issue, agents frequently proceed to write code, patch files, or execute destructive shell commands without prior user approval or a validated implementation plan.

Furthermore, current gating mechanisms have loopholes:
1. `check_active_issue` passes if any issue across the repository is in `in-progress` status, even if from a previous session.
2. An agent can autonomously create an issue in `.along/ISSUES/` during a read-only turn to bypass the active issue gate.
3. Merely checking the existence of a plan file (`implementation_plan.md` or `living_plan.md`) is insufficient because the agent can write the plan file and immediately execute mutations without waiting for human approval.

## 2. Target Scope & Architecture

Implement a cross-runtime mechanical gate intercepting `PreToolUse` events before mutating tools run:

1. **Stateful Session Phase & Lock (`.along/.session/state.json`)**:
   - Track session phase (`inquiry`, `planning`, `execution`) and plan approval state (`plan_approved: bool`).
   - Default state for new inquiries is `inquiry` (read-only for repository files).

2. **PreToolUse Interception (`alongkit.hooks.predicates.check_mutation_authorization`)**:
   - Whitelist read-only tools (`view_file`, `grep_search`, `list_dir`), read-only commands (`git status`, `git diff`, test runners), and session scratchpads (`.along/.session/**`, brain artifacts).
   - For repository code and doc writes: block execution if `phase != execution` or `plan_approved != true`.
   - **Antigravity runtime**: return `decision: "ask"` / `decision: "force_ask"` with clear reason prompting human-in-the-loop confirmation.
   - **Claude Code, Codex, and Cursor runtimes**: terminate with exit code `2` (`DENY`) and explicit remediation feedback instructing the model to output analysis as text or request confirmation.

3. **Declarative Gate Catalogue Registration**:
   - Add `require_plan_approval` gate to `scripts/alongkit/hooks/default_gates.yaml`.
   - Update `docs/topic--runtime-hooks-and-gates.md` and `docs/topic--declarative-gates-and-traceability.md`.

4. **Hardening of Issue Anchor Gate**:
   - Bind `check_active_issue` to the current session or worktree rather than any global in-progress issue.
   - Prevent self-authorization within the same unapproved inquiry turn.

## 3. Acceptance Criteria

- [x] Implement `check_mutation_authorization` predicate in `scripts/alongkit/hooks/predicates.py`.
- [x] Define declarative gate in `scripts/alongkit/hooks/default_gates.yaml` and wire into `HookEngine`.
- [x] Support runtime-specific feedback (`ask` in Antigravity, `deny` in Claude/Codex/Cursor).
- [x] Whitelist internal session files and memory artifacts while protecting repository source code.
- [x] Add hermetic unit tests in `tests/test_hooks_core.py` or new dedicated test module.
- [x] Reconcile documentation and ensure `along hook verify` passes with zero drift.
