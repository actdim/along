# Plan: Wire DeepSeek cache telemetry into wrap/doctor, add timeout safety net, and document audit

## Execution Mode
Role-Based

## Context and Scope
Follow-up to `task--opencode-deepseek-cache-configuration-audit` (`001330e`):
1. Scrub all references to the private/test provider from `.along/` history, done issue, plan, and session records.
2. Document generic OpenAI-compatible proxy prompt-caching behavior (`prompt_cache_hit_tokens` vs `prompt_tokens_details.cached_tokens`, prefix stability) and runner `brief_via_stdin` delivery and timeout handling in `docs/topic--multi-runtime-orchestration.md`.
3. Add a configurable default timeout safety net (`DEFAULT_TIMEOUT_SECONDS` / `timeout_seconds`) to `DeepSeekHarnessRunner` in `scripts/alongkit/runner/deepseek.py` so headless runs do not hang indefinitely, and normalize `cache_hit_ratio_pct` calculation in `format_usage_summary`.
4. Wire `format_usage_summary` and `cache_hit_ratio_pct` via a shared `handoff.aggregate_run_usage` helper into `along wrap` (`session.py`, `lifecycle.py`) and `along doctor` (`commands/doctor.py`) with graceful no-op behavior when no usage records exist.
5. Add headless execution, timeout safety net, and `along wrap` / `along doctor` telemetry tests in `tests/test_runtime_adapters.py`.

Target Issue: `task--deepseek-telemetry-and-timeout`
Milestone: `v5.0.0-agent-run-protocol-and-observability`

## Step-by-Step Implementation Plan

### Step 1: Scrub private references and update documentation
- Anonymize `.along/ISSUES/done/task--opencode-deepseek-cache-configuration-audit.md`, `.along/ISSUES/done/task--opencode-deepseek-cache-configuration-audit/plan.md`, `.along/SESSIONS/2026/2026-11-22--opencode-deepseek-cache-configuration-audit.md` (front-matter/Summary only, leaving Blackboard Record append-only), and `.along/HISTORY.md`.
- Update `docs/topic--multi-runtime-orchestration.md` with generic OpenAI-compatible proxy caching compatibility notes (`prompt_cache_hit_tokens` vs `cached_tokens`, prefix stability) and `brief_via_stdin` / timeout behavior.

### Step 2: Add timeout safety net and usage normalization in DeepSeekHarnessRunner
- In `scripts/alongkit/runner/deepseek.py`:
  - Define `DEFAULT_TIMEOUT_SECONDS = 600`.
  - Support `timeout_seconds` in `__init__` and `execute_run`, defaulting `self.timeout` / `self.timeout_seconds` when `timeout` is `None`, and rejecting non-positive values.
  - Ensure `format_usage_summary` computes `cache_hit_ratio_pct` from `input_tokens` and `cache_read_tokens` when absent.

### Step 3: Wire usage telemetry into along wrap and along doctor
- In `scripts/alongkit/handoff.py`: add `aggregate_run_usage(records)` to aggregate token counts and `cache_hit_ratio_pct` across run records.
- In `scripts/alongkit/session.py` (`render_blackboard_markdown`) and `scripts/alongkit/lifecycle.py` (`execute_wrap`): render `### Token Usage` in session logs and print `format_usage_summary` during `along wrap` before blackboard purge when run records carry `usage` (no-op when absent).
- In `scripts/alongkit/commands/doctor.py`: add `_doctor_runner_telemetry_checks` scanning active session run records and printing `format_usage_summary` when usage telemetry is present (graceful no-op when absent).

### Step 4: Add unit tests and verify full suite and gates
- In `tests/test_runtime_adapters.py`: add tests covering `DeepSeekHarnessRunner` headless execution (stdin and CLI arg), configurable/default `timeout_seconds` and `TimeoutExpired` handling, and `along wrap` / `along doctor` usage telemetry surfacing plus no-op when absent.
- Run targeted tests, full `.along\scripts\test.py -q`, `along sanitize`, `along hook verify --strict`, `along kb-sync --check --strict`, and private-reference grep check.
