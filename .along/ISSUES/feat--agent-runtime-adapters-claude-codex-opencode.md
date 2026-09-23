---
protocol: along
protocol_version: "4.0.1"
slug: agent-runtime-adapters-claude-codex-opencode
type: feat
status: open
priority: medium
created: 2026-09-23
updated: 2026-09-23
agent: antigravity
tags: [runtime, claude-code, codex, opencode, adapters, local-models, ollama]
milestone: v6.0.0-multi-runtime-and-omnichannel-expansion
blocked_by: [feat--agent-run-protocol-core]
related: [feat--agent-runtime-runner-antigravity]
parent: feat--multi-runtime-and-omnichannel-expansion
---

# Multi-Runtime Adapters: Claude Code, OpenAI Codex & OpenCode

## Goal
Implement dedicated runtime adapters for Claude Code, OpenAI Codex, OpenCode, and generic headless CLIs, normalizing their execution streams into standardized OpenTelemetry AEP spans.

## Problem Statement
Development teams employ different AI agent CLIs across projects. Some use commercial tools (Claude Code, Codex), while others use open-source, local-first runtimes (OpenCode) to ensure data confidentiality. Along must observe all of these runtimes uniformly without vendor lock-in.

## Technical Specifications

### 1. Claude Code Adapter
- Integration with Claude Code configuration hooks (`~/.claude/` or workspace hooks).
- Headless execution capture via `--json` / structured output streams.
- Mapping tool calls (Bash, FileEdit, Glob, Grep) to `openinference.span.kind = "TOOL"`.

### 2. OpenAI Codex Adapter
- Ingestion of Codex JSONL session events and execution streams.
- Correlation of command execution, patch application, and test results.

### 3. OpenCode Adapter (Private & Air-Gapped Workflows)
- First-class support for OpenCode runtime configured with local inference backends (Ollama, vLLM, LiteLLM).
- Configuration of local model endpoints via `OPENAI_BASE_URL` (e.g. `http://localhost:11434/v1`).
- Zero data leakage: telemetry and inference remain 100% contained within the local network perimeter.

### 4. Generic CLI Fallback Adapter
- Universal wrapper for uninstrumented CLIs: process lifecycle monitoring, exit code tracking, and line-buffered stdout/stderr capture.

## Acceptance Criteria
- [ ] Claude Code adapter tested in headless execution mode.
- [ ] Codex adapter tested with structured JSONL event streams.
- [ ] OpenCode adapter tested with local Ollama/vLLM models in a simulated private environment.
- [ ] Generic CLI adapter successfully captures process exit codes and buffered stdout/stderr.
