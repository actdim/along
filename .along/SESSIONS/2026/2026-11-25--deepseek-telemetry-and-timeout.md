---
protocol: along
protocol_version: "4.9.1"
date: 2026-11-25
slug: deepseek-telemetry-and-timeout
agent: antigravity
branch: main
commit: 09b6deb
summary: Wire DeepSeek cache telemetry into wrap/doctor, add runner timeout safety net, document generic proxy caching, and scrub private provider references
milestone: v5.0.0-agent-run-protocol-and-observability
issues_advanced: []
issues_completed: [task--deepseek-telemetry-and-timeout]
decisions: []
---

# Session: Deepseek telemetry and timeout

## Summary
Wire DeepSeek cache telemetry into wrap/doctor, add runner timeout safety net, document generic proxy caching, and scrub private provider references

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: role-based; plan revision 2; approved: true.

| Step | Title | Status | Retries | Review |
| --- | --- | --- | --- | --- |
| 1 | Step 1 | passed | 0 | yes |
| 2 | Step 2 | passed | 0 | yes |
| 3 | Step 3 | passed | 0 | yes |
| 4 | Step 4 | passed | 0 | yes |

Plan: kept with the issue (`plan/plan.md`, 1 revision(s)).

### Execution Trace

#### Execution Trace: deepseek-telemetry-and-timeout
- 2026-11-25T19:46:07Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: 25b877e75b72
- 2026-11-25T19:46:18Z step 1: pending -> in-progress
- 2026-11-25T19:47:01Z step 1: in-progress -> passed
- 2026-11-25T19:47:01Z step 2: pending -> in-progress
- 2026-11-25T19:48:32Z step 2: in-progress -> passed
- 2026-11-25T19:48:32Z step 3: pending -> in-progress
- 2026-11-25T19:49:11Z step 3: in-progress -> passed
- 2026-11-25T19:49:11Z step 4: pending -> in-progress
- 2026-11-25T19:50:42Z step 4: in-progress -> passed

### Review step-1

---
verdict: pass
defects: []
---

#### Step 1 Review: Scrub private references and document proxy caching

- Verified all private/test provider references were removed from `.along/ISSUES/done/task--opencode-deepseek-cache-configuration-audit.md`, `.along/ISSUES/done/task--opencode-deepseek-cache-configuration-audit/plan.md`, `.along/SESSIONS/2026/2026-11-22--opencode-deepseek-cache-configuration-audit.md` (Blackboard Record lines untouched), and `.along/HISTORY.md`.
- Verified `docs/topic--multi-runtime-orchestration.md` documents generic OpenAI-compatible proxy caching compatibility (`prompt_cache_hit_tokens` vs `cached_tokens`, prefix affinity/stability), `brief_via_stdin` delivery, and timeout safety net without naming any private provider.

### Review step-2

---
verdict: pass
defects: []
---

#### Step 2 Review: DeepSeekHarnessRunner timeout safety net and cache ratio helper

- `DeepSeekHarnessRunner` (`scripts/alongkit/runner/deepseek.py`) now enforces a positive timeout safety net (`DEFAULT_TIMEOUT_SECONDS = 600`), accepting `timeout` and `timeout_seconds` in `__init__` and `execute_run`, rejecting non-positive timeouts with `ValueError`, and delegating to `BaseRunner.execute_run` so `subprocess.TimeoutExpired` kills the process tree and returns `outcome: "timeout"`, `exit_code: 124`.
- Extracted shared `compute_cache_hit_ratio_pct` and `aggregate_run_usage` helpers in `scripts/alongkit/handoff.py`, shared across `deepseek.py` and `opencode.py`.
- `format_usage_summary` computes `cache_hit_ratio_pct` when missing from a usage payload.

### Review step-3

---
verdict: pass
defects: []
---

#### Step 3 Review: Wire usage telemetry into along wrap and along doctor

- `scripts/alongkit/handoff.py` exposes shared `compute_cache_hit_ratio_pct` and `aggregate_run_usage`, used across `session.py`, `lifecycle.py`, `commands/doctor.py`, `runner/deepseek.py`, and `runner/opencode.py`.
- `session.render_blackboard_markdown` renders a `### Token Usage` section in the archived session log via `format_usage_summary` whenever run records include `usage`.
- `lifecycle.execute_wrap` aggregates run usage before blackboard purge and prints `-> Token usage: ...` in both dry-run and live wrap when usage records exist (no-op when absent).
- `commands/doctor.py` (`_doctor_runner_telemetry_checks`) scans active session run records and prints `[OK] Runner token usage ...` via `format_usage_summary` when telemetry is present, remaining a silent no-op when absent.

### Review step-4

---
verdict: pass
defects: []
---

#### Step 4 Review: Unit tests and verification

- Added unit tests in `tests/test_runtime_adapters.py` (`TestDeepSeekTimeoutAndTelemetryIntegration`) covering:
  - `DeepSeekHarnessRunner` default (`DEFAULT_TIMEOUT_SECONDS = 600`) and custom `timeout_seconds` configuration plus validation on non-positive values.
  - Real headless subprocess execution via shim for both `brief_via_stdin=True` and `brief_via_stdin=False`, verifying NDJSON usage parsing and `cache_hit_ratio_pct`.
  - Headless timeout safety net terminating a hanging child process with `outcome: "timeout"` and `exit_code: 124`.
  - `format_usage_summary` ratio computation fallback when `cache_hit_ratio_pct` is absent.
  - `along doctor` and `along wrap` (`lifecycle.execute_wrap` + session log) telemetry surfacing and graceful no-op behavior when no usage records exist.
- Targeted suite (250 tests across `test_runtime_adapters`, `test_wrap_atomicity`, `test_lifecycle_wrap`, `test_session_records`, `test_alongkit`, `test_runtime_detection`) passed cleanly.
