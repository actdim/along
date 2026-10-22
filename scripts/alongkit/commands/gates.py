#!/usr/bin/env python3
"""
alongkit.commands.gates - Git merge driver setup and commit-time / CI gate pipeline CLI.
[debt--split-along-exec-and-entities]
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
import os
import sys
from typing import List, Optional, Tuple

from .. import gitgates, merge, repo
from .common import flag_value


def handle_git_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along git [setup|status|sync] [args...]")
        print("  setup  [--uninstall] [--dry-run]  Register merge drivers and .gitattributes bindings")
        print("  status [--json]                   Report driver registration and pending resync")
        print("  sync                              Recompile projections after a driver-handled merge")
        sys.exit(0)

    subcmd = args[0].lower()
    flags = set(args[1:])
    if not merge.git_dir(repo_root):
        print(f"[Error] Not a git repository: {repo_root}", file=sys.stderr)
        sys.exit(1)

    if subcmd == "setup":
        report = merge.setup(repo_root, uninstall="--uninstall" in flags, dry_run="--dry-run" in flags)
        verb = "Would change" if report["dry_run"] else "Changed"
        action = "removal" if report["uninstall"] else "registration"
        changed = report["config_changed"]
        if not changed and not report["gitattributes_changed"]:
            print(f"-> Merge driver {action}: already up to date.")
        else:
            for key in changed:
                print(f"   {verb} .git/config: {key}")
            if report["gitattributes_changed"]:
                print(f"   {verb} .gitattributes (managed merge driver block)")
            print(f"-> Merge driver {action} " + ("planned (dry run, nothing written)." if report["dry_run"] else "complete."))
        sys.exit(0)

    if subcmd == "status":
        info = merge.status(repo_root)
        if "--json" in flags:
            print(json.dumps(info, indent=2))
            sys.exit(0)
        for key, state in info["config"].items():
            print(f"[{'OK' if state == 'ok' else 'WARN'}] {key}: {state}")
        print(f"[{'OK' if info['gitattributes'] else 'WARN'}] .gitattributes bindings: "
              f"{'present' if info['gitattributes'] else 'missing'}")
        if info["pending_resync"]:
            print("[WARN] Projections kept as 'ours' during a merge; run `along git sync`: "
                  + ", ".join(info["pending_resync"]))
        if not merge.is_configured(info):
            print("-> Run `along git setup` to register the merge drivers.")
        sys.exit(0)

    if subcmd == "sync":
        kb_script = repo.resolve_tool_script("along_kb_sync.py", repo_root)
        done = merge.resync(repo_root, kb_script=kb_script)
        for path in done:
            print(f"   -> Recompiled {path}")
        print("-> Projections synchronized.")
        sys.exit(0)

    print(f"[Error] Unknown git subcommand: {subcmd}. Use setup, status, or sync.", file=sys.stderr)
    sys.exit(1)


def handle_lint_command(repo_root: str, args: List[str]):
    """`along lint`: the commit-time checks on demand (`along gates check`). [debt--gate-simplification]"""
    if args and args[0] in ("-h", "--help", "help"):
        print("Usage: along lint [--ci] [--range COMMIT_RANGE] [--no-links] [--json]")
        print("  Commit-time checks (typography, code fences, links, filenames, secrets, stubs,")
        print("  rule packs, entities) on staged changes; same as 'along gates check'.")
        sys.exit(0)
    handle_gates_command(repo_root, ["check", *args])


def handle_gates_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along gates check [--hook {pre-commit,commit-msg}] [--ci] [--range COMMIT_RANGE] [--no-links] [--json] [hook_args...]")
        print("  Run the commit-time gate subset outside agent runtimes (git hooks, CI).")
        print("       along gates stats [--since YYYY-MM-DD]")
        print("  Per-gate counts of blocks, shadow warnings and recorded bypasses, and repeated")
        print("  identical blocks per conversation (agent loops).")
        print("       along gates denials [--slug SLUG] [--json]")
        print("  Gate denials of the bound issue: open, resolved (retry / approve) and acknowledged.")
        print("       along gates ack (ID... | --all) --note \"...\" [--slug SLUG]")
        print("  Record that the user was told what a denied tool call left undone; closeout")
        print("  accepts the acknowledgement once the user has replied after it.")
        sys.exit(0)

    subcmd = args[0].lower()
    if subcmd == "stats":
        from alongkit import gatestats
        since = flag_value(args, "--since")
        print(gatestats.format_table(gatestats.collect(repo_root, since)))
        print()
        print(gatestats.format_loops(gatestats.loops(repo_root, since)))
        sys.exit(0)
    if subcmd in ("denials", "ack"):
        sys.exit(_handle_denials(repo_root, subcmd, args[1:]))
    if subcmd != "check":
        print(f"[Error] Unknown gates subcommand: {subcmd}. Use check, stats, denials or ack.", file=sys.stderr)
        sys.exit(2)

    check_args = args[1:]
    parser = argparse.ArgumentParser(
        prog="along gates check",
        description="Run the commit-time gate subset outside agent runtimes (git hooks, CI).")
    parser.add_argument("--hook", choices=list(gitgates.HOOK_NAMES),
                        help="Run as the named git hook (installed by `along hooks install --git`)")
    parser.add_argument("hook_args", nargs="*", help="Arguments git passes to the hook")
    parser.add_argument("--ci", action="store_true", help="Check a commit range, projections and links")
    parser.add_argument("--range", dest="commit_range", default=None,
                        help="Commit range for --ci (default: from GITHUB_BASE_REF / ALONG_CI_BEFORE, else HEAD^..HEAD)")
    parser.add_argument("--no-links", action="store_true", help="Skip the link integrity check in --ci")
    parser.add_argument("--json", action="store_true", help="Emit violations as JSON")
    opts = parser.parse_args(check_args)

    if not repo_root:
        print("[Error] Cannot locate repository root.", file=sys.stderr)
        sys.exit(2)

    if opts.hook == "pre-commit":
        context, violations = "pre-commit", gitgates.check_pre_commit(repo_root)
    elif opts.hook == "commit-msg":
        if not opts.hook_args:
            print("[Error] commit-msg hook needs the message file argument.", file=sys.stderr)
            sys.exit(2)
        context, violations = "commit-msg", gitgates.check_commit_msg(repo_root, opts.hook_args[0])
    elif opts.ci:
        kb_script = None if opts.no_links else repo.resolve_tool_script("along_kb_sync.py", repo_root)
        context = f"ci {opts.commit_range or gitgates.default_ci_range() or 'HEAD^..HEAD'}"
        violations = gitgates.check_ci(repo_root, opts.commit_range, links=not opts.no_links,
                                       kb_script=kb_script)
    else:
        context = "staged changes"
        violations = gitgates.check_pre_commit(repo_root)

    if opts.json:
        print(json.dumps([v.__dict__ for v in violations], indent=2))
    else:
        stream = sys.stderr if violations else sys.stdout
        print(gitgates.format_report(violations, context), file=stream)
    sys.exit(1 if violations else 0)


def _denials_target(repo_root: str, slug: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """(context, slug): the named issue's blackboard, else the one this session is bound to."""
    from .. import session
    key = session.current_session_key()
    ctx, bound = session.bound_blackboard(repo_root, key)
    if not slug:
        return ctx, bound
    slug = slug.split("--", 1)[1] if "--" in slug else slug
    if bound == slug and ctx:
        return ctx, slug
    return (repo_root, slug) if session.load_state(repo_root, slug) is not None else (None, slug)


def _handle_denials(repo_root: str, subcmd: str, args: List[str]) -> int:
    """`along gates denials` / `along gates ack`. [feat--anti-silent-fallback-gate]"""
    from .. import session
    parser = argparse.ArgumentParser(prog=f"along gates {subcmd}", allow_abbrev=False)
    parser.add_argument("--slug", default=None, help="Issue slug (default: the issue this session is bound to)")
    if subcmd == "ack":
        parser.add_argument("ids", nargs="*", help="Denial ids (see 'along gates denials')")
        parser.add_argument("--all", action="store_true", help="Acknowledge every open denial")
        parser.add_argument("--note", default=None, help="What the user was told was not done, and why")
    else:
        parser.add_argument("--json", action="store_true", help="Emit the denials as JSON")
    opts = parser.parse_args(args)

    ctx, slug = _denials_target(repo_root, opts.slug)
    if not ctx or not slug:
        what = f"issue '{slug}' has no blackboard" if slug else "this session is not bound to an issue"
        print(f"[Error] No gate denials to read: {what} (along start <slug>, or --slug).", file=sys.stderr)
        return 2
    items = session.denial_status(ctx, slug)

    if subcmd == "denials":
        if opts.json:
            print(json.dumps(items, indent=2))
            return 0
        if not items:
            print(f"No gate denials recorded for '{slug}'.")
            return 0
        for d in items:
            state = d["state"]
            if state == session.DENIAL_RESOLVED:
                state = f"resolved ({d['via']})"
            elif state == session.DENIAL_ACKED:
                state = {True: "acked", False: "acked, awaiting the user's reply",
                         None: "acked (unverified)"}[d["verified"]]
            print(f"{d['id']}  {str(d['ts'])[:19]}  [{d['gate']}]  {state}")
            print(f"    {d.get('target') or d.get('tool') or ''}")
            if d.get("note"):
                print(f"    note: {d['note']}")
        return 0

    note = (opts.note or "").strip()
    if not note:
        print("[Error] along gates ack needs --note \"...\": what the user was told was not done, and why.",
              file=sys.stderr)
        return 2
    open_items = [d for d in items if d["state"] == session.DENIAL_OPEN]
    if opts.all:
        chosen = open_items
    else:
        known = {d["id"]: d for d in items}
        missing = [i for i in opts.ids if i not in known]
        if not opts.ids or missing:
            print(f"[Error] Name denial ids or pass --all; unknown: {', '.join(missing) or '(none given)'}. "
                  "See 'along gates denials'.", file=sys.stderr)
            return 2
        chosen = [known[i] for i in opts.ids if known[i]["state"] != session.DENIAL_RESOLVED]
    if not chosen:
        print(f"-> No open gate denials for '{slug}'.")
        return 0
    key = session.current_session_key()
    for d in chosen:
        session.append_event(ctx, slug, key, "ack", extra={"id": d["id"], "note": note})
        session.trace_event(repo_root, key, f"acknowledged denial {d['id']} [{d['gate']}]: {note}")
    print(f"-> Acknowledged {len(chosen)} gate denial(s) of '{slug}': {session.format_denials(chosen)}")
    print("   The user must see this in your reply; closeout accepts it once they have replied.")
    return 0
