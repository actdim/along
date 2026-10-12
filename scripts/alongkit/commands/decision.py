#!/usr/bin/env python3
"""
alongkit.commands.decision - Modular CLI command router for along decision.
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
from datetime import datetime
import os
import sys
from typing import List

from alongkit import entities, repo, textio
from .common import check_unknown_args, require_entity_name


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="along decision",
        description="Architectural Decision Record (ADR) management.",
        allow_abbrev=False,
    )
    sub = parser.add_subparsers(dest="subcmd")

    p_sync = sub.add_parser("sync", help="Recompile .along/DECISIONS.md and .along/CONSTRAINTS.md projections")
    p_sync.add_argument("--check", action="store_true", help="Check for decision conflicts without recompiling")

    for name in ("create", "add"):
        p_create = sub.add_parser(name, help="Create a modular ADR")
        p_create.add_argument("slug", help="ADR slug (kebab-case)")
        p_create.add_argument("--title", "-t", default=None, help="ADR title")
        p_create.add_argument("--context", default="", help="Context & Problem Statement")
        p_create.add_argument("--decision", default="", help="Decision Outcome")
        p_create.add_argument("--consequences", default="", help="Consequences & Trade-offs")

    return parser


def handle_decision_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along decision [create|sync] [args...]")
        print("  create <slug> --title \"Title\" --context \"Context\" --decision \"Decision\" --consequences \"Tradeoffs\"")
        print("  sync   Recompile .along/DECISIONS.md and .along/CONSTRAINTS.md projections from ADRs")
        sys.exit(0)

    subcmd = args[0].lower()
    today = datetime.now().strftime("%Y-%m-%d")

    if subcmd == "sync":
        parser = argparse.ArgumentParser(prog="along decision sync", allow_abbrev=False)
        parser.add_argument("--check", action="store_true")
        parsed, extra = parser.parse_known_args(args[1:])
        check_unknown_args(extra, "along decision sync")

        if parsed.check:
            conflicts = entities.check_decision_conflicts(repo_root)
            if conflicts:
                print("[Error] Decision conflict(s) detected [gate: decision-conflict]:", file=sys.stderr)
                for c in conflicts:
                    print(f"  - {c['message']}", file=sys.stderr)
                sys.exit(1)
            sdir = repo.state_dir(repo_root)
            con_path = os.path.join(sdir, "CONSTRAINTS.md")
            if os.path.isfile(con_path):
                con_text = textio.read_text(con_path, strict=False)
                decisions = entities.scan_decisions(repo_root)
                superseded_slugs = [d["slug"] for d in decisions if (d.get("status") or "").lower() not in entities.ACTIVE_DECISION_STATUSES]
                found_superseded = [s for s in superseded_slugs if s in con_text]
                if found_superseded:
                    print(f"[Error] CONSTRAINTS.md contains superseded decision(s): {', '.join(found_superseded)}", file=sys.stderr)
                    sys.exit(1)
            print("-> [OK] No decision conflicts detected across active ADRs.")
            sys.exit(0)

        entities.compile_decisions_board(repo_root)
        entities.sync_constraints(repo_root)
        try:
            import along_kb_sync
        except ImportError:
            along_kb_sync = None
        if along_kb_sync is not None and hasattr(along_kb_sync, "sync_decisions_to_docs"):
            try:
                along_kb_sync.sync_decisions_to_docs(repo_root)
            except (OSError, ValueError, AttributeError, RuntimeError) as exc:
                print(f"[Warning] Failed to sync decisions to docs: {exc}", file=sys.stderr)
        print("-> Recompiled .along/DECISIONS.md projection board.")
        print("-> Recompiled .along/CONSTRAINTS.md projection.")
        sys.exit(0)

    elif subcmd in ("create", "add"):
        if len(args) < 2:
            print("[Error] Usage: along decision create <slug> --title \"Title\" --context \"Why\" --decision \"What\" --consequences \"Consequences\"", file=sys.stderr)
            sys.exit(1)
        raw_slug = args[1].lstrip("#")
        slug = require_entity_name(raw_slug.lower(), "along decision create <slug> --title \"Title\"")

        parser = argparse.ArgumentParser(prog=f"along decision {subcmd}", allow_abbrev=False)
        parser.add_argument("slug")
        parser.add_argument("pos_title", nargs="?", default=None)
        parser.add_argument("--title", "-t", default=None)
        parser.add_argument("--context", default="")
        parser.add_argument("--decision", default="")
        parser.add_argument("--consequences", default="")

        parsed, extra = parser.parse_known_args(args[1:])
        check_unknown_args(extra, f"along decision {subcmd}")

        title = parsed.title or parsed.pos_title or slug.replace("-", " ").capitalize()
        context = parsed.context
        decision = parsed.decision
        consequences = parsed.consequences

        created_path = entities.create_decision_file(
            repo_root=repo_root,
            slug=slug,
            title=title,
            context=context,
            decision=decision,
            consequences=consequences,
            day=today,
            status="accepted",
        )
        rel_created = repo.normalize_posix(repo.safe_relpath(created_path, repo_root))
        print(f"-> Created modular ADR file: {rel_created}")

        # Automatically recompile projections
        entities.compile_decisions_board(repo_root)
        entities.sync_constraints(repo_root)
        try:
            import along_kb_sync
        except ImportError:
            along_kb_sync = None
        if along_kb_sync is not None and hasattr(along_kb_sync, "sync_decisions_to_docs"):
            try:
                along_kb_sync.sync_decisions_to_docs(repo_root)
            except (OSError, ValueError, AttributeError, RuntimeError) as exc:
                print(f"[Warning] Failed to sync decisions to docs: {exc}", file=sys.stderr)
        print("-> Recompiled .along/DECISIONS.md projection board.")
        print("-> Recompiled .along/CONSTRAINTS.md projection.")
        sys.exit(0)

    else:
        print(f"[Error] Unknown decision subcommand: '{subcmd}'. Run 'along decision --help'.", file=sys.stderr)
        sys.exit(1)
