#!/usr/bin/env python3
"""
alongkit.commands.orchestrator - CLI command router for along orchestrate and along team.

Provides command-line dispatch for cross-runtime multi-agent supervisor loops.
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

from .. import orchestrator, repo, session


def handle_orchestrate_command(repo_root: str, args: List[str]) -> int:
    """CLI handler for `along orchestrate <slug> [options]`."""
    parser = argparse.ArgumentParser(
        prog="along orchestrate",
        description="Cross-runtime multi-agent supervisor orchestrator for tiered model workflows.",
    )
    parser.add_argument("slug", nargs="?", help="Target issue slug (defaults to active session or in-progress issue)")
    parser.add_argument("--dry-run", action="store_true", help="Preview prompt payloads and simulated runs")
    parser.add_argument("--max-retries", type=int, default=orchestrator.DEFAULT_MAX_RETRIES, help="Maximum retry attempts per step (default: 3)")
    parser.add_argument("--timeout", type=int, default=None, help="Process timeout per role execution in seconds")
    parser.add_argument("--scout", type=str, default=None, help="Runtime adapter for scout role (e.g. claude-code, opencode)")
    parser.add_argument("--architect", type=str, default=None, help="Runtime adapter for architect role")
    parser.add_argument("--implementer", type=str, default=None, help="Runtime adapter for implementer role")
    parser.add_argument("--reviewer", type=str, default=None, help="Runtime adapter for reviewer role")
    parser.add_argument("--model", type=str, default=None, help="Default model override across roles")
    parser.add_argument("--skip-scout", action="store_true", help="Skip scout research phase")
    parser.add_argument("--skip-architect", action="store_true", help="Skip architect living plan phase")
    parser.add_argument("--force", action="store_true", help="Force claim acquisition or execution restart")
    parser.add_argument("--json", action="store_true", help="Output execution results as JSON")

    if args and args[0] in ("-h", "--help", "help"):
        parser.print_help()
        return 0

    parsed = parser.parse_args(args)

    try:
        target_slug = orchestrator.resolve_orchestrator_issue(repo_root, parsed.slug)
    except ValueError as exc:
        print(f"[Error] {exc}", file=sys.stderr)
        parser.print_usage(file=sys.stderr)
        return 1

    overrides = {}
    if parsed.scout:
        overrides["scout"] = parsed.scout
    if parsed.architect:
        overrides["architect"] = parsed.architect
    if parsed.implementer:
        overrides["implementer"] = parsed.implementer
    if parsed.reviewer:
        overrides["reviewer"] = parsed.reviewer
    if parsed.model:
        overrides["model"] = parsed.model
    if parsed.timeout:
        overrides["timeout"] = parsed.timeout

    if not parsed.json:
        print(f"-> [Orchestrator] Dispatching multi-agent loop for issue '{target_slug}'...")

    result = orchestrator.run_orchestration(
        repo_root=repo_root,
        slug=target_slug,
        overrides=overrides,
        max_retries=parsed.max_retries,
        timeout=parsed.timeout,
        dry_run=parsed.dry_run,
        force=parsed.force,
        skip_scout=parsed.skip_scout,
        skip_architect=parsed.skip_architect,
    )

    if parsed.json:
        print(json.dumps(result, indent=2))
    else:
        status = result.get("status", "unknown")
        if status == "completed":
            print(f"-> [Orchestrator] Orchestration completed successfully for '{target_slug}'.")
        elif status == "needs-input":
            print(f"-> [Orchestrator] Halted: waiting for operator input (status: needs-input).")
        elif status == "blocked":
            print(f"-> [Orchestrator] Blocked: {result.get('reason')}", file=sys.stderr)
        elif status == "timeout":
            print(f"-> [Orchestrator] Timed out during {result.get('phase', 'execution')}.", file=sys.stderr)
        elif status == "failed":
            print(f"-> [Orchestrator] Orchestration failed: {result.get('reason', 'step failed')}", file=sys.stderr)
        elif status == "dry-run":
            print(f"-> [Orchestrator] Dry run for '{target_slug}': nothing was run or changed.")
            for ph in result.get("phases", []):
                where = f" step {ph['step']}" if "step" in ph else ""
                if "role" in ph:
                    brief = ph.get("brief_bytes")
                    detail = f"{ph['runtime']}, timeout {ph['timeout']}s" + (f", brief {brief} bytes" if brief else "")
                    print(f"   - {ph['phase']}{where}: {detail}")
                else:
                    print(f"   - {ph['phase']}: {ph.get('source', '')}")
        else:
            print(f"-> [Orchestrator] Finished with status '{status}'.")

    status = result.get("status")
    if status in ("completed", "needs-input", "dry-run"):
        return 0
    return 1


def handle_team_command(repo_root: str, args: List[str]) -> int:
    """CLI handler for `along team <subcommand> [args...]`."""
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along team <subcommand> [args...]")
        print("")
        print("Subcommands:")
        print("  orchestrate [<slug>] [options]   Execute cross-runtime multi-agent loop")
        print("  status      [<slug>]             Show team session status")
        return 0

    sub = args[0].lower().strip()
    if sub == "orchestrate":
        return handle_orchestrate_command(repo_root, args[1:])
    elif sub == "status":
        slug = args[1] if len(args) > 1 else None
        target_slug = slug
        if not target_slug:
            target_slug = session.get_active_session_slug(repo_root)
        if target_slug:
            st = session.load_state(repo_root, target_slug)
            if st:
                print(f"Team Session: {st.get('slug')}")
                print(f"Phase: {st.get('phase')}")
                print(f"Status: {st.get('status')}")
                print(f"Current Step: {st.get('current_step')} / {st.get('total_steps')}")
                print(f"Plan Approved: {st.get('plan_approved')}")
                return 0
        print("[Notice] No active team session found.", file=sys.stderr)
        return 1
    else:
        print(f"[Error] Unknown team subcommand '{sub}'. Expected 'orchestrate' or 'status'.", file=sys.stderr)
        return 1


__all__ = [
    "handle_orchestrate_command",
    "handle_team_command",
]
