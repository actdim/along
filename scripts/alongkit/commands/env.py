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
from alongkit.exceptions import CommandError, ValidationError
from .common import check_unknown_args, require_entity_name


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
        return 0

    subcmd = args[0].lower().strip()
    sub_args = args[1:]

    valid_subcmds = {"up", "down", "status", "logs", "shell", "update"}
    if subcmd not in valid_subcmds:
        raise ValidationError(f"Unknown subcommand '{subcmd}'. Run 'along env --help' for usage.")

    # 1. UP
    if subcmd == "up":
        if not sub_args or sub_args[0] in ("-h", "--help"):
            print("Usage: along env up <name> [--repo <url>] [--branch <branch>] [--dir <path>]")
            return 0

        require_entity_name(sub_args[0], "along env up <name> [--repo <url>] [--branch <branch>] [--dir <path>]")

        parser = argparse.ArgumentParser(prog="along env up", allow_abbrev=False)
        parser.add_argument("name")
        parser.add_argument("--repo", default=None)
        parser.add_argument("--branch", default=None)
        parser.add_argument("--dir", default=None)
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along env up")

        try:
            res = environment.env_up(
                name=parsed.name,
                repo_url=parsed.repo,
                branch=parsed.branch,
                base_dir=parsed.dir,
            )
            if res.get("error"):
                raise CommandError(str(res["error"]))
            print(f"-> Created isolated environment: {res['name']}")
            print(f"   Directory: {res['path']}")
            print(f"   Container: {res['container_name']}")
            print(f"   Status:    {res['status']}")
            return 0
        except environment.EnvConfigError as exc:
            raise CommandError(str(exc))
        except ValueError as exc:
            raise ValidationError(str(exc))

    # 2. DOWN
    if subcmd == "down":
        if not sub_args or sub_args[0] in ("-h", "--help"):
            print("Usage: along env down <name> [--dir <path>]")
            return 0

        require_entity_name(sub_args[0], "along env down <name> [--dir <path>]")

        parser = argparse.ArgumentParser(prog="along env down", allow_abbrev=False)
        parser.add_argument("name")
        parser.add_argument("--dir", default=None)
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along env down")

        try:
            res = environment.env_down(name=parsed.name, base_dir=parsed.dir)
            if res.get("error"):
                raise CommandError(str(res["error"]))
            print(f"-> Stopped isolated environment: {res['name']}")
            return 0
        except environment.EnvConfigError as exc:
            raise CommandError(str(exc))
        except FileNotFoundError as exc:
            raise CommandError(str(exc))
        except ValueError as exc:
            raise ValidationError(str(exc))

    # 3. STATUS
    if subcmd == "status":
        if any(a in ("-h", "--help") for a in sub_args):
            print("Usage: along env status [<name>] [--dir <path>] [--json]")
            return 0

        parser = argparse.ArgumentParser(prog="along env status", allow_abbrev=False)
        parser.add_argument("name", nargs="?", default=None)
        parser.add_argument("--dir", default=None)
        parser.add_argument("--json", action="store_true")
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along env status")

        if parsed.name and parsed.name.startswith("-"):
            require_entity_name(parsed.name, "along env status [<name>] [--dir <path>] [--json]")

        try:
            res = environment.env_status(name=parsed.name, base_dir=parsed.dir)
        except environment.EnvConfigError as exc:
            raise CommandError(str(exc))
        except ValueError as exc:
            raise ValidationError(str(exc))

        if parsed.json:
            print(json.dumps(res, indent=2))
            return 0

        if parsed.name:
            if not isinstance(res, dict):
                return 1
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
                return 0
            print("=== Along Isolated Environments ===")
            print(f"{'NAME':<16} {'STATUS':<12} {'RUNTIMES':<24} {'BRANCH':<12} REPOSITORY")
            print("-" * 78)
            for item in res:
                runtimes = ", ".join(item.get("runtimes", []))[:22]
                repo_str = item.get("repo", "") or "-"
                branch_str = item.get("branch", "") or "-"
                print(f"{item['name']:<16} {item.get('status', 'unknown'):<12} {runtimes:<24} {branch_str:<12} {repo_str}")
        return 0

    # 4. LOGS
    if subcmd == "logs":
        if not sub_args or sub_args[0] in ("-h", "--help"):
            print("Usage: along env logs <name> [-f] [--tail <n>] [--dir <path>]")
            return 0

        require_entity_name(sub_args[0], "along env logs <name> [-f] [--tail <n>] [--dir <path>]")

        parser = argparse.ArgumentParser(prog="along env logs", allow_abbrev=False)
        parser.add_argument("name")
        parser.add_argument("-f", "--follow", action="store_true")
        parser.add_argument("--tail", type=int, default=None)
        parser.add_argument("--dir", default=None)
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along env logs")

        try:
            code = environment.env_logs(
                name=parsed.name,
                follow=parsed.follow,
                tail=parsed.tail,
                base_dir=parsed.dir,
            )
            return code
        except environment.EnvConfigError as exc:
            raise CommandError(str(exc))
        except ValueError as exc:
            raise ValidationError(str(exc))

    # 5. SHELL
    if subcmd == "shell":
        if not sub_args or sub_args[0] in ("-h", "--help"):
            print("Usage: along env shell <name> [--dir <path>]")
            return 0

        require_entity_name(sub_args[0], "along env shell <name> [--dir <path>]")

        parser = argparse.ArgumentParser(prog="along env shell", allow_abbrev=False)
        parser.add_argument("name")
        parser.add_argument("--dir", default=None)
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along env shell")

        try:
            code = environment.env_shell(name=parsed.name, base_dir=parsed.dir)
            return code
        except environment.EnvConfigError as exc:
            raise CommandError(str(exc))
        except ValueError as exc:
            raise ValidationError(str(exc))

    # 6. UPDATE
    if subcmd == "update":
        if not sub_args or sub_args[0] in ("-h", "--help"):
            print("Usage: along env update <name> [--dir <path>]")
            return 0

        require_entity_name(sub_args[0], "along env update <name> [--dir <path>]")

        parser = argparse.ArgumentParser(prog="along env update", allow_abbrev=False)
        parser.add_argument("name")
        parser.add_argument("--dir", default=None)
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along env update")

        try:
            res = environment.env_update(name=parsed.name, base_dir=parsed.dir)
            if res.get("error"):
                raise CommandError(str(res["error"]))
            print(f"-> Updated isolated environment: {res['name']}")
            return 0
        except environment.EnvConfigError as exc:
            raise CommandError(str(exc))
        except FileNotFoundError as exc:
            raise CommandError(str(exc))
        except ValueError as exc:
            raise ValidationError(str(exc))
