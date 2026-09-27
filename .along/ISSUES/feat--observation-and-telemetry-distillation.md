---
protocol: along
protocol_version: "4.1.0"
slug: observation-and-telemetry-distillation
type: feat
status: open
priority: high
created: 2026-09-27
updated: 2026-09-27
agent: antigravity
tags: [telemetry, runners, noise-reduction, token-efficiency, context, skill-state]
milestone: v4.4.0-multi-user-merge-automation
blocked_by: []
related: [docs--state-centric-execution-and-skill-state-comparison, feat--structured-blackboard-state-machine]
---

# Observation and Telemetry Distillation in CLI Runners

## Problem

As demonstrated in recent empirical research on agent execution horizons (arXiv:2608.26263, Experiment 2: Noise Robustness), real-world execution environments emit dense background telemetry and noisy command outputs (dependency warnings, test runner chatter, irrelevant system logs).

When raw terminal output is injected directly into an agent's context:
1. **Attention Drag**: Irrelevant background chatter causes model reasoning degradation (task accuracy collapses from 0.68 down to 0.53 under noise).
2. **Context Bloat**: Test suites and build commands emit hundreds of lines of passing checks and deprecation notices, wasting thousands of context tokens.
3. **Error Obfuscation**: Critical failure traces and assertion mismatches get buried under irrelevant log lines, forcing the agent to spend extra reasoning turns locating the root cause.

## Requirements

### 1. Distillation Filter in Subprocess Engine (`alongkit.proc`)
- Add an optional distillation mode to `alongkit.proc.run_capture` (e.g., `distill=True`).
- On successful exit (code 0):
  - Strip routine progress indicators, spinner characters, and verbose success messages.
  - Return a concise one-line summary: `PASS: <command> completed successfully (code 0, <duration>s)`.
- On failure (non-zero exit):
  - Strip irrelevant environment chatter, platform warnings, and third-party deprecation notices.
  - Isolate and extract failing assertions, stack traces, and compiler errors.
  - Cap distilled error payload to a bounded token ceiling (maximum 50 lines / 2 KB).

### 2. Quiet Runner Hardening across Lifecycle Commands
- Update `along test` (`scripts/along_test.py`) and `along build` (`scripts/along_build.py`):
  - Ensure test runners default to high-signal distilled output.
  - Extract failure summaries: failing test file, line number, assertion diff, and exception message.
- Provide a `--verbose` flag for situations where full unparsed output is explicitly required for debugging.

### 3. Traceability and Telemetry Integration
- In the Agent Run Protocol (`alongkit.telemetry`), preserve raw output in offline artifacts (`.along/artifacts/<run_id>/`) while emitting only the distilled observation in the active execution span.

## Acceptance Criteria

- [ ] `alongkit.proc.run_capture` supports distilled execution mode with configurable token ceilings.
- [ ] `along test` and `along build` filter out background telemetry and isolate failing lines.
- [ ] Hermetic tests verify that noisy mock command outputs are reduced by at least 70% in token volume.
- [ ] Clean ASCII formatting with zero forbidden typography characters.
