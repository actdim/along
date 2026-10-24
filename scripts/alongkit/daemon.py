#!/usr/bin/env python3
"""
alongkit.daemon - VPS runner host daemon and Telegram ingress dispatcher.

Provides persistent background runner supervisor for autonomous agent loops:
- Daemon lifecycle: start (foreground or daemonized with PID tracking), stop (graceful
  SIGTERM/SIGINT signal delivery), status (PID, uptime, active task), logs tailing.
- Telegram long-polling dispatcher: polling loop querying Telegram Bot API getUpdates
  with authorization filtering on allowed chat_id/user_id, parsing /task <slug> or
  /run <slug> commands.
- Execution dispatch: delegates to alongkit.orchestrator.CrossRuntimeOrchestrator to
  run the issue, respecting claims in state.json (one run at a time per repo).
- Worker isolation: uses alongkit.worktree when configured or repository root in
  container mode.
- Graceful shutdown handlers releasing locks and PID files.
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along daemon --help   (or: python scripts/along_exec.py daemon --help)"
    )

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from . import entities, handoff, orchestrator, proc, repo, textio, worktree

DAEMON_DIR_NAME: str = ".daemon"
PID_FILE_NAME: str = "daemon.pid"
STATE_FILE_NAME: str = "daemon.json"
LOG_FILE_NAME: str = "daemon.log"
DEFAULT_POLL_INTERVAL: float = 5.0
DEFAULT_TIMEOUT_SEC: float = 10.0
#: Commands older than this (seconds) were queued while the daemon was down; they are not run.
DEFAULT_MAX_COMMAND_AGE: float = 600.0
#: How long shutdown waits for a running task; below systemd's TimeoutStopSec=30.
DEFAULT_STOP_GRACE_SECONDS: float = 20.0
MAX_POLL_BACKOFF_SECONDS: float = 300.0
LOG_MAX_BYTES: int = 5 * 1024 * 1024
#: sysexits EX_CONFIG: a bad bot token. The systemd unit does not restart on it.
EXIT_CONFIG: int = 78


def _utc_now_iso() -> str:
    """ISO 8601 formatted UTC timestamp with trailing Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_now_display() -> str:
    """Human-readable UTC timestamp for logging."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def get_daemon_dir(repo_root: str) -> str:
    """Return the filesystem directory for daemon runtime files."""
    return os.path.join(repo.state_dir(repo_root), DAEMON_DIR_NAME)


def get_pid_file(repo_root: str) -> str:
    """Return the filesystem path for the daemon PID file."""
    return os.path.join(get_daemon_dir(repo_root), PID_FILE_NAME)


def get_state_file(repo_root: str) -> str:
    """Return the filesystem path for the daemon state JSON file."""
    return os.path.join(get_daemon_dir(repo_root), STATE_FILE_NAME)


def get_log_file(repo_root: str) -> str:
    """Return the filesystem path for the daemon log file."""
    return os.path.join(get_daemon_dir(repo_root), LOG_FILE_NAME)


def is_pid_alive(pid: int) -> bool:
    """Check whether a process with the given PID is currently active."""
    if pid <= 0:
        return False

    if os.name == "nt":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        SYNCHRONIZE = 0x00100000
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
        if not handle:
            err = kernel32.GetLastError()
            return err == 5  # ERROR_ACCESS_DENIED implies process exists
        try:
            exit_code = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                STILL_ACTIVE = 259
                return exit_code.value == STILL_ACTIVE
            return False
        finally:
            kernel32.CloseHandle(handle)
    else:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False


def process_identity(pid: int) -> Optional[str]:
    """Opaque start-time token of a live process, or None when it cannot be read.

    A PID alone is reused by the OS; the PID plus its start time names one process. Stop and
    status act only on a PID whose token matches the one recorded at start.
    [bug--runner-daemon-lifecycle-safety] REQ-4
    """
    if pid <= 0:
        return None
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return None
        try:
            times = [wintypes.FILETIME() for _ in range(4)]
            if not kernel32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
                return None
            return str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)
        finally:
            kernel32.CloseHandle(handle)
    stat_path = f"/proc/{pid}/stat"
    if os.path.isfile(stat_path):
        try:
            raw = textio.read_text(stat_path, strict=False)
            # Field 22 (starttime); the command name in field 2 may hold spaces and ')'.
            fields = raw[raw.rindex(")") + 2:].split()
            return fields[19]
        except (OSError, ValueError, IndexError):
            return None
    try:
        res = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)],
                             capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    out = (res.stdout or "").strip()
    return out if res.returncode == 0 and out else None


def is_daemon_process(pid: Optional[int], token: Optional[str]) -> bool:
    """True when `pid` is alive and is the very process that recorded `token`."""
    if pid is None or not token or not is_pid_alive(pid):
        return False
    return process_identity(pid) == token


def read_pid_record(repo_root: str) -> Tuple[Optional[int], Optional[str]]:
    """(pid, identity token) from the PID file; the token is None in a pre-identity file."""
    pid_path = get_pid_file(repo_root)
    if not os.path.isfile(pid_path):
        return None, None
    try:
        lines = textio.read_text(pid_path, strict=False).splitlines()
        val = int(lines[0].strip())
    except (OSError, ValueError, TypeError, IndexError):
        return None, None
    if val <= 0:
        return None, None
    token = lines[1].strip() if len(lines) > 1 and lines[1].strip() else None
    return val, token


def read_pid(repo_root: str) -> Optional[int]:
    """Read running daemon PID from PID file if valid."""
    return read_pid_record(repo_root)[0]


def write_pid(repo_root: str, pid: int, token: Optional[str] = None) -> None:
    """Write daemon PID (and its identity token) to file, replacing any previous one."""
    ddir = get_daemon_dir(repo_root)
    os.makedirs(ddir, exist_ok=True)
    pid_path = get_pid_file(repo_root)
    ident = token if token is not None else process_identity(pid)
    textio.write_text(pid_path, f"{pid}\n{ident or ''}\n")


def acquire_pid_file(repo_root: str) -> bool:
    """Create the PID file for this process exclusively; False when a live daemon holds it.

    A file whose process is gone, or whose identity does not match (PID reused, or written
    before identities were recorded), is stale and is replaced. [bug--runner-daemon-lifecycle-safety] REQ-5
    """
    os.makedirs(get_daemon_dir(repo_root), exist_ok=True)
    pid_path = get_pid_file(repo_root)
    my_pid = os.getpid()
    content = f"{my_pid}\n{process_identity(my_pid) or ''}\n"
    for _ in range(2):
        try:
            fd = os.open(pid_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            other_pid, other_token = read_pid_record(repo_root)
            if is_daemon_process(other_pid, other_token):
                return False
            remove_pid(repo_root)
            continue
        with os.fdopen(fd, "w", encoding="ascii") as fh:
            fh.write(content)
        return True
    return False


def remove_pid(repo_root: str) -> None:
    """Remove daemon PID file if present."""
    pid_path = get_pid_file(repo_root)
    if os.path.isfile(pid_path):
        try:
            os.remove(pid_path)
        except OSError:
            pass


def load_daemon_state(repo_root: str) -> Dict[str, Any]:
    """Load daemon state metadata from daemon.json."""
    spath = get_state_file(repo_root)
    if not os.path.isfile(spath):
        return {}
    try:
        raw = textio.read_text(spath, strict=False)
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def save_daemon_state(repo_root: str, state: Dict[str, Any]) -> None:
    """Save daemon state metadata to daemon.json."""
    ddir = get_daemon_dir(repo_root)
    os.makedirs(ddir, exist_ok=True)
    spath = get_state_file(repo_root)
    try:
        textio.write_text(spath, json.dumps(state, indent=2) + "\n")
    except OSError:
        pass


def append_daemon_log(repo_root: str, message: str, level: str = "INFO") -> None:
    """Append a formatted entry to the daemon log file."""
    ddir = get_daemon_dir(repo_root)
    os.makedirs(ddir, exist_ok=True)
    lpath = get_log_file(repo_root)
    entry = f"[{_utc_now_display()}] [{level.upper()}] {message}\n"
    try:
        # One rotated generation keeps a long-running daemon from filling the disk.
        if os.path.isfile(lpath) and os.path.getsize(lpath) > LOG_MAX_BYTES:
            os.replace(lpath, lpath + ".1")
        with open(lpath, "a", encoding="utf-8", errors="replace") as f:
            f.write(entry)
    except OSError:
        pass


def terminate_pid(pid: int, timeout_sec: float = DEFAULT_TIMEOUT_SEC) -> bool:
    """Send graceful termination signal to process and wait up to timeout_sec."""
    if not is_pid_alive(pid):
        return True

    # 1. Graceful signal
    try:
        if os.name == "nt":
            import signal
            os.kill(pid, signal.SIGTERM)
        else:
            import signal
            os.kill(pid, signal.SIGTERM)
    except OSError:
        pass

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if not is_pid_alive(pid):
            return True
        time.sleep(0.1)

    # 2. Force termination if still active
    if is_pid_alive(pid):
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    capture_output=True,
                    check=False,
                )
            else:
                import signal
                os.kill(pid, signal.SIGKILL)
        except OSError:
            pass

        # Final verification
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if not is_pid_alive(pid):
                return True
            time.sleep(0.1)

    return not is_pid_alive(pid)


def get_daemon_status(repo_root: str) -> Dict[str, Any]:
    """Retrieve detailed daemon running status and metadata.

    `running` only for the process that wrote the PID file (PID and identity token match); a
    live PID with another or no token is a reused PID, reported as `stale-pid`.
    """
    pid, token = read_pid_record(repo_root)
    state = load_daemon_state(repo_root)

    if pid is not None:
        if is_daemon_process(pid, token):
            started_at = state.get("started_at")
            uptime_seconds = None
            if started_at:
                try:
                    dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    uptime_seconds = max(0.0, (now - dt).total_seconds())
                except (ValueError, TypeError):
                    pass

            return {
                "running": True,
                "pid": pid,
                "status": state.get("status", "running"),
                "uptime_seconds": uptime_seconds,
                "started_at": started_at,
                "current_task": state.get("current_task"),
                "current_run_id": state.get("current_run_id"),
                "worktree": state.get("worktree", False),
                "poll_interval": state.get("poll_interval", DEFAULT_POLL_INTERVAL),
                "port": state.get("port"),
                "last_poll_at": state.get("last_poll_at"),
            }
        else:
            # Stale PID file
            return {
                "running": False,
                "pid": pid,
                "status": "stale-pid",
                "uptime_seconds": None,
                "started_at": state.get("started_at"),
                "current_task": None,
                "current_run_id": None,
                "worktree": state.get("worktree", False),
                "poll_interval": state.get("poll_interval", DEFAULT_POLL_INTERVAL),
                "port": state.get("port"),
                "stale": True,
                # Alive but not ours: the PID was reused, or an older version wrote no token.
                "pid_alive": is_pid_alive(pid),
            }

    return {
        "running": False,
        "pid": None,
        "status": "stopped",
        "uptime_seconds": None,
        "started_at": state.get("started_at"),
        "current_task": None,
        "current_run_id": None,
        "worktree": state.get("worktree", False),
        "poll_interval": state.get("poll_interval", DEFAULT_POLL_INTERVAL),
        "port": state.get("port"),
    }


def stop_daemon(repo_root: str, timeout_sec: float = DEFAULT_TIMEOUT_SEC) -> Tuple[bool, str]:
    """Gracefully terminate running runner daemon."""
    status = get_daemon_status(repo_root)
    pid = status.get("pid")

    if not status.get("running"):
        if pid is not None and status.get("stale"):
            remove_pid(repo_root)
            st = load_daemon_state(repo_root)
            st["status"] = "stopped"
            save_daemon_state(repo_root, st)
            if status.get("pid_alive"):
                append_daemon_log(repo_root, f"Stale PID file names live PID {pid} that is not this daemon; "
                                  "not signalled", level="WARNING")
                return True, (f"Cleaned up stale daemon PID file ({pid}). PID {pid} is alive but is not a "
                              "verified along daemon (reused PID, or started by an older version); it was "
                              "not signalled. Stop it by hand if it is yours.")
            return True, f"Cleaned up stale daemon PID file ({pid}). Daemon was not running."
        return True, "Daemon is not running."

    append_daemon_log(repo_root, f"Termination requested for PID {pid}", level="INFO")
    ok = terminate_pid(pid, timeout_sec=timeout_sec)
    if ok:
        remove_pid(repo_root)
        st = load_daemon_state(repo_root)
        st["status"] = "stopped"
        save_daemon_state(repo_root, st)
        append_daemon_log(repo_root, f"Daemon PID {pid} stopped successfully", level="INFO")
        return True, f"Daemon (PID {pid}) stopped successfully."
    else:
        append_daemon_log(repo_root, f"Failed to stop daemon PID {pid}", level="ERROR")
        return False, f"Failed to stop daemon (PID {pid}): process did not terminate."


def tail_daemon_logs(
    repo_root: str,
    lines: int = 50,
    follow: bool = False,
    output_fn: Optional[Callable[[str], None]] = None,
) -> None:
    """Print or tail daemon log output."""
    out = output_fn or print
    log_path = get_log_file(repo_root)

    if not os.path.isfile(log_path):
        out(f"No daemon log file found at {log_path}")
        return

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            for line in all_lines[-lines:]:
                out(line.rstrip("\r\n"))

            if not follow:
                return

            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if line:
                    out(line.rstrip("\r\n"))
                else:
                    time.sleep(0.5)
    except KeyboardInterrupt:
        pass


# ---------------------------------------------------------------------------
# Telegram Client & Message Dispatcher
# ---------------------------------------------------------------------------

class TelegramAuthError(RuntimeError):
    """The Bot API rejected the token (HTTP 401/404); retrying cannot help."""


class TelegramClient:
    """Standard library HTTP client for Telegram Bot API."""

    def __init__(self, bot_token: str, base_url: str = "https://api.telegram.org") -> None:
        self.bot_token = bot_token.strip()
        self.base_url = f"{base_url.rstrip('/')}/bot{self.bot_token}"

    def get_updates(
        self,
        offset: Optional[int] = None,
        limit: int = 100,
        timeout: int = 20,
    ) -> List[Dict[str, Any]]:
        """Fetch incoming updates using long polling."""
        params: Dict[str, Any] = {
            "timeout": timeout,
            "limit": limit,
            "allowed_updates": ["message"],
        }
        if offset is not None:
            params["offset"] = offset

        query = urllib.parse.urlencode(params)
        url = f"{self.base_url}/getUpdates?{query}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Along-Runner-Daemon/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout + 15) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("ok"):
                        res = data.get("result", [])
                        return res if isinstance(res, list) else []
        except urllib.error.HTTPError as exc:
            # The URL holds the token: report the status only.
            if exc.code in (401, 404):
                raise TelegramAuthError(f"getUpdates rejected the bot token (HTTP {exc.code})") from None
            raise RuntimeError(f"getUpdates HTTP {exc.code}") from None
        except (urllib.error.URLError, OSError, ValueError, TypeError, TimeoutError) as exc:
            raise RuntimeError(f"getUpdates network error: {exc}") from exc
        return []

    def send_message(self, chat_id: Union[int, str], text: str) -> bool:
        """Send a plain text message to the specified Telegram chat."""
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text[:4000],
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Along-Runner-Daemon/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return bool(data.get("ok"))
        except (urllib.error.URLError, OSError, ValueError, TypeError, TimeoutError):
            return False
        return False


def parse_telegram_command(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse incoming Telegram text message for commands and arguments.

    Supports:
      /task <slug>
      /run <slug>
      /status
      /stop
      /help
    Also handles @botname suffixes (e.g. /task@my_runner_bot <slug>).

    Returns:
      (command, argument) or (None, None)
    """
    if not text:
        return None, None
    raw = text.strip()
    if not raw.startswith("/"):
        return None, None

    parts = raw.split(None, 1)
    cmd_part = parts[0]
    arg = parts[1].strip() if len(parts) > 1 else None

    # Strip leading slash if present: /task -> task
    if cmd_part.startswith("/"):
        cmd_part = cmd_part[1:]

    # Strip bot handle if present: task@along_bot -> task
    if "@" in cmd_part:
        cmd_part = cmd_part.split("@", 1)[0]

    return cmd_part.lower(), arg


def is_sender_authorized(
    allowed_ids: Optional[Sequence[Union[int, str]]],
    chat_id: Optional[Union[int, str]],
    user_id: Optional[Union[int, str]],
) -> bool:
    """Verify whether sender chat_id or user_id is authorized.

    If allowed_ids is empty or None, authorization fails (fail-closed security).
    """
    if not allowed_ids:
        return False

    allowed_set = {str(item).strip() for item in allowed_ids if str(item).strip()}
    if not allowed_set:
        return False

    if chat_id is not None and str(chat_id).strip() in allowed_set:
        return True
    if user_id is not None and str(user_id).strip() in allowed_set:
        return True
    return False


def resolve_daemon_config(repo_root: str) -> Dict[str, Any]:
    """Resolve Telegram token, chat IDs, and operational settings from env and configs."""
    cfg: Dict[str, Any] = {
        "bot_token": "",
        "chat_ids": [],
        "poll_interval": DEFAULT_POLL_INTERVAL,
        "worktree": False,
        "port": None,
        "max_command_age": DEFAULT_MAX_COMMAND_AGE,
    }

    # 1. Read global config
    global_cfg_path = os.path.expanduser("~/.along/config.json")
    if os.path.isfile(global_cfg_path):
        try:
            with open(global_cfg_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    t_section = loaded.get("transports", {}).get("telegram", {})
                    if isinstance(t_section, dict):
                        if t_section.get("bot_token"):
                            cfg["bot_token"] = str(t_section["bot_token"]).strip()
                        if t_section.get("chat_id"):
                            cfg["chat_ids"].append(str(t_section["chat_id"]).strip())
        except (OSError, json.JSONDecodeError):
            pass

    # 2. Read local repo config
    local_cfg_path = os.path.join(repo.state_dir(repo_root), "config.json")
    if os.path.isfile(local_cfg_path):
        try:
            with open(local_cfg_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    t_section = loaded.get("transports", {}).get("telegram", {})
                    if isinstance(t_section, dict):
                        if t_section.get("bot_token"):
                            cfg["bot_token"] = str(t_section["bot_token"]).strip()
                        if t_section.get("chat_id"):
                            cid = str(t_section["chat_id"]).strip()
                            if cid and cid not in cfg["chat_ids"]:
                                cfg["chat_ids"].append(cid)
                    d_section = loaded.get("daemon", {})
                    if isinstance(d_section, dict):
                        if "worktree" in d_section:
                            cfg["worktree"] = bool(d_section["worktree"])
                        if "poll_interval" in d_section:
                            cfg["poll_interval"] = float(d_section["poll_interval"])
                        if "max_command_age" in d_section:
                            cfg["max_command_age"] = float(d_section["max_command_age"])
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            pass

    # 3. Environment overrides (authoritative)
    env_token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("ALONG_TELEGRAM_BOT_TOKEN")
    if env_token:
        cfg["bot_token"] = env_token.strip()

    env_chat = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("ALONG_TELEGRAM_CHAT_ID")
    if env_chat:
        # Support comma-separated chat IDs
        for part in env_chat.split(","):
            clean_part = part.strip()
            if clean_part and clean_part not in cfg["chat_ids"]:
                cfg["chat_ids"].append(clean_part)

    env_interval = os.environ.get("ALONG_DAEMON_POLL_INTERVAL")
    if env_interval:
        try:
            cfg["poll_interval"] = float(env_interval)
        except (ValueError, TypeError):
            pass

    env_wt = os.environ.get("ALONG_DAEMON_WORKTREE")
    if env_wt:
        cfg["worktree"] = env_wt.lower() in ("1", "true", "yes")

    env_age = os.environ.get("ALONG_DAEMON_MAX_COMMAND_AGE")
    if env_age:
        try:
            cfg["max_command_age"] = float(env_age)
        except (ValueError, TypeError):
            pass

    return cfg


# ---------------------------------------------------------------------------
# Runner Daemon Engine
# ---------------------------------------------------------------------------

class RunnerDaemon:
    """Supervises VPS background execution loop and Telegram ingress."""

    def __init__(
        self,
        repo_root: Optional[str] = None,
        poll_interval: Optional[float] = None,
        port: Optional[int] = None,
        use_worktree: bool = False,
        dry_run: bool = False,
        telegram_token: Optional[str] = None,
        allowed_chats: Optional[Sequence[Union[int, str]]] = None,
        telegram_client: Optional[TelegramClient] = None,
        orchestrator_fn: Optional[Callable[..., Dict[str, Any]]] = None,
        log_to_stdout: bool = True,
        max_command_age: Optional[float] = None,
        stop_grace_seconds: float = DEFAULT_STOP_GRACE_SECONDS,
    ) -> None:
        self.repo_root = os.path.abspath(repo_root) if repo_root else (repo.find_repo_root() or os.getcwd())
        config = resolve_daemon_config(self.repo_root)

        self.bot_token = telegram_token or config.get("bot_token", "")
        self.allowed_chats = list(allowed_chats) if allowed_chats is not None else config.get("chat_ids", [])
        self.poll_interval = float(poll_interval) if poll_interval is not None else float(config.get("poll_interval", DEFAULT_POLL_INTERVAL))
        self.port = port
        self.use_worktree = bool(use_worktree or config.get("worktree", False))
        self.dry_run = bool(dry_run)
        self.log_to_stdout = bool(log_to_stdout)

        self.client = telegram_client or (TelegramClient(self.bot_token) if self.bot_token else None)
        self.orchestrator_fn = orchestrator_fn or orchestrator.run_orchestration

        self.max_command_age = float(max_command_age if max_command_age is not None
                                     else config.get("max_command_age", DEFAULT_MAX_COMMAND_AGE))
        self.stop_grace_seconds = float(stop_grace_seconds)

        self._stop_requested = False
        self._stop_event = threading.Event()
        self.current_task: Optional[str] = None
        self.current_run_id: Optional[str] = None
        # The acknowledged Telegram offset survives restarts: an update accepted before a crash
        # is never handed out again. [bug--runner-daemon-lifecycle-safety] REQ-2
        saved_offset = load_daemon_state(self.repo_root).get("telegram_offset")
        self.last_update_id: Optional[int] = saved_offset if isinstance(saved_offset, int) else None
        self.started_at: Optional[str] = None
        # Tasks run on a worker thread inside run(), inline when called directly.
        self._task_lock = threading.Lock()
        self._async_tasks = False
        self._worker: Optional[threading.Thread] = None
        self._task_chat: Optional[Union[int, str]] = None

    def log(self, message: str, level: str = "INFO") -> None:
        """Write structured log to file and optional stdout."""
        append_daemon_log(self.repo_root, message, level=level)
        if self.log_to_stdout:
            print(f"[{_utc_now_display()}] [{level.upper()}] {message}")

    def request_stop(self) -> None:
        """Request loop termination."""
        self._stop_requested = True
        self._stop_event.set()

    def _sleep(self, seconds: float) -> None:
        """Wait between polls; returns early when a stop is requested."""
        self._stop_event.wait(seconds)

    def _save_offset(self, update_id: int) -> None:
        st = load_daemon_state(self.repo_root)
        st["telegram_offset"] = update_id
        save_daemon_state(self.repo_root, st)

    def _setup_signals(self) -> None:
        """Register signal handlers for graceful termination."""
        def _handler(signum, frame):
            sig_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
            self.log(f"Received signal {sig_name}; shutting down daemon gracefully...")
            self.request_stop()

        try:
            signal.signal(signal.SIGINT, _handler)
        except (ValueError, OSError):
            pass
        if hasattr(signal, "SIGTERM"):
            try:
                signal.signal(signal.SIGTERM, _handler)
            except (ValueError, OSError):
                pass

    def _send_telegram(self, chat_id: Union[int, str], text: str) -> None:
        """Send message to Telegram if client is configured."""
        if self.client:
            try:
                self.client.send_message(chat_id, text)
            except (urllib.error.URLError, OSError, ValueError, RuntimeError, TimeoutError) as exc:
                self.log(f"Failed to send Telegram notification to {chat_id}: {exc}", level="WARNING")

    def _broadcast_telegram(self, text: str) -> None:
        """Broadcast message to all authorized Telegram chat IDs."""
        if not self.client or not self.allowed_chats:
            return
        for cid in self.allowed_chats:
            self._send_telegram(cid, text)

    def handle_status_command(self, chat_id: Union[int, str]) -> None:
        """Handle /status inquiry via Telegram."""
        st = get_daemon_status(self.repo_root)
        uptime = st.get("uptime_seconds")
        uptime_str = f"{int(uptime)}s" if uptime is not None else "unknown"
        task_str = self.current_task or "None (idle)"
        msg = (
            f"[Along Runner Status]\n"
            f"Status: {st.get('status', 'running')}\n"
            f"PID: {st.get('pid')}\n"
            f"Uptime: {uptime_str}\n"
            f"Active Task: {task_str}\n"
            f"Worktree Isolation: {'Enabled' if self.use_worktree else 'Disabled'}\n"
            f"Poll Interval: {self.poll_interval}s"
        )
        self._send_telegram(chat_id, msg)

    def handle_task_command(self, chat_id: Union[int, str], slug: Optional[str]) -> None:
        """Handle /task or /run command to dispatch execution."""
        if not slug:
            self._send_telegram(chat_id, "Error: Missing issue slug. Usage: /task <slug> or /run <slug>")
            return

        clean_slug = slug.strip()
        # Security sanitization on slug: only standard alphanumeric, hyphens, underscores
        if not re.match(r"^[a-zA-Z0-9_-]+$", clean_slug):
            self._send_telegram(chat_id, f"Error: Invalid slug '{clean_slug}'. Use only alphanumeric characters, hyphens, and underscores.")
            return

        with self._task_lock:
            # 1. Single concurrency enforcement: Check if daemon is currently executing a task
            if self.current_task is not None:
                self.log(f"Rejected dispatch for '{clean_slug}': daemon is busy with '{self.current_task}'", level="WARNING")
                self._send_telegram(
                    chat_id,
                    f"Runner busy: currently executing task '{self.current_task}'. Only one task runs at a time per repository.",
                )
                return

            # 2. Check if issue is already claimed by another runner in state.json
            if handoff.is_claim_active(self.repo_root, clean_slug) and not self.dry_run:
                claim_info = handoff.get_claim(self.repo_root, clean_slug)
                owner = claim_info.get("run_id") if claim_info else "another process"
                self.log(f"Rejected dispatch for '{clean_slug}': already claimed by {owner} in state.json", level="WARNING")
                self._send_telegram(
                    chat_id,
                    f"Task '{clean_slug}' is currently claimed in state.json by {owner}. Handoff claim active.",
                )
                return

            # 3. Dispatch execution
            self.current_task = clean_slug
            run_id = f"vps-{int(time.time())}"
            self.current_run_id = run_id
            self._task_chat = chat_id

        # Update daemon state
        st = load_daemon_state(self.repo_root)
        st["status"] = "busy"
        st["current_task"] = clean_slug
        st["current_run_id"] = run_id
        save_daemon_state(self.repo_root, st)

        self.log(f"Dispatched execution for task '{clean_slug}' (run_id: {run_id}, worktree: {self.use_worktree})...")
        self._send_telegram(chat_id, f"Starting execution for issue '{clean_slug}' (run: {run_id})...")

        if self._async_tasks:
            # Off the poll loop, so /status, busy replies and SIGTERM work during a run.
            # [bug--runner-daemon-lifecycle-safety] REQ-6
            self._worker = threading.Thread(
                target=self._execute_task, args=(chat_id, clean_slug, run_id),
                name=f"along-task-{clean_slug}", daemon=True,
            )
            self._worker.start()
        else:
            self._execute_task(chat_id, clean_slug, run_id)

    def _teardown_worktree(self, chat_id: Union[int, str], slug: str, wt_info: Any) -> None:
        """Remove a clean worktree, keep its branch; keep a dirty worktree whole.

        The branch holds the run's commits and nothing has merged it yet.
        [bug--runner-daemon-lifecycle-safety] REQ-1
        """
        status = proc.git(["status", "--porcelain"], cwd=wt_info.path)
        if not status.ok or (status.stdout or "").strip():
            self.log(f"Worktree for '{slug}' has uncommitted changes (or git status failed); kept at {wt_info.path}",
                     level="WARNING")
            self._send_telegram(chat_id, f"Worktree for '{slug}' has uncommitted changes and was kept at "
                                         f"{wt_info.path} (branch {wt_info.branch}).")
            return
        self.log(f"Tearing down isolated worktree for '{slug}' (keeping branch {wt_info.branch})...")
        try:
            worktree.remove_worktree(self.repo_root, slug, force=True, delete_branch=False)
        except (OSError, RuntimeError) as wt_err:
            self.log(f"Failed to remove worktree for '{slug}': {wt_err}", level="WARNING")
        self._send_telegram(chat_id, f"Work for '{slug}' is on branch {wt_info.branch}.")

    def _execute_task(self, chat_id: Union[int, str], clean_slug: str, run_id: str) -> None:
        """Run one dispatched task to its end and return the runner to idle."""
        exec_root = self.repo_root
        wt_info = None

        try:
            if self.use_worktree:
                self.log(f"Creating isolated worktree for '{clean_slug}'...")
                wt_info = worktree.create_worktree(self.repo_root, clean_slug)
                exec_root = wt_info.path
                self.log(f"Isolated worktree created at {exec_root}")

            # Run orchestration
            res = self.orchestrator_fn(
                repo_root=exec_root,
                slug=clean_slug,
                dry_run=self.dry_run,
            )

            status_out = res.get("status", "unknown") if isinstance(res, dict) else "completed"
            if status_out == "completed":
                self.log(f"Task '{clean_slug}' completed successfully.")
                self._send_telegram(chat_id, f"Task '{clean_slug}' completed successfully.")
            elif status_out == "needs-input":
                reason = res.get("reason") if isinstance(res, dict) else None
                self.log(f"Task '{clean_slug}' paused: needs operator input." + (f" {reason}" if reason else ""))
                self._send_telegram(chat_id, f"Task '{clean_slug}' paused: awaiting operator input."
                                    + (f" Reason: {reason}." if reason else ""))
            elif status_out == "blocked":
                reason = res.get("reason", "unknown") if isinstance(res, dict) else ""
                self.log(f"Task '{clean_slug}' blocked: {reason}", level="WARNING")
                self._send_telegram(chat_id, f"Task '{clean_slug}' blocked: {reason}")
            elif status_out == "timeout":
                self.log(f"Task '{clean_slug}' timed out.", level="ERROR")
                self._send_telegram(chat_id, f"Task '{clean_slug}' timed out.")
            elif status_out == "dry-run":
                phases = ", ".join(str(p.get("phase")) for p in res.get("phases", [])) if isinstance(res, dict) else ""
                self.log(f"Dry run for '{clean_slug}': {phases}")
                self._send_telegram(chat_id, f"Dry run for '{clean_slug}' (nothing changed): {phases}")
            else:
                reason = res.get("reason", status_out) if isinstance(res, dict) else status_out
                self.log(f"Task '{clean_slug}' finished with status '{status_out}': {reason}", level="WARNING")
                self._send_telegram(chat_id, f"Task '{clean_slug}' finished: {status_out} ({reason})")

        except (RuntimeError, OSError, ValueError, TypeError, KeyError, AttributeError, subprocess.SubprocessError) as exc:
            self.log(f"Unhandled error during task execution for '{clean_slug}': {exc}", level="ERROR")
            self._send_telegram(chat_id, f"Error during execution of task '{clean_slug}': {exc}")
        finally:
            if wt_info is not None:
                self._teardown_worktree(chat_id, clean_slug, wt_info)

            with self._task_lock:
                self.current_task = None
                self.current_run_id = None
                self._task_chat = None
            st = load_daemon_state(self.repo_root)
            st["status"] = "idle"
            st["current_task"] = None
            st["current_run_id"] = None
            save_daemon_state(self.repo_root, st)
            self.log(f"Runner returned to idle state.")

    def process_update(self, update: Dict[str, Any]) -> None:
        """Process a single Telegram update with authorization filtering."""
        msg = update.get("message")
        if not isinstance(msg, dict):
            return

        chat = msg.get("chat", {})
        sender = msg.get("from", {})
        chat_id = chat.get("id")
        user_id = sender.get("id")
        text = msg.get("text", "")

        # Authorization filter
        if not is_sender_authorized(self.allowed_chats, chat_id, user_id):
            self.log(
                f"Unauthorized ingress attempt rejected from chat_id={chat_id}, user_id={user_id}",
                level="WARNING",
            )
            if chat_id:
                self._send_telegram(chat_id, "Access denied: unauthorized sender ID.")
            return

        cmd, arg = parse_telegram_command(text)
        if not cmd:
            return

        # Commands queued while the daemon was down are not run late without the sender knowing.
        # [bug--runner-daemon-lifecycle-safety] REQ-3
        sent_at = msg.get("date")
        if (self.max_command_age > 0 and isinstance(sent_at, (int, float))
                and time.time() - sent_at > self.max_command_age):
            when = datetime.fromtimestamp(sent_at, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            self.log(f"Ignored stale command '/{cmd}' from chat_id={chat_id} sent at {when}", level="WARNING")
            self._send_telegram(chat_id, f"Ignored /{cmd}{' ' + arg if arg else ''} sent at {when} (older than "
                                         f"{int(self.max_command_age)}s); send it again if you still want it.")
            return

        self.log(f"Authorized Telegram command '{cmd}' from user_id={user_id} in chat_id={chat_id}")

        if cmd in ("task", "run"):
            self.handle_task_command(chat_id, arg)
        elif cmd == "status":
            self.handle_status_command(chat_id)
        elif cmd in ("help", "start"):
            help_msg = (
                "[Along Runner Daemon]\n"
                "Available commands:\n"
                "- /task <slug> : Dispatch issue execution\n"
                "- /run <slug>  : Alias for /task\n"
                "- /status      : Check runner daemon health and active task\n"
                "- /help        : Show this message"
            )
            self._send_telegram(chat_id, help_msg)
        else:
            self._send_telegram(chat_id, f"Unknown command '{cmd}'. Send /help for command list.")

    def run(self) -> int:
        """Main entry point for runner daemon event loop."""
        my_pid = os.getpid()
        self.started_at = _utc_now_iso()
        if not acquire_pid_file(self.repo_root):
            self.log(f"Another runner daemon (PID {read_pid(self.repo_root)}) is running for this repository; "
                     "exiting.", level="ERROR")
            return 1
        self._setup_signals()
        self._async_tasks = True

        initial_state = {
            "pid": my_pid,
            "status": "idle",
            "started_at": self.started_at,
            "current_task": None,
            "current_run_id": None,
            "worktree": self.use_worktree,
            "poll_interval": self.poll_interval,
            "port": self.port,
            "last_poll_at": None,
            "telegram_offset": self.last_update_id,
        }
        save_daemon_state(self.repo_root, initial_state)

        self.log(
            f"Runner daemon started (PID {my_pid}, interval={self.poll_interval}s, "
            f"worktree={self.use_worktree}, dry_run={self.dry_run})"
        )

        if not self.bot_token:
            self.log(
                "No Telegram bot token configured. Daemon running in idle standby heartbeat mode.",
                level="WARNING",
            )

        exit_code = 0
        failures = 0
        try:
            while not self._stop_requested:
                now_iso = _utc_now_iso()
                st = load_daemon_state(self.repo_root)
                st["last_poll_at"] = now_iso
                save_daemon_state(self.repo_root, st)

                if self.client and self.bot_token:
                    try:
                        timeout_val = max(1, min(20, int(self.poll_interval)))
                        offset_val = (self.last_update_id + 1) if self.last_update_id is not None else None
                        updates = self.client.get_updates(
                            offset=offset_val,
                            timeout=timeout_val,
                        )
                        failures = 0
                        for upd in updates:
                            if self._stop_requested:
                                break
                            upd_id = upd.get("update_id")
                            if isinstance(upd_id, int):
                                # Persisted before the update runs: a crash mid-task never replays it.
                                self.last_update_id = upd_id
                                self._save_offset(upd_id)
                            self.process_update(upd)
                    except TelegramAuthError as auth_exc:
                        self.log(f"{auth_exc}; check the bot token. Stopping.", level="ERROR")
                        exit_code = EXIT_CONFIG
                        break
                    except (urllib.error.URLError, OSError, ValueError, RuntimeError, TimeoutError) as poll_exc:
                        # Exponential backoff, capped. [bug--runner-daemon-lifecycle-safety] REQ-7
                        failures += 1
                        delay = min(self.poll_interval * (2 ** (failures - 1)), MAX_POLL_BACKOFF_SECONDS)
                        hint = (" (HTTP 409: another poller or a webhook holds this bot token)"
                                if "409" in str(poll_exc) else "")
                        self.log(f"Telegram polling warning: {poll_exc}{hint}; retrying in {delay:.0f}s",
                                 level="WARNING")
                        self._sleep(delay)
                else:
                    # Standby idle heartbeat mode
                    self._sleep(self.poll_interval)

        except KeyboardInterrupt:
            self.log("KeyboardInterrupt received; terminating runner loop...")
        finally:
            self.log("Runner daemon shutting down...")
            self._finish_worker()
            remove_pid(self.repo_root)
            final_state = load_daemon_state(self.repo_root)
            final_state["status"] = "stopped"
            final_state["current_task"] = None
            save_daemon_state(self.repo_root, final_state)
            self.log("Runner daemon stopped cleanly.")

        return exit_code

    def _finish_worker(self) -> None:
        """At shutdown, give a running task `stop_grace_seconds` to end, telling its chat."""
        worker = self._worker
        if worker is None or not worker.is_alive():
            return
        task, chat = self.current_task, self._task_chat
        self.log(f"Waiting up to {self.stop_grace_seconds:.0f}s for task '{task}' before exiting...", level="WARNING")
        if chat is not None:
            self._send_telegram(chat, f"Runner is stopping; task '{task}' may be interrupted.")
        worker.join(timeout=self.stop_grace_seconds)
        if worker.is_alive():
            self.log(f"Task '{task}' still running at shutdown; its claim expires by TTL.", level="WARNING")


def start_daemon(
    repo_root: str,
    poll_interval: Optional[float] = None,
    port: Optional[int] = None,
    use_worktree: bool = False,
    dry_run: bool = False,
    foreground: bool = False,
) -> int:
    """Start runner daemon in foreground or detached background process."""
    status = get_daemon_status(repo_root)
    if status.get("running"):
        pid = status.get("pid")
        print(f"[Error] Runner daemon is already running (PID {pid}).", file=sys.stderr)
        print("Run 'along daemon status' or 'along daemon stop'.", file=sys.stderr)
        return 1

    if foreground:
        daemon = RunnerDaemon(
            repo_root=repo_root,
            poll_interval=poll_interval,
            port=port,
            use_worktree=use_worktree,
            dry_run=dry_run,
            log_to_stdout=True,
        )
        return daemon.run()

    # Daemonized background execution: the engine next to this alongkit package, never a
    # `scripts/along_daemon.py` the target repository happens to carry. REQ-8
    daemon_script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "along_daemon.py")

    cmd = [
        sys.executable,
        daemon_script,
        "start",
        "--foreground",
    ]
    if poll_interval is not None:
        cmd.extend(["--poll-interval", str(poll_interval)])
    if port is not None:
        cmd.extend(["--port", str(port)])
    if use_worktree:
        cmd.append("--worktree")
    if dry_run:
        cmd.append("--dry-run")

    env = proc.child_env()

    if os.name == "nt":
        # Windows detached process creation flags
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        DETACHED_PROCESS = 0x00000008
        CREATE_NO_WINDOW = 0x08000000
        p = subprocess.Popen(
            cmd,
            cwd=repo_root,
            env=env,
            creationflags=CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS | CREATE_NO_WINDOW,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        # POSIX detached session
        p = subprocess.Popen(
            cmd,
            cwd=repo_root,
            env=env,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # Wait briefly to confirm PID registration
    deadline = time.time() + 5.0
    spawned_pid = None
    while time.time() < deadline:
        st = get_daemon_status(repo_root)
        if st.get("running"):
            spawned_pid = st.get("pid")
            break
        time.sleep(0.2)

    if spawned_pid:
        print(f"-> Runner daemon started in background (PID {spawned_pid}).")
        print("Run 'along daemon status' or 'along daemon logs -f' to monitor.")
        return 0
    exit_status = p.poll()
    if exit_status is not None:
        print(f"[Error] Runner daemon exited during startup (exit code {exit_status}). "
              "See 'along daemon logs'.", file=sys.stderr)
        return 1
    print(f"-> Runner daemon process spawned (PID {p.pid}), still initializing; "
          "check 'along daemon status'.", file=sys.stderr)
    return 0


__all__ = [
    "DEFAULT_MAX_COMMAND_AGE",
    "DEFAULT_POLL_INTERVAL",
    "DEFAULT_TIMEOUT_SEC",
    "EXIT_CONFIG",
    "RunnerDaemon",
    "TelegramAuthError",
    "TelegramClient",
    "acquire_pid_file",
    "append_daemon_log",
    "get_daemon_dir",
    "get_daemon_status",
    "get_log_file",
    "get_pid_file",
    "get_state_file",
    "is_daemon_process",
    "is_pid_alive",
    "is_sender_authorized",
    "load_daemon_state",
    "parse_telegram_command",
    "process_identity",
    "read_pid",
    "read_pid_record",
    "remove_pid",
    "resolve_daemon_config",
    "save_daemon_state",
    "start_daemon",
    "stop_daemon",
    "tail_daemon_logs",
    "terminate_pid",
    "write_pid",
]
