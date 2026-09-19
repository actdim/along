---
protocol: along
protocol_version: "3.7.0"
slug: cli-flag-collision-and-bootstrap
type: bug
status: done
completed: 2026-09-20
priority: high
created: 2026-09-18
updated: 2026-09-20
agent: antigravity
tags: [cli, flags, bootstrap, lifecycle]
milestone: v4.0.0-runtime-gates-and-worktree-isolation
blocked_by: []
related: []
---

# CLI Wrap Flag Collision and Dev Script UV Bootstrap

## Problem Description

During the audit of skill parameters, CLI command aliases, and direct script execution protection, two critical defects were identified:

1. **Flag Collision between `along wrap` and `along session wrap`**:
   - In `scripts/along_wrap.py` (`along wrap <slug>`), the `-s` flag is bound to `--summary` (`parser.add_argument("--summary", "-s", "-m")`), while `--status` has no short alias.
   - In `scripts/along_exec.py` (`along session wrap <slug>`), `-s` is bound to `--status` (`args[i] in ("--status", "-s")`), while `-m` is bound to `--summary`.
   - Running `along wrap <slug> -s superseded` silently assigns the text "superseded" to the session summary while leaving the issue status as "done". This violates CLI predictability and corrupts wrap metadata.
   - In addition, within `along session create`, `-s` means `--summary`, while in `along session wrap`, `-s` means `--status`.

2. **Unprotected Direct Execution of Lifecycle Scripts without UV/venv**:
   - While all 18 scripts in `scripts/*.py` invoke `bootstrap.ensure_deps()` (and `along_dash.py` has an automated `uv run` re-entry block), `.along/scripts/dev.py` lacks dependency bootstrapping.
   - Direct execution via `python .along/scripts/dev.py` by an agent or developer in an environment without pre-installed FastAPI/Uvicorn crashes with `ModuleNotFoundError` instead of cleanly bootstrapping via `uv run` or providing an actionable error.

## Acceptance Criteria

- [ ] **Align Wrap Short Flags**:
  - In `scripts/along_wrap.py`, reserve `-s` exclusively for `--status` (`choices=["done", "superseded", "cancelled", "duplicate"]`).
  - Retain `-m` for `--summary` (matching `git commit -m` convention and `along session wrap`). Remove `-s` from `--summary`.
  - Ensure flag parity between `along wrap` and `along session wrap`.
- [ ] **Standardize Session Creation Flags**:
  - Unify summary and status flags across all `along session` commands so `-m` is summary and `-s` is status wherever both appear.
- [ ] **Lifecycle Dev Script Self-Bootstrap**:
  - Add transparent `uv run` re-entry / `ensure_deps` handling to `.along/scripts/dev.py` (analogous to `along_dash.py`) so direct invocation via `python .along/scripts/dev.py` does not fail with unhandled `ModuleNotFoundError`.
- [ ] **Documentation and Skills Reconciliation**:
  - Update `skills/along-wrap/SKILL.md` and related docs to document the corrected `-s` (`--status`) and `-m` (`--summary`) flags.
- [ ] **Automated Tests**:
  - Add unit tests in `tests/` verifying argument parsing parity between `along_wrap.py` and `along_exec.py session wrap`, and verifying error handling on invalid status.
  - Zero test failures across repository test suite (`python .along/scripts/test.py`).
