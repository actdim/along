#!/usr/bin/env python3
"""
alongkit.commands.milestone - Modular CLI command router for along milestone.
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
import json
import os
import sys
from typing import List

from alongkit import entities, repo, textio
from .common import check_unknown_args, require_entity_name


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="along milestone",
        description="Milestone lifecycle management.",
        allow_abbrev=False,
    )
    sub = parser.add_subparsers(dest="subcmd")

    p_sync = sub.add_parser("sync", help="Recompute target_issues, progress_pct, and status")
    p_sync.add_argument("slug", nargs="?", default=None, help="Target milestone slug")

    p_list = sub.add_parser("list", help="List active milestones")
    p_list.add_argument("--status", "-s", default=None, help="Filter by status")
    p_list.add_argument("--json", action="store_true", help="Format as JSON")

    p_show = sub.add_parser("show", help="Show milestone details")
    p_show.add_argument("slug", help="Milestone slug or version query")
    p_show.add_argument("--json", action="store_true", help="Format as JSON")

    p_create = sub.add_parser("create", help="Create a new milestone")
    p_create.add_argument("slug", help="Milestone slug (e.g. v1.2.0-beta)")
    p_create.add_argument("--title", "-t", default=None, help="Milestone title")
    p_create.add_argument("--due", "--due-date", "-d", dest="due", default=None, help="Due date (YYYY-MM-DD)")

    return parser


def handle_milestone_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along milestone [sync|list|show|create] [args...]")
        print("  sync [<slug>]             Recompute target_issues, progress_pct, and status")
        print("  list [--status <status>] [--json]")
        print("  show <slug> [--json]")
        print("  create <slug> --title \"Title\" [--due YYYY-MM-DD]")
        sys.exit(0)

    subcmd = args[0].lower()

    if subcmd == "sync":
        parser = argparse.ArgumentParser(prog="along milestone sync", allow_abbrev=False)
        parser.add_argument("slug", nargs="?", default=None)
        parsed, extra = parser.parse_known_args(args[1:])
        check_unknown_args(extra, "along milestone sync")

        target = parsed.slug if parsed.slug and not parsed.slug.startswith("-") else None
        try:
            results = entities.sync_milestones(repo_root, target_slug=target)
        except ValueError as e:
            print(f"[Error] {e}", file=sys.stderr)
            sys.exit(1)

        print(f"-> Synchronized {len(results)} milestone(s):")
        for r in results:
            print(f"   - {r['slug']}: {r['status']} ({r['progress_pct']}%, {r['done_issues']}/{r['total_issues']} issues completed)")
        sys.exit(0)

    elif subcmd == "list":
        parser = argparse.ArgumentParser(prog="along milestone list", allow_abbrev=False)
        parser.add_argument("--status", "-s", default=None)
        parser.add_argument("--json", action="store_true")
        parsed, extra = parser.parse_known_args(args[1:])
        check_unknown_args(extra, "along milestone list")

        milestones = entities.scan_milestones(repo_root)
        if parsed.status:
            milestones = [m for m in milestones if m["status"] == parsed.status.lower()]

        if parsed.json:
            out = []
            for m in milestones:
                fm = m["frontmatter"]
                out.append({
                    "slug": m["slug"],
                    "title": m.get("title"),
                    "status": m["status"],
                    "progress_pct": fm.get("progress_pct", 0),
                    "target_issues": fm.get("target_issues", []),
                    "file_path": repo.normalize_posix(repo.safe_relpath(m["file_path"], repo_root)),
                })
            print(json.dumps(out, indent=2))
        else:
            print(f"-> Milestones in {repo_root}:")
            for m in milestones:
                fm = m["frontmatter"]
                pct = fm.get("progress_pct", 0)
                targets = fm.get("target_issues", [])
                print(f"   - [{m['status']}] {m['slug']} ({pct}%, {len(targets)} target issues)")
        sys.exit(0)

    elif subcmd == "show":
        if len(args) < 2:
            print("[Error] Usage: along milestone show <slug> [--json]", file=sys.stderr)
            sys.exit(1)
        query = args[1]
        parser = argparse.ArgumentParser(prog="along milestone show", allow_abbrev=False)
        parser.add_argument("slug")
        parser.add_argument("--json", action="store_true")
        parsed, extra = parser.parse_known_args(args[1:])
        check_unknown_args(extra, "along milestone show")

        m = entities.resolve_milestone_by_query(repo_root, parsed.slug)
        if not m:
            print(f"[Error] Milestone '{parsed.slug}' not found in .along/MILESTONES/.", file=sys.stderr)
            sys.exit(1)

        fm = m["frontmatter"]
        target_keys = fm.get("target_issues", [])
        all_issues = entities.scan_issues(repo_root, include_done=True)
        assigned = []
        for iss in all_issues:
            key = entities.canonical_key(iss["type"], iss["slug"])
            if key in target_keys or iss["slug"] in target_keys or str(iss["frontmatter"].get("milestone")) in (m["slug"], os.path.basename(m["file_path"])[:-3]):
                assigned.append(iss)

        if parsed.json:
            out = {
                "slug": m["slug"],
                "title": m["title"],
                "status": m["status"],
                "progress_pct": fm.get("progress_pct", 0),
                "due_date": fm.get("due_date"),
                "file_path": repo.normalize_posix(repo.safe_relpath(m["file_path"], repo_root)),
                "target_issues": [
                    {
                        "slug": iss["slug"],
                        "type": iss["type"],
                        "status": iss["status"],
                        "done": iss["done"],
                    }
                    for iss in assigned
                ]
            }
            print(json.dumps(out, indent=2))
        else:
            print(f"=== Milestone: {m['slug']} ===")
            print(f"Title:        {m['title']}")
            print(f"Status:       {m['status']}")
            print(f"Progress:     {fm.get('progress_pct', 0)}%")
            print(f"Due Date:     {fm.get('due_date') or 'none'}")
            print(f"Target Issues ({len(assigned)}):")
            for iss in assigned:
                box = "x" if iss["done"] else " "
                print(f"   - [{box}] ({iss['type']}) {iss['slug']} [{iss['status']}]")
        sys.exit(0)

    elif subcmd == "create":
        if len(args) < 2:
            print("[Error] Usage: along milestone create <slug> --title \"Title\" [--due YYYY-MM-DD]", file=sys.stderr)
            sys.exit(1)
        raw_slug = args[1].lower().strip()
        mslug = require_entity_name(raw_slug, "along milestone create <slug> --title \"Title\" [--due YYYY-MM-DD]")

        parser = argparse.ArgumentParser(prog="along milestone create", allow_abbrev=False)
        parser.add_argument("slug")
        parser.add_argument("--title", "-t", default=None)
        parser.add_argument("--due", "--due-date", "-d", dest="due", default=None)
        parsed, extra = parser.parse_known_args(args[1:])
        check_unknown_args(extra, "along milestone create")

        title = parsed.title or mslug.replace("-", " ").capitalize()
        due_date = parsed.due

        collision_err = entities.check_milestone_version_collision(repo_root, mslug)
        if collision_err:
            print(f"[Error] {collision_err}", file=sys.stderr)
            sys.exit(1)

        m_dir = os.path.join(repo_root, ".along", "MILESTONES")
        os.makedirs(m_dir, exist_ok=True)
        clean_slug = mslug[:-3] if mslug.endswith(".md") else mslug
        target_file = os.path.join(m_dir, f"{clean_slug}.md")
        if os.path.exists(target_file):
            print(f"[Error] Milestone file already exists: {target_file}", file=sys.stderr)
            sys.exit(1)

        from alongkit.version import CURRENT_PROTOCOL_VERSION
        from datetime import timezone
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        due_val = f'"{due_date}"' if due_date else "null"
        content = (
            "---\n"
            "protocol: along\n"
            f'protocol_version: "{CURRENT_PROTOCOL_VERSION}"\n'
            f"slug: {clean_slug}\n"
            f'title: "{title}"\n'
            "status: open\n"
            f"due_date: {due_val}\n"
            f"created: {today_str}\n"
            "target_issues: []\n"
            "progress_pct: 0\n"
            "---\n\n"
            f"# Milestone: {title}\n\n"
            "## Intent\n\n"
            "## Target Scope\n\n"
            f"## Definition of Done for {clean_slug}\n"
        )
        textio.write_text(target_file, content, newline="\n")
        print(f"-> Created milestone: .along/MILESTONES/{clean_slug}.md")
        sys.exit(0)

    else:
        print(f"[Error] Unknown milestone subcommand '{subcmd}'. Run 'along milestone --help'.", file=sys.stderr)
        sys.exit(1)
