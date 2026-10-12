#!/usr/bin/env python3
"""
alongkit.commands.worktree - Modular CLI command router for along worktree.
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

from alongkit import worktree
from .common import check_unknown_args, require_entity_name


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="along worktree",
        description="Isolated Git worktree management.",
        allow_abbrev=False,
    )
    sub = parser.add_subparsers(dest="subcmd")

    p_create = sub.add_parser("create", help="Create an isolated worktree")
    p_create.add_argument("slug", help="Worktree slug")
    p_create.add_argument("--branch", default=None, help="Target branch name")
    p_create.add_argument("--base-ref", default=None, help="Base commit or branch")
    p_create.add_argument("--force-cross-os", action="store_true", help="Force worktree across OS mount")

    p_remove = sub.add_parser("remove", help="Safely remove a worktree")
    p_remove.add_argument("slug", help="Worktree slug")
    p_remove.add_argument("--force", "-f", action="store_true", help="Force removal")
    p_remove.add_argument("--keep-branch", action="store_true", help="Keep the worktree git branch")

    p_merge = sub.add_parser("merge", help="Merge worktree branch back")
    p_merge.add_argument("slug", help="Worktree slug")
    p_merge.add_argument("--squash", "-s", action="store_true", help="Squash merge")

    p_list = sub.add_parser("list", help="List active worktrees")
    p_list.add_argument("--json", action="store_true", help="Format as JSON")

    p_status = sub.add_parser("status", help="Show worktree readiness status")
    p_status.add_argument("--json", action="store_true", help="Format as JSON")

    for name in ("is_supported", "is-supported", "check"):
        p_sup = sub.add_parser(name, help="Check if worktree isolation is supported")
        p_sup.add_argument("--force-cross-os", action="store_true", help="Force check across OS mount")

    sub.add_parser("gc", help="Clean up pruned worktrees and deferred deletions")
    return parser


def handle_worktree_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along worktree [create|remove|merge|list|status|gc|is_supported] [args...]")
        print("Subcommands:")
        print("  create <slug> [--branch <name>] [--base-ref <ref>] [--force-cross-os]")
        print("  remove <slug> [--force] [--keep-branch]")
        print("  merge  <slug> [--squash]")
        print("  list   [--json]")
        print("  status [--json]")
        print("  is_supported [--force-cross-os]")
        print("  gc")
        sys.exit(0)

    subcmd = args[0].lower().strip()
    sub_args = args[1:]

    if subcmd == "create":
        if not sub_args:
            print("[Error] Usage: along worktree create <slug> [--branch <name>] [--base-ref <ref>] [--force-cross-os]", file=sys.stderr)
            sys.exit(1)
        require_entity_name(sub_args[0], "along worktree create <slug> [--branch <name>] [--base-ref <ref>] [--force-cross-os]")

        parser = argparse.ArgumentParser(prog="along worktree create", allow_abbrev=False)
        parser.add_argument("slug")
        parser.add_argument("--branch", default=None)
        parser.add_argument("--base-ref", default=None)
        parser.add_argument("--force-cross-os", action="store_true")
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along worktree create")

        try:
            info = worktree.create_worktree(
                repo_root, parsed.slug,
                branch=parsed.branch,
                base_ref=parsed.base_ref,
                force_cross_os=parsed.force_cross_os,
            )
            print(f"-> Created isolated worktree: {info.path}")
            print(f"   Branch: {info.branch}")
            if info.linked_dirs:
                print(f"   Linked dependencies: {', '.join(info.linked_dirs)}")
            if info.copied_files:
                print(f"   Propagated configs: {', '.join(info.copied_files)}")
            sys.exit(0)
        except RuntimeError as exc:
            print(f"[Error] Worktree creation failed: {exc}", file=sys.stderr)
            sys.exit(1)

    elif subcmd == "remove":
        if not sub_args:
            print("[Error] Usage: along worktree remove <slug> [--force] [--keep-branch]", file=sys.stderr)
            sys.exit(1)
        require_entity_name(sub_args[0], "along worktree remove <slug> [--force] [--keep-branch]")

        parser = argparse.ArgumentParser(prog="along worktree remove", allow_abbrev=False)
        parser.add_argument("slug")
        parser.add_argument("--force", "-f", action="store_true")
        parser.add_argument("--keep-branch", action="store_true")
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along worktree remove")

        removed = worktree.remove_worktree(
            repo_root, parsed.slug,
            force=parsed.force,
            delete_branch=not parsed.keep_branch,
        )
        if removed:
            print(f"-> Successfully removed worktree for '{parsed.slug}'.")
            sys.exit(0)
        else:
            print(f"[Warning] Worktree for '{parsed.slug}' was unlinked from Git but directory removal is deferred due to active file locks.", file=sys.stderr)
            print("Run 'along worktree gc' once open handles are closed.", file=sys.stderr)
            sys.exit(0)

    elif subcmd == "merge":
        if not sub_args:
            print("[Error] Usage: along worktree merge <slug> [--squash]", file=sys.stderr)
            sys.exit(1)
        require_entity_name(sub_args[0], "along worktree merge <slug> [--squash]")

        parser = argparse.ArgumentParser(prog="along worktree merge", allow_abbrev=False)
        parser.add_argument("slug")
        parser.add_argument("--squash", "-s", action="store_true")
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along worktree merge")

        strategy = "squash" if parsed.squash or len(sub_args) == 1 else "ff"
        res = worktree.merge_worktree(repo_root, parsed.slug, strategy=strategy)
        if res.ok:
            print(f"-> Successfully merged worktree branch 'along/{parsed.slug}' into current branch.")
            if res.stdout.strip():
                print(res.stdout.strip())
            sys.exit(0)
        else:
            print(f"[Error] Worktree merge failed: {res.stderr or res.stdout}", file=sys.stderr)
            sys.exit(1)

    elif subcmd in ("list", "status"):
        parser = argparse.ArgumentParser(prog=f"along worktree {subcmd}", allow_abbrev=False)
        parser.add_argument("--json", action="store_true")
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, f"along worktree {subcmd}")

        items = worktree.list_worktrees(repo_root)
        if parsed.json:
            print(json.dumps(items, indent=2))
        else:
            if not items:
                print("No active Along worktrees.")
            else:
                print(f"Active Along Worktrees ({len(items)}):")
                for it in items:
                    status_str = "ready" if it.get("is_git_registered") else "unregistered"
                    print(f"  - {it['slug']} [{it['branch']}] ({status_str})")
                    print(f"    Path: {it['path']}")
                    if it.get("linked_dirs"):
                        print(f"    Linked: {', '.join(it['linked_dirs'])}")
        sys.exit(0)

    elif subcmd in ("is_supported", "is-supported", "check"):
        parser = argparse.ArgumentParser(prog=f"along worktree {subcmd}", allow_abbrev=False)
        parser.add_argument("--force-cross-os", action="store_true")
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, f"along worktree {subcmd}")

        supported, reason = worktree.is_worktree_supported(repo_root, force_cross_os=parsed.force_cross_os)
        if supported:
            print(f"-> Worktree isolation supported: {reason}")
            sys.exit(0)
        else:
            print(f"[Error] Worktree isolation unsupported: {reason}", file=sys.stderr)
            sys.exit(1)

    elif subcmd == "gc":
        parser = argparse.ArgumentParser(prog="along worktree gc", allow_abbrev=False)
        _parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along worktree gc")

        cleaned = worktree.gc_worktrees(repo_root)
        print(f"-> Pruned worktrees and cleaned {cleaned} deferred items.")
        sys.exit(0)

    else:
        print(f"[Error] Unknown worktree subcommand: {subcmd}. Available: create, remove, merge, list, status, gc, is_supported.", file=sys.stderr)
        sys.exit(1)
