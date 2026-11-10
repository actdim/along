# Living Plan: Lightweight Untracked Workspace Activity Tracking and Heartbeat Engine

## Execution Mode
Direct

## 1. Context & Technical Scrutiny

In modern multi-agent systems, agents operate alongside human developers, test suites, and background watchers. Without an explicit activity signal, autonomous agents cannot detect whether the workspace is currently in an active mutation window (e.g., executing tests, running step loops) or quiescent.

### Architectural Safety Properties
1. **Zero Git Footprint**: `activity.json` is stored inside `.along/.session/activity.json`, which is already in `.gitignore`. It is purely ephemeral machine-local memory and leaves zero traces in commits or worktree branches.
2. **Crash-Resilient Heartbeats**: Instead of fragile persistent lock files that linger after unexpected process termination, activity state relies on sliding-window heartbeats (`last_ping`). If an agent process crashes or is killed, its activity automatically decays from `busy` to `idle` once the timeout window (e.g. 5 minutes) expires.
3. **Atomic File Updates**: All writes to `activity.json` use atomic temp-file write-and-replace (`alongkit.textio.write_text`) to prevent partial reads by concurrent processes.

---

## 2. Requirements & Traceability

- **REQ-1 (Activity State File)**: Define `WorkspaceActivity` dataclass and schema in `scripts/alongkit/session.py`.
- **REQ-2 (Heartbeat Updates)**:
  - Add `record_heartbeat(repo_root, key, slug, runner_active=False)` in `alongkit.session`.
  - Invoke `record_heartbeat` in `along start`, `along test` (at start and end), and during `along scratch update`.
- **REQ-3 (Idle/Busy Evaluation)**:
  - Implement `get_workspace_activity(repo_root, threshold_seconds=300) -> WorkspaceActivity`.
  - Compare `last_ping` epoch with current system time.
- **REQ-4 (CLI Inspection)**:
  - Extend `scripts/alongkit/commands/session.py` with subcommand `activity [--json]`.
- **REQ-5 (Idle Coordination Helper)**:
  - Implement `is_workspace_idle(repo_root)` and `wait_until_idle(repo_root, timeout=60, poll_interval=1.0)`.
- **REQ-6 (Testing & ASCII Hygiene)**:
  - Implement hermetic unit tests in `tests/test_workspace_activity.py`.
  - Enforce ASCII typography via `python scripts/sanitize_typography.py --check`.

---

## 3. Step-by-Step Implementation Changes

### Step 1: Core Activity Dataclass and File Operations
In `scripts/alongkit/session.py`:
- Define `ACTIVITY_FILENAME = "activity.json"`.
- Implement `get_activity_file(repo_root: str) -> str`.
- Implement `load_activity(repo_root: str) -> Optional[Dict[str, Any]]`.
- Implement `record_heartbeat(repo_root: str, key: Optional[str] = None, slug: Optional[str] = None, runner_active: bool = False) -> Dict[str, Any]`.
- Implement `get_workspace_activity(repo_root: str, threshold_seconds: int = 300) -> Dict[str, Any]`.

### Step 2: Hook Activity Updates into Core Lifecycle Commands
- In `scripts/alongkit/commands/lifecycle.py` (`along start`): record initial busy heartbeat.
- In `scripts/along_wrap.py` / `lifecycle.py` (`along wrap`): mark activity as `idle` upon closeout.
- In `.along/scripts/test.py`: record `runner_active=True` during test run and `runner_active=False` on completion.
- In `scripts/alongkit/commands/scratch.py`: refresh heartbeat during step updates.

### Step 3: Implement CLI Command `along session activity`
In `scripts/alongkit/commands/session.py`:
- Add parser for `activity` with `--json` option.
- Output formatted active session, current slug, last ping, and status (`IDLE` or `BUSY`).

### Step 4: Coordination Helpers
In `scripts/alongkit/session.py`:
- Implement `is_workspace_idle(repo_root: str) -> bool`.
- Implement `wait_until_idle(repo_root: str, timeout: float = 60.0, poll_interval: float = 1.0) -> bool`.

---

## 4. Verification Plan

### Automated Test Cases
1. Verify fresh repo reports `idle`.
2. Verify calling `record_heartbeat` marks workspace as `busy`.
3. Verify simulating an aged timestamp (> 300 seconds) causes status to decay to `idle`.
4. Verify `runner_active=True` forces status to `busy` even if session is unassigned.
5. Verify `along session activity` CLI command formats output properly in text and JSON modes.
6. Verify `wait_until_idle` waits until simulated heartbeat expires or returns True immediately when idle.
