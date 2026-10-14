---
protocol: along
protocol_version: "4.4.13"
date: 2026-10-14
slug: along-dash-missing-dashboard
agent: antigravity
branch: main
commit: 02c7b9c
summary: Completed bug--along-dash-missing-dashboard
issues_advanced: []
issues_completed: [bug--along-dash-missing-dashboard]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session: Along dash missing dashboard

## Summary
Completed bug--along-dash-missing-dashboard

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `dashboard/__init__.py` | source | 1 | 2026-10-14T10:03:03Z | antigravity--e736a933-131a-470f-b2e6-f654809a09d4 |
| `dashboard/app.py` | source | 1 | 2026-10-14T10:03:11Z | antigravity--e736a933-131a-470f-b2e6-f654809a09d4 |
| `install.ps1` | source | 2 | 2026-10-14T10:03:56Z | antigravity--e736a933-131a-470f-b2e6-f654809a09d4 |
| `install.sh` | source | 2 | 2026-10-14T10:04:14Z | antigravity--e736a933-131a-470f-b2e6-f654809a09d4 |
| `pyproject.toml` | source | 1 | 2026-10-14T10:04:28Z | antigravity--e736a933-131a-470f-b2e6-f654809a09d4 |
| `scripts/along_dash.py` | source | 1 | 2026-10-14T10:02:57Z | antigravity--e736a933-131a-470f-b2e6-f654809a09d4 |
| `scripts/alongkit/install.py` | source | 1 | 2026-10-14T10:03:33Z | antigravity--e736a933-131a-470f-b2e6-f654809a09d4 |
| `scripts/alongkit/repo.py` | source | 1 | 2026-10-14T10:03:21Z | antigravity--e736a933-131a-470f-b2e6-f654809a09d4 |
| `skills/along-dash/SKILL.md` | source | 1 | 2026-10-14T10:04:50Z | antigravity--e736a933-131a-470f-b2e6-f654809a09d4 |
| `tests/hermetic.py` | source | 1 | 2026-10-14T10:04:21Z | antigravity--e736a933-131a-470f-b2e6-f654809a09d4 |

### Plan

#### Living Plan: along-dash-missing-dashboard

Title: Fix along dash instant startup and missing dashboard module in global install

##### Problem
1. `along dash` fails with `ModuleNotFoundError: No module named 'dashboard'` when invoked globally or inside the repo via `along.ps1` / `along_exec.py`.
2. Root causes:
   - `install.ps1`, `install.sh`, and `alongkit/install.py` do not copy/plan the `dashboard/` package into `~/.along/bin/dashboard`.
   - `scripts/along_dash.py` hardcodes `repo_root = Path(__file__).resolve().parent.parent`, which resolves to `~/.along` in a global install instead of resolving `dashboard` as a sibling or in repo.
   - `alongkit/repo.py` prioritizes `~/.along/bin` over `repo_root/scripts` even when developing inside the source repository.
   - `/along-dash` skill runs CLI summary before background web launch instead of starting the web server immediately.

##### Proposed Changes
1. **Engine Dynamic Import Resolution (`scripts/along_dash.py`)**:
   - Search for `dashboard` in:
     - Sibling directory: `Path(__file__).resolve().parent / "dashboard"` (global install in `~/.along/bin/dashboard`)
     - Parent directory: `Path(__file__).resolve().parent.parent / "dashboard"` (source repo root)
     - `repo_root / "dashboard"` if running in a repo containing it.
   - Add the discovered parent to `sys.path` before importing `dashboard.app`.
2. **Installers & Layout Specification (`install.ps1`, `install.sh`, `scripts/alongkit/install.py`)**:
   - In `scripts/alongkit/install.py`: include `dashboard/` tree under `homes.bin / "dashboard"` in `engine_files` / `planned_files`.
   - In `install.ps1` and `install.sh`: copy `dashboard/` into `~/.along/bin/dashboard` (clearing `__pycache__`).
3. **Repository Script Resolution Precedence (`scripts/alongkit/repo.py`)**:
   - In `tool_search_path(repo_root)`: when `repo_root` is an Along development repository containing `scripts/`, search `repo_root/scripts` ahead of global `~/.along/bin`.
4. **Instant Auto-Launch in Skill (`skills/along-dash/SKILL.md`)**:
   - Prioritize launching the background daemon web server immediately, then displaying summary statistics and links.
5. **Sync Global Install**:
   - Run `install.ps1` to sync `~/.along/bin` with the fix so `along dash` works instantly in terminal and IDE.
6. **Verification**:
   - Run unit tests: `python .along/scripts/test.py test_installers.py -q` and `python .along/scripts/test.py test_skills_and_scripts.py -q`.
   - Verify `along dash . --cli` and `along dash . --web --no-browser` work from CLI.

##### Execution Mode
Execution Mode: Direct

### Execution Trace

#### Execution Trace: along-dash-missing-dashboard
- 2026-10-14T10:01:31Z plan approved (along plan approve) approved_via: cli-unverified, plan_sha256: a69d04398a8a
- 2026-10-14T10:02:57Z edit scripts/along_dash.py
- 2026-10-14T10:03:03Z edit dashboard/__init__.py
- 2026-10-14T10:03:11Z edit dashboard/app.py
- 2026-10-14T10:03:21Z edit scripts/alongkit/repo.py
- 2026-10-14T10:03:33Z edit scripts/alongkit/install.py
- 2026-10-14T10:03:56Z edit install.ps1 (x2)
- 2026-10-14T10:04:14Z edit install.sh (x2)
- 2026-10-14T10:04:21Z edit tests/hermetic.py
- 2026-10-14T10:04:28Z edit pyproject.toml
- 2026-10-14T10:04:50Z edit skills/along-dash/SKILL.md
- 2026-10-14T10:05:27Z denied [require_plan_approval] run_command: Unclassified Tool Nature [gate: require-plan-approval]: Tool or command 'powershell Bypass' has unclassified nature. Ask the user for its nature (read-only, ...
- 2026-10-14T10:05:39Z denied [workspace_containment] run_command: Workspace containment violation [gate: workspace-containment]: Shell working directory outside the allowed scope: 'c:\users\admin'. To allow it, declare it i...
- 2026-10-14T10:09:11Z denied [require_plan_approval] run_command: Unclassified Tool Nature [gate: require-plan-approval]: Tool or command 'get-process python' has unclassified nature. Ask the user for its nature (read-only,...
- 2026-10-14T10:09:30Z denied [require_plan_approval] run_command: Unclassified Tool Nature [gate: require-plan-approval]: Tool or command 'get-nettcpconnection 8765' has unclassified nature. Ask the user for its nature (rea...
- 2026-10-14T10:14:33Z archived by issue done
