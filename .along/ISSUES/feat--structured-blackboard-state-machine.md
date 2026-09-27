---
protocol: along
protocol_version: "4.1.0"
slug: structured-blackboard-state-machine
type: feat
status: open
priority: high
created: 2026-09-27
updated: 2026-09-27
agent: antigravity
tags: [blackboard, state-machine, delta-patch, session, alongkit, skill-state]
milestone: v4.5.0-structured-state-and-blackboard-engine
blocked_by: [feat--observation-and-telemetry-distillation]
related: [feat--bounded-prompt-footprint-gate, feat--clean-turn-context-isolation-in-along-team]
---

# Structured Session State Machine and Deterministic Patch Merging

## Problem

Along's ephemeral session storage (`.along/.session/<slug>/` via `alongkit.session`) maintains top-level task status (`step`, `status`, `retries`, `plan_revision`) in `state.json`. However, in-flight working context (hypotheses, discovered symbols, modified files, open defects) is either unparsed or left to an unstructured `blackboard.json`.

As highlighted in the SKILL.state research (arXiv:2608.26263):
1. **Unstructured State Drift**: Unstructured context in agent sessions leads to state corruption, forgotten constraints, and context re-exploration.
2. **Model State Overwrite Fragility**: When LLMs are asked to maintain and overwrite state directly, open-weight models suffer a 68% failure rate from accidentally deleting or omitting existing keys.
3. **Missing Patch Abstraction**: Agents lack a deterministic CLI mechanism to submit incremental state mutations (`state_patch`) with clean dictionary merge semantics.

## Requirements

### 1. Structured Working Context Schema in `alongkit.session`
- Define a standardized schema for session working memory in `state.json` (or `blackboard.json`):
  - `active_hypotheses`: Dictionary or list of current working hypotheses and their status.
  - `discovered_symbols`: Targeted code symbols and their locations.
  - `touched_files`: Set of paths modified during the session.
  - `open_defects`: Verification issues identified by the Reviewer.
  - `custom`: Extensible key-value dictionary for task-specific variables.

### 2. Deterministic Runtime Merge Operator with Null-Deletion
- Implement a deterministic merge operator in `alongkit.session` matching the mathematical specification:
  $$\Sigma_{t+1} = \Sigma_t \oplus \Delta \Sigma_t$$
- Rules:
  - Nested dictionary keys in \(\Delta \Sigma\) are merged into existing structures.
  - Setting any key value to `null` (`None`) removes that key from the persistent state.
  - Lists can append or deduplicate items based on schema configuration.
  - Schema types are validated deterministically before committing to disk; invalid patches are rejected with descriptive errors.

### 3. CLI Subcommand for Atomic Patching (`along scratch patch`)
- Add `along scratch patch <slug> <json-delta>` to `scripts/along_exec.py` and `alongkit.session`:
  - Validates JSON format and schema conformity.
  - Applies atomic file write using `alongkit.transaction` or safe file replacement.
  - Exposes `--show` to inspect the updated structured state.

## Acceptance Criteria

- [ ] `alongkit.session` implements structured state schema and deterministic merge operator \(\oplus\) with null-deletion semantics.
- [ ] `along scratch patch <slug> <json-delta>` works via CLI and validates schema before commit.
- [ ] Unit tests verify that partial updates merge correctly and setting values to null deletes target keys without corrupting sibling state.
- [ ] Clean ASCII formatting with zero forbidden typography characters.
