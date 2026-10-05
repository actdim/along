---
protocol: along
protocol_version: "4.4.5"
slug: test-hook-lacks-dashboard-deps
type: bug
status: done
completed: 2026-10-05
priority: medium
created: 2026-10-05
updated: 2026-10-05
agent: claude-code
tags: [tests, bootstrap, dashboard]
blocked_by: []
related: [bug--bootstrap-guard-leaks-to-children]
---

# Test hook re-execs into the runtime venv, dashboard tests fail without pydantic

`.along/scripts/test.py` calls `bootstrap.ensure_deps()`, which re-executes it into the shared
runtime environment `~/.along/venv`. That environment carries only the engine runtime
dependency (`ruamel.yaml`), while the suite needs the `dev` dependency group (`actdim-along[dash]`:
`fastapi`, `uvicorn`, `pydantic`, `rich`). `along test` from a global install therefore errors in
three dashboard tests (`test_kb_search.TestCollectorSkipReporting`, `test_skills_and_scripts`
`test_13_*`) with `No module named 'pydantic'`; only a run from the repository `.venv` passes.

Installing the dashboard stack into `~/.along/venv` is not an option: its stamp is the runtime
dependency list, so hooks would rebuild it back and forth.

## Requirements
- REQ-1: The test hook runs the suite in the project's dev environment: when the dev modules are
  missing and `uv` is available, it re-executes via `uv run --project <repo>` (the `dev` group is
  synced by default) before the runtime bootstrap. Helper lives in `alongkit.bootstrap`, with its
  own guard that is cleared once the modules are present (same rule as
  [bug--bootstrap-guard-leaks-to-children]).
- REQ-2: Without `uv` (or when the project environment still lacks them), tests that need the
  dashboard stack are skipped with an explicit reason instead of erroring.

## Acceptance Criteria
- [x] Hermetic test: the helper re-executes through `uv run --project <root>` when modules are missing, does nothing when present or when its guard is set, and clears the guard after success.
- [x] The three dashboard tests skip with a reason when `pydantic`/`fastapi` are absent (`hermetic.requires_dashboard_deps`).
- [x] `python .along/scripts/test.py` from the system interpreter (the `along test` path): zero failures.
- [x] Docs: `docs/topic--runtime-hooks-and-gates.md` bootstrap paragraph updated.
- [x] Automated tests passing (926)
