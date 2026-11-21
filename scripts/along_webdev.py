#!/usr/bin/env python3
"""along_webdev.py - Self-contained web development, browser execution, and test substrate.

Usage:
  along webdev bootstrap [--status] [--download] [--version VER]
  along webdev limits
  along webdev schema
  along webdev serve up|status|logs|down [options]
  along webdev session start|step|batch|save|stop|status [options]
  along webdev run <scenario> [options]
  along webdev shot --url <url> --out <path> [options]
  along webdev checklist compile <file|issue-key> [options]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap

# Ensure core dependencies
bootstrap.ensure_deps()

from alongkit import repo
from alongkit.webdev import browser, cft


def handle_bootstrap(args: argparse.Namespace) -> int:
    """Handle along webdev bootstrap command."""
    repo_root = repo.find_repo_root()
    ver = args.version or cft.DEFAULT_CFT_VERSION

    if args.status:
        st = cft.status(repo_root=repo_root, version=ver)
        if args.json:
            print(json.dumps(st, indent=2))
        else:
            print("=== Chrome for Testing (CfT) Runtime Status ===")
            print(f"  Platform:    {st['platform']}")
            print(f"  Version:     {st['version']}")
            print(f"  Cached:      {'yes' if st['cached'] else 'no'}")
            print(f"  Cache Dir:   {st['cache_dir']}")
            print(f"  Binary:      {st['path'] or 'not installed'}")
            print(f"  Available:   {'yes' if st['available'] else 'no'}")
            if st["custom_path"]:
                print(f"  Custom Path: {st['custom_path']}")
        return 0 if st["available"] else 1

    if args.download or not args.status:
        try:
            path = cft.download_cft(version=ver, quiet=args.quiet)
            print(f"-> CfT {ver} ready at: {path}")
            return 0
        except (OSError, RuntimeError) as exc:
            print(f"[Error] Failed to bootstrap CfT: {exc}", file=sys.stderr)
            return 1

    return 0


def handle_limits(args: argparse.Namespace) -> int:
    """Print declared platform limits and emulation substitutes (REQ-12)."""
    limits = [
        {
            "id": "platform-limit:mobile-virtual-keyboard",
            "name": "Mobile Virtual Keyboard",
            "reason": "OS-level soft keyboard cannot be directly actuated or visually captured.",
            "substitute": "visual_viewport: {height: <px>} resize step to approximate layout compression.",
        },
        {
            "id": "platform-limit:os-media-flyout",
            "name": "OS Media Flyout / Lock-Screen Controls",
            "reason": "System-level media controls outside browser window context.",
            "substitute": "spy: {target: 'navigator.mediaSession.setPositionState'} to verify dispatched metadata.",
        },
        {
            "id": "platform-limit:native-file-dialog",
            "name": "Native OS File Dialogs",
            "reason": "Host file picker dialogs cannot be automated via standard DOM events.",
            "substitute": "upload: {locator: <file_input>, generate: {...}} step directly targeting input[type=file].",
        },
        {
            "id": "platform-limit:push-notifications",
            "name": "System Push Notifications",
            "reason": "OS notification center delivery outside browser process.",
            "substitute": "Service worker message event inspection or route interception.",
        },
    ]

    if getattr(args, "json", False):
        print(json.dumps(limits, indent=2))
    else:
        print("=== Declared WebDev Platform Limits (REQ-12) ===")
        for lim in limits:
            print(f"- {lim['id']}: {lim['name']}")
            print(f"    Reason:     {lim['reason']}")
            print(f"    Substitute: {lim['substitute']}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="along webdev",
        description="Along WebDev & Browser Execution Substrate.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="WebDev subcommands")

    # bootstrap
    p_boot = subparsers.add_parser("bootstrap", help="Provision or inspect Portable CfT runtime")
    p_boot.add_argument("--status", action="store_true", help="Inspect CfT cache status without downloading")
    p_boot.add_argument("--download", action="store_true", help="Download and unpack CfT archive")
    p_boot.add_argument("--version", default=None, help="Specific CfT version to check or download")
    p_boot.add_argument("--json", action="store_true", help="Emit machine-readable JSON status")
    p_boot.add_argument("-q", "--quiet", action="store_true", help="Suppress progress output")

    # limits
    p_limits = subparsers.add_parser("limits", help="Show declared platform limits and emulation substitutes")
    p_limits.add_argument("--json", action="store_true", help="Emit JSON list of limits")

    # schema
    p_schema = subparsers.add_parser("schema", help="Print declarative YAML/JSON scenario schema")

    # serve
    p_serve = subparsers.add_parser("serve", help="Manage application dev services lifecycle")
    p_serve.add_argument("action", choices=["up", "status", "logs", "down"], help="Service action")
    p_serve.add_argument("services", nargs="*", help="Service names (defaults to all)")
    p_serve.add_argument("--tail", type=int, default=40, help="Lines of logs to tail")
    p_serve.add_argument("--grep", default=None, help="Regex to filter service logs")
    p_serve.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    # session
    p_session = subparsers.add_parser("session", help="Interactive browser session daemon")
    p_session.add_argument("action", choices=["start", "step", "batch", "save", "stop", "status", "_worker"], help="Session action")
    p_session.add_argument("--issue", default=None, help="Issue key to attribute session")
    p_session.add_argument("--headed", action="store_true", help="Launch browser in headed mode")
    p_session.add_argument("--as", dest="save_as", default=None, help="Output scenario path for save")
    p_session.add_argument("--step", default=None, help="JSON or YAML step payload for step")
    p_session.add_argument("--batch", default=None, help="JSON or YAML array of steps for batch")
    p_session.add_argument("--json", action="store_true", help="Emit JSON output")

    # run
    p_run = subparsers.add_parser("run", help="Run Playwright script or declarative YAML scenario")
    p_run.add_argument("scenario", help="Path to scenario file (.yaml/.json) or test script")
    p_run.add_argument("--issue", default=None, help="Bound issue key to attribute results")
    p_run.add_argument("--check", action="append", default=[], help="Run only specified check IDs")
    p_run.add_argument("--matrix", action="append", default=[], help="Filter matrix (key=val)")
    p_run.add_argument("--headed", action="store_true", help="Run browser in visible (headed) mode")
    p_run.add_argument("--file-failures", action="store_true", help="Auto-file bug issues for failed checks")
    p_run.add_argument("--keep-evidence", default=None, help="Export evidence screenshots to tracked directory")
    p_run.add_argument("--publish", default=None, help="Publish report destination (sharepoint|s3|local)")
    p_run.add_argument("--json", action="store_true", help="Emit JSON result summary")

    # shot
    p_shot = subparsers.add_parser("shot", help="Quick visual proof screenshot of a web route")
    p_shot.add_argument("--url", required=True, help="URL to capture")
    p_shot.add_argument("--out", required=True, help="Output screenshot path")
    p_shot.add_argument("--issue", default=None, help="Issue key attribution")
    p_shot.add_argument("--viewport", default="desktop-1440x900", help="Viewport preset or WxH")
    p_shot.add_argument("--theme", choices=["light", "dark"], default="light", help="Color scheme")

    # checklist
    p_check = subparsers.add_parser("checklist", help="Natural-language checklist compiler")
    p_check.add_argument("action", choices=["compile"], help="Checklist action")
    p_check.add_argument("target", help="Markdown checklist file path or issue key")
    p_check.add_argument("--out", default=None, help="Output scenario YAML path")
    p_check.add_argument("--json", action="store_true", help="Emit JSON output")

    # mcp
    subparsers.add_parser("mcp", help="Run stdio Model Context Protocol (MCP) server")

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if not args.subcommand:
        parser.print_help()
        return 0

    if args.subcommand == "bootstrap":
        return handle_bootstrap(args)

    if args.subcommand == "limits":
        return handle_limits(args)

    if args.subcommand == "schema":
        try:
            from alongkit.webdev import schema
            print(schema.get_scenario_schema_json())
            return 0
        except ImportError:
            print("[Error] Schema module not yet loaded.", file=sys.stderr)
            return 2

    if args.subcommand == "serve":
        from alongkit.webdev import services
        return services.handle_serve_cli(args)

    if args.subcommand == "session":
        from alongkit.webdev import daemon
        return daemon.handle_session_cli(args)

    if args.subcommand == "run":
        from alongkit.webdev import runner
        return runner.handle_run_cli(args)

    if args.subcommand == "shot":
        from alongkit.webdev import runner
        return runner.handle_shot_cli(args)

    if args.subcommand == "checklist":
        from alongkit.webdev import checklist
        return checklist.handle_checklist_cli(args)

    if args.subcommand == "mcp":
        from alongkit.webdev import mcp_server
        return mcp_server.run_stdio_server()

    print(f"[Error] Unknown subcommand: {args.subcommand}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
