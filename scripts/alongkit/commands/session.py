#!/usr/bin/env python3
"""
alongkit.commands.session - Modular CLI command router for along session.
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
from typing import Any, Dict, List, Optional, Tuple

from alongkit import entities, frontmatter, lifecycle, proc, repo, session, textio
from alongkit.version import CURRENT_PROTOCOL_VERSION
from .common import check_unknown_args, require_entity_name


def _git_head_facts(repo_root: str) -> Tuple[Optional[str], Optional[str]]:
    branch = None
    commit = None
    res = proc.git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
    if res.ok and res.stdout.strip():
        branch = res.stdout.strip()
    res = proc.git(["rev-parse", "--short", "HEAD"], cwd=repo_root)
    if res.ok and res.stdout.strip():
        commit = res.stdout.strip()
    return branch, commit


def _tests_evidence_line(repo_root: str) -> str:
    from alongkit import testruns
    roots = [repo_root]
    found = repo.find_context(os.path.dirname(os.path.abspath(repo_root)))
    while found and len(roots) < 8:
        roots.append(found[0])
        found = repo.find_context(os.path.dirname(found[0]))
    tree = testruns.tree_hash(repo_root)
    for root in roots:
        run = testruns.green_run_for(root, tree) if tree else None
        if run:
            return (f"- Tests: a passing `along test` run was recorded for this working tree at "
                    f"{run.get('ts', '?')}; state the command here.")
    try:
        from alongkit.hooks.predicates import load_activity_trace
        trace = load_activity_trace(repo_root, session.current_session_key())
    except (ImportError, OSError, ValueError):
        trace = {}
    test_time = trace.get("last_test_time")
    edit_time = trace.get("last_edit_time")
    if test_time and (not edit_time or test_time >= edit_time):
        return (f"- Tests: a test run was recorded by the runtime hooks at {test_time}, "
                "after the last recorded edit; state the command and its result here.")
    return "- Tests: no test run recorded for this session; state the command and its result here."


def _work_completed_lines(repo_root: str, keys: List[str]) -> str:
    lines = []
    for key in keys:
        iss = entities.find_issue_by_slug(repo_root, key)
        if not iss:
            lines.append(f"- `{key}` (not found in .along/ISSUES/)")
            continue
        title = iss["frontmatter"].get("title")
        if not title:
            try:
                _fm, body = frontmatter.parse(textio.read_text(iss["file_path"]), path=iss["file_path"])
            except (OSError, UnicodeDecodeError, ValueError):
                body = ""
            title = next((ln[2:].strip() for ln in body.splitlines() if ln.startswith("# ")), iss["slug"])
        lines.append(f"- `{key}`: {title} ({iss['status']})")
    return "\n".join(lines) or "- No issue named (`--issues`); describe the work here."


def _render_session_log(repo_root: str, *, today: str, slug: str, agent: str, summary: str,
                        milestone: Optional[str], issues: List[str], decisions: List[str],
                        commit: Optional[str] = None) -> str:
    advanced: List[str] = []
    completed: List[str] = []
    for ref in issues:
        iss = entities.find_issue_by_slug(repo_root, ref)
        if not iss:
            advanced.append(ref)
            continue
        key = entities.canonical_key(iss["type"], iss["slug"])
        closed = iss["done"] or iss["status"] in entities.CLOSED_ISSUE_STATUSES
        (completed if closed else advanced).append(key)
    branch, head = _git_head_facts(repo_root)
    fm: Dict[str, Any] = {
        "protocol": "along",
        "protocol_version": frontmatter.quoted(CURRENT_PROTOCOL_VERSION),
        "date": today,
        "slug": slug,
        "agent": agent,
    }
    if branch:
        fm["branch"] = branch
    if commit or head:
        fm["commit"] = commit or head
    fm["summary"] = summary
    if milestone:
        fm["milestone"] = milestone
    fm.update({
        "issues_advanced": advanced,
        "issues_completed": completed,
        "decisions": list(decisions),
        "risks_logged": [],
        "spikes_conducted": [],
    })
    body = (
        f"# Session: {slug.replace('-', ' ').capitalize()}\n\n"
        f"## Summary\n{summary}\n\n"
        f"## Work Completed\n{_work_completed_lines(repo_root, completed + advanced)}\n\n"
        "## Code Review & Blast Radius\n"
        f"{_tests_evidence_line(repo_root)}\n"
    )
    return frontmatter.render(fm, body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="along session",
        description="Session log and agent-session lifecycle management.",
        allow_abbrev=False,
    )
    sub = parser.add_subparsers(dest="subcmd")

    p_create = sub.add_parser("create", help="Create a session log")
    p_create.add_argument("slug", help="Session slug")
    p_create.add_argument("--summary", "-s", default="Work session", help="Summary text")
    p_create.add_argument("--issues", "-i", default=None, help="Comma-separated issue slugs")
    p_create.add_argument("--decisions", "-d", default=None, help="Comma-separated ADR slugs")
    p_create.add_argument("--agent", "-a", default=None, help="Agent identity")
    p_create.add_argument("--milestone", "-m", default=None, help="Milestone slug")
    p_create.add_argument("--commit", default=None, help="Commit SHA")

    p_wrap = sub.add_parser("wrap", help="Wrap session and archive blackboard")
    p_wrap.add_argument("slug", help="Session slug")
    p_wrap.add_argument("--status", "-s", default="done", help="Session status")
    p_wrap.add_argument("--summary", "-m", default=None, help="Summary text")
    p_wrap.add_argument("--dry-run", action="store_true", help="Dry run without writing")
    p_wrap.add_argument("-n", "--no-verify", dest="no_verify", action="store_true", help="Skip test verification")
    p_wrap.add_argument("--agent", "-a", default=None, help="Agent identity")
    p_wrap.add_argument("--decisions", "-d", default=None, help="Comma-separated ADR slugs")
    p_wrap.add_argument("--no-decisions", action="store_true", help="Explicitly declare no decisions")
    p_wrap.add_argument("--force-reason", default=None, help="Force reason")
    p_wrap.add_argument("--reason", default=None, help="Bypass reason")

    sub.add_parser("bindings", help="List agent-session bindings")

    p_gc = sub.add_parser("gc", help="Garbage collect stale bindings")
    p_gc.add_argument("--dry-run", action="store_true", help="Simulate without removing")

    p_list = sub.add_parser("list", help="List closeout readiness")
    p_list.add_argument("--json", action="store_true", help="Format as JSON")

    p_close = sub.add_parser("close", help="Close out finished work")
    p_close.add_argument("slugs", nargs="*", help="Issue slugs to close")
    p_close.add_argument("--ready", action="store_true", help="Close all ready issues")
    p_close.add_argument("--dry-run", action="store_true", help="Simulate closeout")
    p_close.add_argument("--push", action="store_true", help="Push after closeout commit")

    return parser


def handle_session_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along_exec.py session create <slug> --summary \"Summary text\" [--issues \"slug1,slug2\"] [--decisions \"ADR-slug\"]")
        print("       along_exec.py session bindings          List agent-session bindings")
        print("       along_exec.py session gc [--dry-run]    Remove stale or orphaned bindings")
        print("       along_exec.py session list [--json]     Readiness of every issue in progress, binding and blackboard")
        print("       along_exec.py session close <slug>... | --ready [--dry-run] [--push]")
        print("                                               Close out finished work: tests once, wrap, commit by attribution,")
        print("                                               push once (needs 'along plan approve --closeout' after the user's yes)")
        sys.exit(0)

    subcmd = args[0].lower()
    sub_args = args[1:]

    if subcmd == "bindings":
        parser = argparse.ArgumentParser(prog="along session bindings", allow_abbrev=False)
        _parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along session bindings")

        rows = session.list_bindings(repo_root)
        if not rows:
            print("No agent-session bindings.")
        for b in rows:
            print(f"{b.get('key')}: {b.get('slug') or '-'} (approved: "
                  f"{str(bool(b.get('plan_approved'))).lower()}, updated: {b.get('updated')})")
        sys.exit(0)

    if subcmd == "gc":
        parser = argparse.ArgumentParser(prog="along session gc", allow_abbrev=False)
        parser.add_argument("--dry-run", action="store_true")
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along session gc")

        removed = session.gc_bindings(repo_root, dry_run=parsed.dry_run)
        verb = "Would remove" if parsed.dry_run else "Removed"
        print(f"-> {verb} {len(removed)} stale binding(s){': ' + ', '.join(removed) if removed else ''}.")
        sys.exit(0)

    if subcmd == "list":
        parser = argparse.ArgumentParser(prog="along session list", allow_abbrev=False)
        parser.add_argument("--json", action="store_true")
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along session list")

        from alongkit import closeout
        status = closeout.closeout_status(repo_root)
        if parsed.json:
            print(json.dumps(status, indent=2))
        else:
            print(closeout.format_closeout_status(status))
        sys.exit(0)

    if subcmd == "close":
        parser = argparse.ArgumentParser(prog="along session close", allow_abbrev=False)
        parser.add_argument("slugs", nargs="*")
        parser.add_argument("--ready", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--push", action="store_true")
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along session close")

        from alongkit import closeout
        names = [a for a in parsed.slugs if not a.startswith("-")]
        if not names and not parsed.ready and not closeout.load_run(repo_root):
            print("[Error] Usage: along session close <slug>... | --ready [--dry-run] [--push]", file=sys.stderr)
            sys.exit(2)
        sys.exit(closeout.run_closeout(repo_root, keys=names, ready=parsed.ready,
                                       dry_run=parsed.dry_run, push=parsed.push))

    today = datetime.now().strftime("%Y-%m-%d")
    year = datetime.now().strftime("%Y")
    sessions_dir = os.path.join(repo_root, ".along", "SESSIONS", year)

    if subcmd == "create":
        if not sub_args:
            print("[Error] Usage: along_exec.py session create <slug> --summary \"Summary\"", file=sys.stderr)
            sys.exit(1)
        require_entity_name(sub_args[0].lower(), "along session create <slug> --summary \"Summary\"")

        parser = argparse.ArgumentParser(prog="along session create", allow_abbrev=False)
        parser.add_argument("slug")
        parser.add_argument("--summary", "-s", default="Work session")
        parser.add_argument("--commit", default=None)
        parser.add_argument("--issues", "-i", default=None)
        parser.add_argument("--decisions", "-d", default=None)
        parser.add_argument("--agent", "-a", default=None)
        parser.add_argument("--milestone", "-m", default=None)
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along session create")

        slug = parsed.slug.lower()
        # Only after the name is valid: a rejected name leaves no directory behind.
        os.makedirs(sessions_dir, exist_ok=True)
        summary = parsed.summary
        issues = [iss.strip() for iss in parsed.issues.split(",") if iss.strip()] if parsed.issues else []
        decisions = [d.strip() for d in parsed.decisions.split(",") if d.strip()] if parsed.decisions else []
        agent = entities.detect_agent(parsed.agent)

        milestone = None
        if parsed.milestone:
            clean_m = parsed.milestone[:-3] if parsed.milestone.endswith(".md") else parsed.milestone
            m_path = os.path.join(repo_root, ".along", "MILESTONES", f"{clean_m}.md")
            if not os.path.exists(m_path):
                print(f"[Error] Milestone '{parsed.milestone}' does not exist in .along/MILESTONES/.", file=sys.stderr)
                sys.exit(1)
            milestone = clean_m
        else:
            milestone = entities.resolve_in_progress_milestone(repo_root)

        target_file = os.path.join(sessions_dir, f"{today}--{slug}.md")
        content = _render_session_log(
            repo_root, today=today, slug=slug, agent=agent, summary=summary,
            milestone=milestone, issues=issues, decisions=decisions, commit=parsed.commit,
        )
        textio.write_text(target_file, content, newline="\n", atomic=True)
        print(f"-> Created session log: {target_file}")

        # Update HISTORY.md
        history_file = os.path.join(repo_root, ".along", "HISTORY.md")
        if os.path.exists(history_file):
            h_content = textio.read_text(history_file)
            entry = f"{today} - {slug} - {agent} - {summary} - [.along/SESSIONS/{year}/{today}--{slug}.md](./SESSIONS/{year}/{today}--{slug}.md)"
            if entry not in h_content:
                h_content = h_content.strip() + f"\n{entry}\n"
                textio.write_text(history_file, h_content, newline="\n")
        sys.exit(0)

    elif subcmd == "wrap":
        if not sub_args:
            print("[Error] Usage: along session wrap <slug> [--status done|superseded|cancelled|duplicate] [--summary \"Summary\"] [--dry-run] [-n]", file=sys.stderr)
            sys.exit(1)
        require_entity_name(sub_args[0], "along session wrap <slug> [--status ...] [--summary \"Summary\"]")

        parser = argparse.ArgumentParser(prog="along session wrap", allow_abbrev=False)
        parser.add_argument("slug")
        parser.add_argument("--status", "-s", default="done")
        parser.add_argument("--summary", "-m", default=None)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("-n", "--no-verify", dest="no_verify", action="store_true")
        parser.add_argument("--agent", "-a", default=None)
        parser.add_argument("--decisions", "-d", default=None)
        parser.add_argument("--no-decisions", action="store_true")
        parser.add_argument("--force-reason", default=None)
        parser.add_argument("--reason", default=None)
        parser.add_argument("--no-commit", action="store_true", help="Skip automatic git commit on wrap")
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along session wrap")

        # Same contract as `along wrap` [feat--wrap-session-log-from-blackboard].
        if (parsed.decisions is None) == (not parsed.no_decisions):
            print("[Error] Answer whether architectural decisions were made: "
                  "--decisions ADR-a,ADR-b or --no-decisions (exactly one).", file=sys.stderr)
            sys.exit(2)
        decisions = [] if parsed.decisions is None else [d.strip() for d in parsed.decisions.split(",") if d.strip()]

        code = lifecycle.execute_wrap(
            repo_root=repo_root,
            slug=parsed.slug,
            status=parsed.status.lower(),
            summary=parsed.summary,
            dry_run=parsed.dry_run,
            no_verify=parsed.no_verify,
            agent=parsed.agent,
            decisions=decisions,
            force_reason=parsed.force_reason,
            guard_bypass=True,
            bypass_reason=parsed.reason,
            no_commit=parsed.no_commit,
        )
        sys.exit(code)

    else:
        print(f"[Error] Unknown session subcommand '{subcmd}'. Run 'along session --help'.", file=sys.stderr)
        sys.exit(1)
