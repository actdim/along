#!/usr/bin/env python3
"""
alongkit.commands.env - Modular CLI command router for along env.
[debt--along-exec-argparse-migration]
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
from typing import List

from alongkit import environment
from .common import check_unknown_args, require_entity_name


def build_parser() -> argparse.ArgumentParser:
    """Build root parser for along env subcommands."""
    parser = argparse.ArgumentParser(
        prog="along env",
        description="Isolated Docker environment manager for autonomous agent runs.",
        allow_abbrev=False,
    )
    sub = parser.add_subparsers(dest="subcmd")

    p_up = sub.add_parser("up", help="Create and start an isolated Docker environment", allow_abbrev=False)
    p_up.add_argument("name", help="Environment name")
    p_up.add_argument("--repo", default=None, help="Git repository URL")
    p_up.add_argument("--branch", default=None, help="Git branch name")
    p_up.add_argument("--dir", default=None, help="Base environments directory or target env path")

    p_down = sub.add_parser("down", help="Stop isolated Docker environment", allow_abbrev=False)
    p_down.add_argument("name", help="Environment name")
    p_down.add_argument("--dir", default=None, help="Base environments directory or target env path")

    p_status = sub.add_parser("status", help="Show environment status", allow_abbrev=False)
    p_status.add_argument("name", nargs="?", default=None, help="Environment name (optional)")
    p_status.add_argument("--dir", default=None, help="Base environments directory or target env path")
    p_status.add_argument("--json", action="store_true", help="Format output as JSON")

    p_logs = sub.add_parser("logs", help="View container logs", allow_abbrev=False)
    p_logs.add_argument("name", help="Environment name")
    p_logs.add_argument("-f", "--follow", action="store_true", help="Follow log output")
    p_logs.add_argument("--tail", type=int, default=None, help="Number of lines to show from the end of the logs")
    p_logs.add_argument("--dir", default=None, help="Base environments directory or target env path")

    p_shell = sub.add_parser("shell", help="Open an interactive shell in the container", allow_abbrev=False)
    p_shell.add_argument("name", help="Environment name")
    p_shell.add_argument("--dir", default=None, help="Base environments directory or target env path")

    p_update = sub.add_parser("update", help="Update image and refresh environment", allow_abbrev=False)
    p_update.add_argument("name", help="Environment name")
    p_update.add_argument("--dir", default=None, help="Base environments directory or target env path")

    return parser


def handle_env_command(repo_root: str, args: List[str]):
    """Unified entry point for along env subcommands."""
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along env [up|down|status|logs|shell|update] [args...]")
        print("")
        print("Isolated Docker Environment Commands:")
        print("  up       <name> [--repo <url>] [--branch <branch>] [--dir <path>]")
        print("  down     <name> [--dir <path>]")
        print("  status   [<name>] [--dir <path>] [--json]")
        print("  logs     <name> [-f] [--tail <n>] [--dir <path>]")
        print("  shell    <name> [--dir <path>]")
        print("  update   <name> [--dir <path>]")
        sys.exit(0)

    subcmd = args[0].lower().strip()
    sub_args = args[1:]

    valid_subcmds = {"up", "down", "status", "logs", "shell", "update"}
    if subcmd not in valid_subcmds:
        print(f"[Error] Unknown subcommand '{subcmd}'. Run 'along env --help' for usage.", file=sys.stderr)
        sys.exit(2)

    # 1. UP
    if subcmd == "up":
        if not sub_args or sub_args[0] in ("-h", "--help"):
            print("Usage: along env up <name> [--repo <url>] [--branch <branch>] [--dir <path>]")
            sys.exit(0)

        require_entity_name(sub_args[0], "along env up <name> [--repo <url>] [--branch <branch>] [--dir <path>]")

        parser = argparse.ArgumentParser(prog="along env up", allow_abbrev=False)
        parser.add_argument("name")
        parser.add_argument("--repo", default=None)
        parser.add_argument("--branch", default=None)
        parser.add_argument("--dir", default=None)
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along env up")

        res = environment.env_up(
            name=parsed.name,
            repo_url=parsed.repo,
            branch=parsed.branch,
            base_dir=parsed.dir,
        )
        print(f"-> Created isolated environment: {res['name']}")
        print(f"   Directory: {res['path']}")
        print(f"   Container: {res['container_name']}")
        print(f"   Status:    {res['status']}")
        if res.get("error"):
            print(f"   Notice:    {res['error']}")
        sys.exit(0)

    # 2. DOWN
    if subcmd == "down":
        if not sub_args or sub_args[0] in ("-h", "--help"):
            print("Usage: along env down <name> [--dir <path>]")
            sys.exit(0)

        require_entity_name(sub_args[0], "along env down <name> [--dir <path>]")

        parser = argparse.ArgumentParser(prog="along env down", allow_abbrev=False)
        parser.add_argument("name")
        parser.add_argument("--dir", default=None)
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along env down")

        try:
            res = environment.env_down(name=parsed.name, base_dir=parsed.dir)
            print(f"-> Stopped isolated environment: {res['name']}")
            if res.get("error"):
                print(f"   Notice: {res['error']}")
            sys.exit(0)
        except FileNotFoundError as exc:
            print(f"[Error] {exc}", file=sys.stderr)
            sys.exit(1)

    # 3. STATUS
    if subcmd == "status":
        if any(a in ("-h", "--help") for a in sub_args):
            print("Usage: along env status [<name>] [--dir <path>] [--json]")
            sys.exit(0)

        parser = argparse.ArgumentParser(prog="along env status", allow_abbrev=False)
        parser.add_argument("name", nargs="?", default=None)
        parser.add_argument("--dir", default=None)
        parser.add_argument("--json", action="store_true")
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along env status")

        if parsed.name and parsed.name.startswith("-"):
            require_entity_name(parsed.name, "along env status [<name>] [--dir <path>] [--json]")

        res = environment.env_status(name=parsed.name, base_dir=parsed.dir)

        if parsed.json:
            print(json.dumps(res, indent=2))
            sys.exit(0)

        if parsed.name:
            if not isinstance(res, dict):
                sys.exit(1)
            print(f"=== Along Environment: {res['name']} ===")
            print(f"  Path:        {res.get('path', '')}")
            print(f"  Container:   {res.get('container_name', '')}")
            print(f"  Status:      {res.get('status', 'unknown')}")
            print(f"  Repository:  {res.get('repo', '') or '(none)'}")
            print(f"  Branch:      {res.get('branch', '') or '(none)'}")
            runtimes = ", ".join(res.get("runtimes", []))
            print(f"  Runtimes:    {runtimes or 'default'}")
            print(f"  Secrets:     {'present' if res.get('has_secrets') else 'missing'}")
            print(f"  Compose:     {'present' if res.get('has_compose') else 'missing'}")
            print(f"  gVisor:      {'enabled' if res.get('gvisor') else 'disabled'}")
        else:
            if not isinstance(res, list) or not res:
                print("No isolated environments configured.")
                sys.exit(0)
            print("=== Along Isolated Environments ===")
            print(f"{'NAME':<16} {'STATUS':<12} {'RUNTIMES':<24} {'BRANCH':<12} REPOSITORY")
            print("-" * 78)
            for item in res:
                runtimes = ", ".join(item.get("runtimes", []))[:22]
                repo_str = item.get("repo", "") or "-"
                branch_str = item.get("branch", "") or "-"
                print(f"{item['name']:<16} {item.get('status', 'unknown'):<12} {runtimes:<24} {branch_str:<12} {repo_str}")
        sys.exit(0)

    # 4. LOGS
    if subcmd == "logs":
        if not sub_args or sub_args[0] in ("-h", "--help"):
            print("Usage: along env logs <name> [-f] [--tail <n>] [--dir <path>]")
            sys.exit(0)

        require_entity_name(sub_args[0], "along env logs <name> [-f] [--tail <n>] [--dir <path>]")

        parser = argparse.ArgumentParser(prog="along env logs", allow_abbrev=False)
        parser.add_argument("name")
        parser.add_argument("-f", "--follow", action="store_true")
        parser.add_argument("--tail", type=int, default=None)
        parser.add_argument("--dir", default=None)
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along env logs")

        code = environment.env_logs(
            name=parsed.name,
            follow=parsed.follow,
            tail=parsed.tail,
            base_dir=parsed.dir,
        )
        sys.exit(code)

    # 5. SHELL
    if subcmd == "shell":
        if not sub_args or sub_args[0] in ("-h", "--help"):
            print("Usage: along env shell <name> [--dir <path>]")
            sys.exit(0)

        require_entity_name(sub_args[0], "along env shell <name> [--dir <path>]")

        parser = argparse.ArgumentParser(prog="along env shell", allow_abbrev=False)
        parser.add_argument("name")
        parser.add_argument("--dir", default=None)
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along env shell")

        code = environment.env_shell(name=parsed.name, base_dir=parsed.dir)
        sys.exit(code)

    # 6. UPDATE
    if subcmd == "update":
        if not sub_args or sub_args[0] in ("-h", "--help"):
            print("Usage: along env update <name> [--dir <path>]")
            sys.exit(0)

        require_entity_name(sub_args[0], "along env update <name> [--dir <path>]")

        parser = argparse.ArgumentParser(prog="along env update", allow_abbrev=False)
        parser.add_argument("name")
        parser.add_argument("--dir", default=None)
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along env update")

        try:
            res = environment.env_update(name=parsed.name, base_dir=parsed.dir)
            print(f"-> Updated isolated environment: {res['name']}")
            if res.get("error"):
                print(f"   Notice: {res['error']}")
            sys.exit(0)
        except FileNotFoundError as exc:
            print(f"[Error] {exc}", file=sys.stderr)
            sys.exit(1)
