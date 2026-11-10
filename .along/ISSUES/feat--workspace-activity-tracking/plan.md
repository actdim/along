# Plan: workspace activity (DEFERRED; minimal variant only if a consumer appears)

## Execution Mode
Direct

## Verdict: defer
Checked against the code (2026-11-10):
- Nothing would read the signal. The named consumers (background draft drainage,
  idle auto-claim `feat--team-idle-auto-claim`) are not implemented, and
  `feat--issue-drafts-lifecycle` (as re-planned) has no background promotion.
- The daemon (`scripts/alongkit/daemon.py`) already keeps its own `busy`/`idle` state for
  the only real background runner, and refuses a second task while busy.
- A heartbeat file written from `along start`, `test.py`, `along scratch update` and the
  hooks touches four write paths and adds a shared file that several processes write.
  `wait_until_idle` with no caller is untestable in practice.

Recommendation: set the ticket to `blocked`, tag `risk`, `blocked_by:
[feat--team-idle-auto-claim]`, and add one line: "Re-plan when the first consumer is
designed; derive activity from existing state first." Do not implement now.

## Minimal variant (only if the user asks for it before a consumer exists)
Read-only, no new state file, no new writers.

### Step 1: `session.workspace_activity(repo_root, threshold_seconds=300) -> Dict`
Derive from what is already on disk:
- bindings: `session.list_bindings(repo_root)` (key, slug).
- last activity per key: mtime of the per-session activity trace
  (`hooks.predicates.get_activity_trace_path(repo_root, key)`).
- daemon: its existing status (`busy` / `idle`) if it exposes one on disk; else omit.
Return `{"status": "busy" | "idle", "sessions": [{key, slug, last_activity, active}],
"daemon": ...}`; `busy` when any session's trace mtime is newer than the threshold or
the daemon is busy.

### Step 2: `along session activity [--json]`
Add one subparser in `scripts/alongkit/commands/session.py`; print the dict (text table or
JSON). No doctor/status integration.

### Step 3: tests (`tests/test_workspace_activity.py`)
Fresh repo -> idle; a binding with a fresh trace -> busy; trace mtime set 10 minutes back
(`os.utime`) -> idle; `--json` parses.

### Verification
```bash
python .along/scripts/test.py tests/test_workspace_activity.py
```

Not in the minimal variant: `activity.json`, heartbeats, `runner_active`, `wait_until_idle`.
