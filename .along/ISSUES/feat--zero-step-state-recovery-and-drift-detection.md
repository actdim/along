---
protocol: along
protocol_version: "4.1.0"
slug: zero-step-state-recovery-and-drift-detection
type: feat
status: open
priority: medium
created: 2026-09-27
updated: 2026-09-27
agent: antigravity
tags: [state-recovery, drift-detection, git-status, along-team, skill-state]
milestone: v4.6.0-clean-turn-agent-loops-and-state-recovery
blocked_by: [feat--clean-turn-context-isolation-in-along-team]
related: [feat--structured-blackboard-state-machine]
---

# Zero-Step State Recovery and External Drift Detection

## Problem

In long-running agent workflows, the environment's ground-truth state often changes outside the agent's immediate awareness:
1. An external background process modifies a lockfile or generates an artifact.
2. A Git checkout or stash occurs, altering the branch head.
3. A subagent or user modifies a file concurrently.

In conversational runtimes, agents suffer from "state recovery lag" (taking 5 to 8 consecutive turns to acknowledge that an item moved or a file changed because historical observations contradict the new reality).
In SKILL.state (arXiv:2608.26263, Experiment 3), an explicit state architecture achieves zero-turn recovery because the agent conditions its actions purely on the latest verified world state rather than on textual memory.

## Requirements

### 1. Pre-Step Drift Detection Probe in `along-team`
- Before executing any step in `along-team` or `along scratch`:
  - Run a lightweight drift probe:
    - Check working tree status: `git status --porcelain -u`.
    - Check current HEAD commit SHA.
    - Check modification timestamps or hashes of targeted files declared in the Living Plan.
  - If drift is detected compared to the session blackboard:
    - Automatically patch `state.json` via the runtime merge operator with a `state_drift_detected` alert.
    - Provide the worker with the reconciled ground-truth state immediately.

### 2. Zero-Turn Corrective Alert Protocol
- When drift occurs, bypass speculative reasoning or conversational debate:
  - Deliver a standardized system observation: `STATE_DRIFT: <path> was modified externally. Current state: <hash/diff>. Proceed with updated state.`
  - The model immediately adapts its next action without attempting to resolve contradictions against prior conversational memory.

## Acceptance Criteria

- [ ] Drift detection probe implemented in `along-team` and `alongkit.session`.
- [ ] External modifications to target files trigger immediate state reconciliation without conversational latency.
- [ ] Hermetic tests verify zero-step recovery when simulated external file modifications occur mid-session.
- [ ] Clean ASCII formatting with zero forbidden typography characters.
