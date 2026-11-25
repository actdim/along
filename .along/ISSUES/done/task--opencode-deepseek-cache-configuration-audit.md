---
protocol: along
protocol_version: "4.9.1"
slug: opencode-deepseek-cache-configuration-audit
type: task
status: done
completed: 2026-11-22
priority: medium
created: 2026-11-22
updated: 2026-11-22
agent: antigravity
tags: [opencode, deepseek, caching, telemetry, runner]
milestone: v5.0.0-agent-run-protocol-and-observability
blocked_by: []
related: [bug--engine-atomicity-and-gate-resilience]
plan_status: approved
---

# Audit OpenCode custom OpenAI-compatible provider caching efficiency and runner prompt delivery resilience

## Problem
Diagnostics performed during an OpenCode session revealed critical performance and resilience gaps in the OpenCode / DeepSeek integration:
1. Zero prompt cache hits: A custom OpenAI-compatible OpenCode provider processed 222,688 input tokens with 0 cache hits (`tokens_cache_read = 0`), whereas the default OpenCode free provider achieved 38.3 million cache read tokens. The endpoint or proxy configuration may be missing required caching headers, prefix stability, or OpenCode provider options.
2. DSH headless runner prompt delivery risk: In `scripts/alongkit/runner/deepseek.py`, `DeepSeekHarnessRunner` defaults to `brief_via_stdin = True` and appends `"-"`. If `dsh` or OpenCode CLI in headless mode expects the prompt as a positional argument (`opencode run "<prompt>"`), piping through stdin causes the runner to hang indefinitely or drop the task brief.
3. Cache telemetry and usage visibility: Along session wrap and `along doctor` do not currently display cache hit ratios or token consumption breakdowns (prompt, completion, cache read, cache write) extracted from harness database records or NDJSON step events.

## Requirements
- REQ-1: OpenCode provider caching audit: Inspect `~/.config/opencode/` provider configuration and verify whether a custom OpenAI-compatible provider requires specific base URLs, proxy parameters, or prompt prefix alignments to activate DeepSeek context caching.
- REQ-2: Headless runner prompt delivery fallback: Update `DeepSeekHarnessRunner` in `scripts/alongkit/runner/deepseek.py` to support auto-detecting or configuring prompt delivery via CLI argument vs stdin (`--stdin` vs positional argument), with a timeout safety net to prevent headless hangs.
- REQ-3: Token and cache observability: Add automated extraction and reporting of token breakdown (`input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, and cache hit ratio percentage) into session wrap summaries and `along doctor` diagnostics.

## Acceptance Criteria
- [x] Audit and document `~/.config/opencode/` provider configuration for custom OpenAI-compatible provider cache behavior
- [x] Verify `DeepSeekHarnessRunner` prompt delivery mechanism (CLI argument vs stdin) with headless execution test
- [x] Implement token cache metrics summary in Along session reporting and diagnostics
- [x] Unit tests in `tests/test_runtime_adapters.py` covering prompt delivery and cache metrics parsing
- [x] Full test pass passes with zero regressions and clean typography
