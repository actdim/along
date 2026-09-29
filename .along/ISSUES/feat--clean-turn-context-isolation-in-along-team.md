---
protocol: along
protocol_version: "4.1.0"
slug: clean-turn-context-isolation-in-along-team
type: feat
status: open
priority: high
created: 2026-09-27
updated: 2026-09-27
agent: antigravity
tags: [along-team, subagents, clean-turn, context-isolation, fix-loop, skill-state]
milestone: v4.7.0-clean-turn-agent-loops-and-state-recovery
blocked_by: [feat--structured-blackboard-state-machine, feat--bounded-prompt-footprint-gate]
related: [feat--zero-step-state-recovery-and-drift-detection]
---

# Clean-Turn Context Isolation for Multi-Agent Step Loops and Fix Retries

## Problem

In `skills/along-team/SKILL.md`, when an Implementer fails Reviewer verification, the Supervisor enters a `[Fix Loop]` (up to 2 retries per step).
In both single-agent mode (Ralph loop) and persistent chat harnesses:
1. **Error Inertia & Context Poisoning**: The conversational history retains the failed code attempt, lengthy error traces, and obsolete reasoning. As demonstrated in SKILL.state (arXiv:2608.26263, Experiment 3: State Recovery), models anchored to historical error transcripts suffer 5 to 8 turns of hallucinated repetition because old context overpowers new instructions.
2. **Context Growth Across Steps**: When executing step 3 or 4 of a Living Plan, chat-based runtimes drag along the full transcript of steps 1 and 2, causing prompt sizes to scale monotonically.
3. **Loss of Ephemeral State Independence**: The model becomes reliant on re-reading previous chat turns rather than relying on the single source of truth in the session blackboard.

## Requirements

### 1. Clean-Turn Handoff Synthesis in `along-team`
- Refactor the Supervisor role in `skills/along-team/SKILL.md`:
  - When spawning or invoking an `Implementer` worker for Step N, synthesize a **clean-turn prompt snapshot**:
    1. Immutable Task Specification (`REQ-N`).
    2. Current Structured Blackboard State (`state.json` / `blackboard.json`).
    3. Target files and AST symbols.
    4. Clean diff of current uncommitted changes.
  - Strictly omit past dialog transcripts from completed steps.

### 2. Discard Intermediate Reasoning on Retry (`Fix Loop`)
- When a step fails verification and triggers a retry:
  - Discard the worker's intermediate reasoning trace and failed command attempts from the next worker turn.
  - Inject only:
    1. Original step specification.
    2. Structured blackboard state with updated `open_defects`.
    3. Current working tree diff.
    4. Distilled reviewer failure verdict (failing assertion and file/line anchor).
  - This eliminates conversational error inertia and forces the model to reason freshly from the current repository state.

### 3. Preservation of Engineering Provenance
- While the operational worker context is kept strictly clean and ephemeral, all reviewer verdicts, retry events, and plan revisions continue to be recorded asynchronously to disk (`.along/.session/<slug>/execution_trace.md` and `step_reviews/`), ensuring 100% auditability during `/along-wrap`.

## Acceptance Criteria

- [ ] `skills/along-team/SKILL.md` orchestrates clean-turn prompts for Step N workers without dragging prior step dialog.
- [ ] Fix Loop retries inject only the clean state snapshot and distilled failure verdict, discarding intermediate failed traces.
- [ ] Provenance logging in `execution_trace.md` remains intact and complete.
- [ ] Clean ASCII formatting with zero forbidden typography characters.
