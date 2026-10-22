#!/usr/bin/env python3
"""
alongkit.commands.brief - Modular CLI command router for along brief.

Generates deterministic, compact, size-bounded prompt payload for cross-runtime role execution.
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

from .. import handoff, repo


def handle_brief_command(repo_root: str, args: List[str]) -> int:
    """CLI handler for `along brief <slug> --role <role>`."""
    parser = argparse.ArgumentParser(
        prog="along brief",
        description="Generate deterministic, compact handoff brief for role execution.",
    )
    parser.add_argument("slug", nargs="?", help="Issue slug or canonical key")
    parser.add_argument(
        "--role",
        required=False,
        type=str,
        help="Target execution role (scout, architect, implementer, reviewer)",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=handoff.DEFAULT_BRIEF_MAX_BYTES,
        help=f"Maximum byte size of generated brief (default: {handoff.DEFAULT_BRIEF_MAX_BYTES})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output payload as a structured JSON object",
    )

    if not args or args[0] in ("-h", "--help", "help"):
        parser.print_help()
        return 0

    parsed = parser.parse_args(args)

    if not parsed.slug:
        print("[Error] along brief requires an issue slug.", file=sys.stderr)
        parser.print_usage(file=sys.stderr)
        return 1

    if not parsed.role:
        print("[Error] along brief requires --role (scout, architect, implementer, reviewer).", file=sys.stderr)
        parser.print_usage(file=sys.stderr)
        return 1

    role_clean = parsed.role.lower().strip()
    if role_clean not in handoff.SUPPORTED_BRIEF_ROLES:
        print(
            f"[Error] Unsupported role '{parsed.role}'. Expected one of: {', '.join(handoff.SUPPORTED_BRIEF_ROLES)}.",
            file=sys.stderr,
        )
        return 1

    try:
        payload = handoff.generate_brief(
            repo_root=repo_root,
            slug=parsed.slug,
            role=role_clean,
            max_bytes=parsed.max_bytes,
        )
    except (ValueError, OSError, KeyError) as exc:
        print(f"[Error] {exc}", file=sys.stderr)
        return 1

    if parsed.json:
        data = {
            "slug": parsed.slug,
            "role": role_clean,
            "bytes": len(payload.encode("utf-8")),
            "max_bytes": parsed.max_bytes,
            "payload": payload,
        }
        print(json.dumps(data, indent=2))
    else:
        print(payload)

    return 0
