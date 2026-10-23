#!/usr/bin/env python3
"""
alongkit.commands.daemon - Modular CLI command router for along daemon.
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: python .along/scripts/test.py"
    )

import argparse
import json
import sys
from typing import List, Optional

from alongkit import daemon
from .common import check_unknown_args


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line parser for along daemon."""
    parser = argparse.ArgumentParser(
        prog="along daemon",
        description="VPS host runner daemon and Telegram ingress dispatcher.",
        allow_abbrev=False,
    )
    sub = parser.add_subparsers(dest="subcmd")

    # along daemon start
    p_start = sub.add_parser("start", help="Start background runner daemon")
    p_start.add_argument("--poll-interval", type=float, default=None, help="Polling interval in seconds (default: 5.0)")
    p_start.add_argument("--port", type=int, default=None, help="Local network port (reserved for ingress/metrics)")
    p_start.add_argument("--worktree", action="store_true", help="Execute runs in isolated git worktrees")
    p_start.add_argument("--dry-run", action="store_true", help="Simulate execution without modifying state")
    p_start.add_argument("--foreground", "-F", action="store_true", help="Run daemon in foreground (blocking)")

    # along daemon stop
    sub.add_parser("stop", help="Stop running background runner daemon")

    # along daemon status
    p_status = sub.add_parser("status", help="Show runner daemon status and active task")
    p_status.add_argument("--json", action="store_true", help="Format output as JSON")

    # along daemon logs
    p_logs = sub.add_parser("logs", help="View or tail daemon execution logs")
    p_logs.add_argument("-f", "--follow", action="store_true", help="Follow log output in real time")
    p_logs.add_argument("--tail", "-n", type=int, default=50, help="Number of trailing lines to view (default: 50)")

    return parser


def format_status_text(status: dict) -> str:
    """Format daemon status dict for human-readable terminal display."""
    running = status.get("running", False)
    pid = status.get("pid")
    status_str = status.get("status", "unknown")
    uptime = status.get("uptime_seconds")

    if uptime is not None:
        mins, secs = divmod(int(uptime), 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            uptime_str = f"{hours}h {mins}m {secs}s"
        elif mins > 0:
            uptime_str = f"{mins}m {secs}s"
        else:
            uptime_str = f"{secs}s"
    else:
        uptime_str = "N/A"

    current_task = status.get("current_task") or "None (idle)"
    worktree_mode = "Enabled" if status.get("worktree") else "Disabled"
    poll_interval = f"{status.get('poll_interval', 5.0)}s"

    lines = [
        "Runner Daemon Status:",
        f"  Running:             {'Yes' if running else 'No'}",
        f"  PID:                 {pid if pid is not None else 'None'}",
        f"  Process State:       {status_str}",
        f"  Uptime:              {uptime_str}",
        f"  Active Task:         {current_task}",
        f"  Worktree Isolation:  {worktree_mode}",
        f"  Poll Interval:       {poll_interval}",
    ]
    if status.get("last_poll_at"):
        lines.append(f"  Last Polled At:      {status.get('last_poll_at')}")

    return "\n".join(lines)


def handle_daemon_command(repo_root: str, args: List[str]) -> int:
    """CLI handler for `along daemon [subcmd] [options]`."""
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along daemon [start|stop|status|logs] [options]")
        print("Subcommands:")
        print("  start   [--poll-interval <sec>] [--port <port>] [--worktree] [--dry-run] [--foreground]")
        print("  stop")
        print("  status  [--json]")
        print("  logs    [-f] [--tail <n>]")
        return 0

    parser = build_parser()
    parsed, extra = parser.parse_known_args(args)
    check_unknown_args(extra, f"along daemon {parsed.subcmd or ''}".strip())

    subcmd = parsed.subcmd

    if subcmd == "start":
        return daemon.start_daemon(
            repo_root=repo_root,
            poll_interval=parsed.poll_interval,
            port=parsed.port,
            use_worktree=parsed.worktree,
            dry_run=parsed.dry_run,
            foreground=parsed.foreground,
        )

    elif subcmd == "stop":
        ok, msg = daemon.stop_daemon(repo_root)
        if ok:
            print(f"-> {msg}")
            return 0
        else:
            print(f"[Error] {msg}", file=sys.stderr)
            return 1

    elif subcmd == "status":
        status_info = daemon.get_daemon_status(repo_root)
        if parsed.json:
            print(json.dumps(status_info, indent=2))
        else:
            print(format_status_text(status_info))
        return 0 if status_info.get("running") else 1

    elif subcmd == "logs":
        daemon.tail_daemon_logs(
            repo_root=repo_root,
            lines=parsed.tail,
            follow=parsed.follow,
        )
        return 0

    else:
        parser.print_help(sys.stderr)
        return 1


__all__ = [
    "build_parser",
    "format_status_text",
    "handle_daemon_command",
]
