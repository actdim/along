---
protocol: along
protocol_version: "4.9.1"
slug: deepseek-telemetry-and-timeout
type: task
status: open
priority: medium
created: 2026-11-24
updated: 2026-11-24
agent: antigravity
tags: [opencode, deepseek, caching, telemetry, runner]
milestone: v5.0.0-agent-run-protocol-and-observability
blocked_by: []
related: [task--opencode-deepseek-cache-configuration-audit]
---

# Wire DeepSeek cache telemetry into wrap/doctor, add timeout safety net, and document audit

## Problem
Follow-up to `task--opencode-deepseek-cache-configuration-audit`. Commit `001330e` added `brief_via_stdin` to `DeepSeekHarnessRunner.__init__`, `cache_hit_ratio_pct`, and `format_usage_summary()`, but left three requirements incomplete:
1. Audit findings for `~/.config/opencode/opencode.jsonc` (`DeepSeek-A` proxy behavior) were recorded only in the ticket's `plan.md`, not in repository documentation (`docs/`).
2. No timeout safety net or headless execution test was added for `DeepSeekHarnessRunner`.
3. `format_usage_summary` and `cache_hit_ratio_pct` are not wired into `along wrap` summaries or `along doctor` diagnostics.

## Requirements
- REQ-1: Repository documentation under `docs/` MUST record the OpenCode `DeepSeek-A` provider caching audit findings and cache-compatible configuration recommendations.
- REQ-2: `DeepSeekHarnessRunner` MUST enforce a configurable timeout safety net to prevent headless hangs, covered by a headless execution unit test in `tests/test_runtime_adapters.py`.
- REQ-3: `along wrap` summaries and `along doctor` diagnostics MUST surface token breakdown and `cache_hit_ratio_pct` via `format_usage_summary`.

## Acceptance Criteria
- [ ] OpenCode `DeepSeek-A` cache audit findings documented in `docs/`
- [ ] `DeepSeekHarnessRunner` timeout safety net implemented and tested with headless execution test in `tests/test_runtime_adapters.py`
- [ ] `format_usage_summary` and `cache_hit_ratio_pct` integrated into `along wrap` and `along doctor`
- [ ] Full test pass passes with zero regressions and clean typography
