---
protocol: along
protocol_version: "4.4.5"
date: 2026-10-05
slug: bootstrap-guard-leaks-to-children
agent: claude-code
branch: main
commit: a7a7075
summary: Bootstrap re-exec guard cleared once deps import, so engines started from a bootstrapped process bootstrap themselves; test hook runs in the uv project environment (dev group), dashboard tests skip without the stack
issues_advanced: []
issues_completed: [bug--bootstrap-guard-leaks-to-children, bug--test-hook-lacks-dashboard-deps]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Bootstrap guard and test environment

## Summary
- `bug--bootstrap-guard-leaks-to-children`: `bootstrap.ensure_deps()` set `ALONGKIT_BOOTSTRAPPED=1`
  for its re-exec and never cleared it, so every descendant inherited it. An installer started
  from a bootstrapped process ran `install_manifest.py` under a bare interpreter, which saw the
  marker, refused to bootstrap and exited 2; the manifest was silently not written (the two
  installer tests failing under `along test`). `ensure_deps()` now pops the marker once the
  dependencies import; the loop guard for a child that still lacks them is unchanged.
- `bug--test-hook-lacks-dashboard-deps`: `.along/scripts/test.py` re-executed into
  `~/.along/venv`, which carries only `ruamel.yaml`, so three dashboard tests errored on
  `pydantic`. New `bootstrap.ensure_project_env(root, modules)` re-executes through
  `uv run --project <root>` (the `dev` group) under its own guard `ALONGKIT_PROJECT_ENV`, cleared
  the same way; the test hook calls it before `ensure_deps()`. Without `uv` the dashboard tests
  skip via `hermetic.requires_dashboard_deps`.
- Docs: `docs/topic--runtime-hooks-and-gates.md` (bootstrap bullets).
- Tests: 4 new in `tests/test_update_and_hooks_hardening.py`. 926 pass both from the system
  interpreter (the `along test` path) and from the repo `.venv`.

## Decisions
- None (confirmed at wrap: no architectural decisions).

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.
