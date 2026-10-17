---
protocol: along
protocol_version: "4.4.16"
slug: headless-runtimes-on-linux
type: spike
title: "Headless agent runtimes on Linux: launch, auth, output, exit codes, hooks"
status: hypothesis
created: 2026-10-17
updated: 2026-10-17
tags: [spike, runtimes, headless, linux, docker, claude-code, codex, opencode, antigravity]
related: [feat--autonomous-multi-runtime-mvp, feat--agent-runtime-adapters-claude-codex-opencode, feat--cross-runtime-supervisor-orchestrator, feat--isolated-environment-docker]
---

# Spike: headless agent runtimes on Linux

## Context

The autonomous mode (`feat--autonomous-multi-runtime-mvp`) launches several agent runtimes as
non-interactive CLI processes inside one Docker container. The orchestrator and the container image
both depend on facts we do not have yet. The current Antigravity runner
(`scripts/alongkit/runner/antigravity.py`) locates a Windows `antigravity.exe`; whether Antigravity
has a real headless mode on Linux is unknown. If it does not, the cheap implementer slot goes to
another CLI (Gemini CLI or OpenCode with cheap models).

## Questions (answer each per runtime: claude, codex, opencode, antigravity, gemini-cli as fallback)

1. Headless launch: exact command for a one-shot task with a prompt file (`claude -p`, `codex exec`, `opencode run`, ...).
2. No-confirmation mode: flag name and what it still blocks.
3. Auth on a server: API key env var vs interactive login; where login state lives (for a persistent volume); vendor terms for automated use.
4. Output: is there structured output (JSON / JSONL stream)? How to get the final message and changed files.
5. Exit codes: success, failure, interrupted, out of budget.
6. Hooks: can Along hooks (PreToolUse / Stop or equivalents) run inside the container for this runtime? Which events exist?
7. Model selection: how to pick the model per run (strong for planning/review, cheap for implementation).
8. Asking the user: what happens when the agent wants to ask a question in headless mode (fails, hangs, returns)?
9. Install footprint: package manager, size, Node/Python version requirements, non-root user support.
10. Time and cost limits: max turns / budget flags.

## Method

Install each CLI in a plain `ubuntu:24.04` container, run the same tiny task (edit one file in a
scratch git repo, run a test, write a summary file), record answers in a table in this file.

## Outcome

To be filled in: a per-runtime table and a recommendation of which runtimes enter the MVP image.

## Acceptance Criteria
- [ ] Every question answered for claude, codex and opencode.
- [ ] Antigravity headless status confirmed or ruled out, with a named replacement if ruled out.
- [ ] Recommendation recorded and reflected in `feat--isolated-environment-docker` and `feat--cross-runtime-supervisor-orchestrator`.
