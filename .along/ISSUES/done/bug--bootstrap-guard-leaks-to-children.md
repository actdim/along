---
protocol: along
protocol_version: "4.4.5"
slug: bootstrap-guard-leaks-to-children
type: bug
status: done
completed: 2026-10-05
priority: high
created: 2026-10-05
updated: 2026-10-05
agent: claude-code
tags: [bootstrap, installer, runtime]
blocked_by: []
related: [bug--test-hook-lacks-dashboard-deps]
---

# Bootstrap re-exec guard leaks into child engines, which then refuse to bootstrap

`bootstrap.ensure_deps()` re-executes an engine under an interpreter that has `ruamel.yaml`
(`~/.along/venv`, or `uv run --with`) and sets `ALONGKIT_BOOTSTRAPPED=1` in the child
environment so a failed import cannot loop. The marker is never cleared: every process the
re-executed engine spawns inherits it. When such a descendant is another engine started with a
bare interpreter (the installers call `python scripts/install_manifest.py`, hooks and MCP setup
likewise), its own `ensure_deps()` sees the marker, skips the bootstrap and exits 2 with
"missing required package `ruamel.yaml`".

Observed: `along test` from a global install runs `test.py` under the system interpreter, which
re-executes into `~/.along/venv`; `test_installers` then runs `install.ps1`, whose manifest step
fails silently and the two linked/PowerShell installer tests report "no install manifest". The
same chain breaks any engine that runs an installer or another engine from a bootstrapped
process (for example a release that reinstalls). Reproduction: `ALONGKIT_BOOTSTRAPPED=1 python
scripts/install_manifest.py --help` under an interpreter without `ruamel.yaml` exits 2.

## Requirements
- REQ-1: The guard protects only the re-exec it was set for: once `ensure_deps()` finds the
  dependencies present, it removes the marker from the process environment, so descendants
  bootstrap normally.
- REQ-2: The loop protection stays: a re-executed child that still cannot import the
  dependencies exits with `missing_exit_code` instead of re-executing again.

## Acceptance Criteria
- [x] Hermetic test: with the marker set and dependencies present, `ensure_deps()` returns and the marker is gone from `os.environ`.
- [x] Hermetic test: a bootstrapped process spawning a bare-interpreter engine lets that engine bootstrap (subprocess end-to-end: the grandchild sees no marker).
- [x] Existing loop-guard test still passes.
- [x] `python .along/scripts/test.py` from the system interpreter (the `along test` path): the installer tests pass.
- [x] Automated tests passing (926, system interpreter and repo `.venv`)
