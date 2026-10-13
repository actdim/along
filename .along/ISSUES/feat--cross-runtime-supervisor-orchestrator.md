---
protocol: along
protocol_version: "4.4.11"
slug: cross-runtime-supervisor-orchestrator
type: feat
status: open
priority: high
created: 2026-10-13
updated: 2026-10-13
agent: antigravity
tags: [orchestration, multi-runtime, supervisor, along-team, claude-code, antigravity, tiered-models]
milestone: v5.0.0-agent-run-protocol-and-observability
blocked_by: [feat--agent-runtime-adapters-claude-codex-opencode, feat--structured-blackboard-state-machine]
related: [docs--tiered-model-workflow-guide, feat--clean-turn-context-isolation-in-along-team, feat--vps-runner-daemon]
parent: feat--agent-run-protocol-and-observability
---

# Cross-Runtime Supervisor Orchestration for Heterogeneous Multi-Agent Loops

## Goal

Implement an orchestrator engine (`along team --orchestrate` or dedicated supervisor CLI) capable of dispatching sequential `along-team` roles (Scout, Architect, Implementer, Reviewer) across heterogeneous agent CLI runtimes (such as Claude Code, Antigravity, and OpenCode), enabling cost-effective tiered-model workflows with deterministic file-based state handover.

## Problem Statement

Engineering workflows benefit significantly from combining different models and runtime environments:
- Strong, expensive models (e.g. Claude Opus/Sonnet via `claude`) excel at research, architectural planning, and code review.
- Cheaper or local models (e.g. Gemini Flash via Antigravity or open-weights via OpenCode) efficiently execute isolated code modification steps when given explicit requirements and tests.

Currently, `skills/along-team/SKILL.md` defines sequential roles (Supervisor, Scout, Architect, Implementer, Reviewer), but only within a single provider boundary (subagents inside Antigravity or Task tools inside Claude Code). 

There is no supervisor engine capable of orchestrating external CLI processes sequentially across different tools:
1. Dispatching separate CLI processes for each role according to a configuration profile.
2. Managing non-interactive headless execution and capturing stdout/stderr traces.
3. Mediating phase transitions strictly through disk artifacts (`.along/ISSUES/<slug>.md`, `.along/.session/<slug>/`).
4. Running automated review gates and fix-retry loops across disparate binaries.

## Requirements

### 1. Heterogeneous Role Mapping Configuration
- Support defining runtime-to-role mappings in repository configuration or CLI arguments:
  ```yaml
  orchestration:
    scout:
      runtime: claude-code
      args: ["--dangerously-skip-permissions"]
    architect:
      runtime: claude-code
    implementer:
      runtime: antigravity
      model: flash
    reviewer:
      runtime: claude-code
  ```
- Allow per-issue or per-session override via CLI flags (`along team orchestrate <slug> --implementer antigravity --reviewer claude`).

### 2. Headless Phase Execution & Artifact Handoff
- The supervisor runs each phase through the respective runtime runner (`alongkit.runner`):
  - **Phase 1 (Scout)**: Spawns the research runtime with a read-only research prompt. Asserts completion by validating `.along/.session/<slug>/research.md`.
  - **Phase 2 (Architect)**: Spawns the planning runtime. Validates the Living Plan in `plan.md` and requirement extraction in `.along/ISSUES/<slug>.md`.
  - **Phase 3 (Implementer)**: Spawns the implementation runtime scoped strictly to Step N.
  - **Phase 4 (Reviewer)**: Spawns the verification runtime to audit the diff and test results.
- Process transitions require no shared memory: all context is mediated by the filesystem and git diff.

### 3. Clean-Turn State Snapshot Synthesis
- Before launching the Implementer or Reviewer runtime, the supervisor synthesizes an isolated prompt payload:
  - Task specifications (`REQ-N`) from the issue file.
  - Latest structured blackboard state (`state.json` / `blackboard.json`).
  - Target files and AST symbols.
  - Clean working tree diff.
- Historical dialog transcripts from other runtimes are strictly omitted, preventing context bloat and cross-model prompt pollution.

### 4. Review Verdict Evaluation & Fix-Retry Loop
- The supervisor reads the Reviewer output artifact (`reviews/step-N.md`) and exit status.
- On `PASS`: Commits or marks the step complete in `state.json` and advances to Step N+1.
- On `FAIL`: Increments retry counter, distills defects into the blackboard, and re-spawns the Implementer runtime with the defect payload (up to the retry limit).
- If retries are exhausted, halts gracefully and notifies the operator.

### 5. Process Lifecycle Supervision & Safety
- Enforces strict process timeouts for each phase.
- Handles `SIGINT` / `SIGTERM` gracefully: terminates active child processes, cleans up temporary files, and leaves `.along/.session/<slug>/` in a recoverable state.

## Acceptance Criteria

- [ ] CLI command `along team orchestrate <slug>` implemented in `scripts/along_exec.py`.
- [ ] Role-to-runtime configuration schema supported and validated.
- [ ] Multi-runtime phase execution tested with Antigravity and Claude Code adapters.
- [ ] Phase handoff succeeds using file-based blackboard state without cross-process memory leakage.
- [ ] Reviewer failure correctly triggers Implementer re-execution within the retry limit.
- [ ] Clean ASCII formatting with zero forbidden typography characters (`along sanitize` passes).
