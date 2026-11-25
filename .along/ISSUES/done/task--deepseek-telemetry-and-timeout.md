---
protocol: along
protocol_version: "4.9.1"
slug: deepseek-telemetry-and-timeout
type: task
status: done
completed: 2026-11-25
priority: medium
created: 2026-11-24
updated: 2026-11-25
agent: antigravity
tags: [opencode, deepseek, caching, telemetry, runner]
milestone: v5.0.0-agent-run-protocol-and-observability
blocked_by: []
related: [task--opencode-deepseek-cache-configuration-audit]
plan_status: approved
---

# Wire DeepSeek cache telemetry into wrap/doctor, add timeout safety net, and document audit

## Problem
Follow-up to `task--opencode-deepseek-cache-configuration-audit`. Commit `001330e` added `brief_via_stdin` to `DeepSeekHarnessRunner.__init__`, `cache_hit_ratio_pct`, and `format_usage_summary()`, but left three requirements incomplete:
1. Findings on OpenAI-compatible proxy prompt caching compatibility (`prompt_cache_hit_tokens` vs `prompt_tokens_details.cached_tokens`, prefix stability, and `brief_via_stdin` CLI vs stdin delivery) were recorded only in the ticket's `plan.md`, not in repository documentation (`docs/`).
2. No timeout safety net or headless execution test was added for `DeepSeekHarnessRunner`.
3. `format_usage_summary` and `cache_hit_ratio_pct` are not wired into `along wrap` summaries or `along doctor` diagnostics.

## Requirements
- REQ-1: Repository documentation under `docs/` MUST record generic OpenAI-compatible proxy prompt caching compatibility findings (`prompt_cache_hit_tokens` vs `cached_tokens`, prefix stability) and runner `brief_via_stdin` delivery / timeout behavior without referencing private/test providers.
- REQ-2: `DeepSeekHarnessRunner` MUST enforce a configurable timeout safety net (`timeout_seconds` / `DEFAULT_TIMEOUT_SECONDS` and `subprocess.TimeoutExpired` handling) to prevent headless hangs, covered by a headless execution + timeout unit test in `tests/test_runtime_adapters.py`.
- REQ-3: `along wrap` summaries and `along doctor` diagnostics MUST surface token breakdown and `cache_hit_ratio_pct` via `format_usage_summary` when telemetry/runner usage data is present (graceful no-op when absent).

## Acceptance Criteria
- [x] Generic OpenAI-compatible proxy caching and runner delivery findings documented in `docs/`
- [x] `DeepSeekHarnessRunner` timeout safety net implemented and tested with headless execution and timeout tests in `tests/test_runtime_adapters.py`
- [x] `format_usage_summary` and `cache_hit_ratio_pct` integrated into `along wrap` and `along doctor`
- [x] All private/test provider references scrubbed across repository files and `.along/` records
- [x] Full test pass passes with zero regressions and clean typography
