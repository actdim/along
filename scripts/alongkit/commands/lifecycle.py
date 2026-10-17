#!/usr/bin/env python3
"""
alongkit.commands.lifecycle - Start, plan approval, status, and history session operations.
[debt--split-along-exec-and-entities]
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: python .along/scripts/test.py"
    )

import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from .. import entities, lifecycle, repo, session, textio
from .common import flag_value, require_entity_name


def _cli_approval_or_exit(repo_root: str, slug: str) -> str:
    """Hold a CLI plan approval of slug to the user's last message; its approved_via."""
    key = session.current_session_key()
    refusal, via = session.check_cli_approval(
        repo_root, key, os.path.join(session.get_session_dir(repo_root, slug), "plan.md"))
    if refusal:
        print(f"[Error] Plan approval refused: {refusal}.", file=sys.stderr)
        sys.exit(2)
    session.append_trace(repo_root, slug, f"plan approved (along scratch; approved_via: {via})")
    return via


def handle_start_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along start <slug> [--approved] [--worktree] [--profile <strict|standard|light>] [--allow-root <path>]... [--write-scope <path>]...")
        print("  Atomically marks issue in-progress, initializes session blackboard, binds this")
        print("  agent session to the issue, and optionally creates an isolated worktree.")
        print("  The plan stays unapproved until the user approves it; --approved is for scripted runs.")
        print("  --profile sets the gate strictness profile (strict, standard, light) for this session.")
        print("  --allow-root / --write-scope add to the issue's allowed_roots / write_scope")
        print("  frontmatter, read by [gate: workspace-containment].")
        sys.exit(0)

    today = datetime.now().strftime("%Y-%m-%d")

    profile_arg = flag_value(args, "--profile")
    if profile_arg:
        try:
            from alongkit import profiles
            profile_val = profiles.validate_profile(profile_arg)
        except ValueError as exc:
            print(f"[Error] {exc}", file=sys.stderr)
            sys.exit(2)
    else:
        profile_val = None

    scope_flags: Dict[str, List[str]] = {"--allow-root": [], "--write-scope": []}
    i = 1
    while i < len(args):
        if args[i] in scope_flags:
            if i + 1 >= len(args) or args[i + 1].startswith("--"):
                print(f"[Error] {args[i]} requires a path.", file=sys.stderr)
                sys.exit(2)
            scope_flags[args[i]].append(args[i + 1])
            i += 2
            continue
        i += 1

    slug = require_entity_name(args[0].lower(), "along start <slug> [--approved] [--worktree] [--profile <profile>]")
    issue = entities.find_issue_by_slug(repo_root, slug)
    if not issue:
        print(f"[Error] Issue '{slug}' not found in .along/ISSUES/.", file=sys.stderr)
        sys.exit(1)

    issue_path = issue.get("file_path", "")
    is_closed = issue.get("done") or issue.get("status") in entities.CLOSED_ISSUE_STATUSES or "done" in os.path.normpath(issue_path).split(os.sep)
    if is_closed:
        print(f"[Error] Cannot start work on issue '{slug}': issue is already closed in ISSUES/done/ (status: {issue.get('status')}).\n"
              f"To resume work on a closed issue, reopen it first:\n"
              f"    along issue reopen {slug}", file=sys.stderr)
        sys.exit(1)

    if issue_path and os.path.isfile(issue_path):
        try:
            content = textio.read_text(issue_path, strict=False)
            is_stub, stub_reasons = entities.is_issue_stub(content)
            if is_stub:
                print(f"[Error] Cannot start work on issue '{slug}': issue contains unfilled scaffold placeholders:\n"
                      + "\n".join(f"  - {r}" for r in stub_reasons)
                      + f"\nPopulate '{repo.safe_relpath(issue_path, repo_root)}' with actual requirements and context before starting work.",
                      file=sys.stderr)
                sys.exit(2)
        except OSError:
            pass

    allow_dirty = "--allow-dirty" in args
    is_worktree = "--worktree" in args

    if not is_worktree:
        from alongkit import closeout
        top = closeout.git_top(repo_root)
        if top:
            changes = closeout.git_changes(repo_root)
            if changes:
                # 1. Hard block if uncommitted files from previously completed (wrapped) issues exist
                done_attr = closeout.done_issues_attribution(repo_root)
                unattributed_candidates = list(changes.keys())
                wrapped_groups: Dict[str, List[str]] = {}
                for dkey, dinfo in done_attr.items():
                    all_dpaths = {closeout.path_key(p) for p in list(dinfo["files"].keys()) + dinfo["entity_files"]}
                    matched = [p for p in unattributed_candidates if closeout.path_key(p) in all_dpaths]
                    if matched:
                        wrapped_groups[dkey] = sorted(matched)
                if wrapped_groups and not allow_dirty:
                    print("[Error] Working tree has uncommitted changes from completed (wrapped) issue(s):", file=sys.stderr)
                    for dkey, wpaths in sorted(wrapped_groups.items()):
                        print(f"  - {dkey}:", file=sys.stderr)
                        for wp in wpaths[:5]:
                            print(f"      {wp}", file=sys.stderr)
                        if len(wpaths) > 5:
                            print(f"      ... and {len(wpaths) - 5} more", file=sys.stderr)
                    print("Commit them first ('along commit -i <slug> --paths ...' or 'along session close'),", file=sys.stderr)
                    print("or pass --allow-dirty to override.", file=sys.stderr)
                    sys.exit(1)

                # 2. Block if active in-progress issue exists with uncommitted working tree changes
                active_others = [i for i in entities.scan_issues(repo_root)
                                 if i.get("status") == "in-progress" and i.get("slug") != issue["slug"]]
                if active_others and not allow_dirty:
                    changed_keys = {closeout.path_key(p): p for p in changes}
                    active_with_changes = []
                    for other in active_others:
                        other_slug = other["slug"]
                        attr_files = session.attributed_files(repo_root, other_slug)
                        other_top_paths = [repo.canonical_relpath(os.path.join(repo_root, p), top) for p in attr_files]
                        dirty_for_other = [changed_keys[closeout.path_key(p)] for p in other_top_paths if closeout.path_key(p) in changed_keys]
                        if dirty_for_other:
                            active_with_changes.append((other["slug"], dirty_for_other))

                    if active_with_changes:
                        print("[Error] Active in-progress issue(s) exist with uncommitted working tree changes:", file=sys.stderr)
                        for os_slug, os_paths in active_with_changes:
                            print(f"  - {os_slug}:", file=sys.stderr)
                            for op in os_paths[:5]:
                                print(f"      {op}", file=sys.stderr)
                            if len(os_paths) > 5:
                                print(f"      ... and {len(os_paths) - 5} more", file=sys.stderr)
                        print(f"To work on '{issue['slug']}' in parallel without dirtying this tree, use:", file=sys.stderr)
                        print(f"  along start {issue['slug']} --worktree", file=sys.stderr)
                        print("Or commit the current changes first, or pass --allow-dirty to proceed anyway.", file=sys.stderr)
                        sys.exit(1)

    updates: Dict[str, Any] = {"status": "in-progress", "updated": today}
    for flag, key in (("--allow-root", "allowed_roots"), ("--write-scope", "write_scope")):
        if scope_flags[flag]:
            current = (issue.get("frontmatter") or {}).get(key) or []
            current = [current] if isinstance(current, str) else [str(p) for p in current]
            updates[key] = current + [p for p in scope_flags[flag] if p not in current]
    fpath, new_fm = entities.update_issue_frontmatter(repo_root, issue["slug"], updates)
    rel_path = repo.normalize_posix(repo.safe_relpath(fpath, repo_root))
    print(f"-> Marked issue in-progress: {rel_path}")

    entities.sync_issues_board(repo_root, recent_done_limit=entities.RECENT_DONE_LIMIT)

    title = new_fm.get("title", issue["slug"].replace("-", " ").capitalize())
    st = session.init_session(repo_root, issue["slug"], title=title, profile=profile_val)
    sdir = session.get_session_dir(repo_root, issue["slug"])
    key = session.current_session_key()

    if "--approved" in args:
        refusal, via = session.check_cli_approval(repo_root, key, os.path.join(sdir, "plan.md"))
        if refusal:
            print(f"[Error] --approved refused: {refusal}.", file=sys.stderr)
            sys.exit(2)
    binding = session.bind_session(repo_root, issue["slug"], key=key,
                                   approved=True if "--approved" in args else None,
                                   profile=profile_val)
    if "--approved" in args:
        session.mark_approval(repo_root, key, via)
        session.append_trace(repo_root, issue["slug"], f"plan approved (along start --approved; approved_via: {via})")
    approved = "--approved" in args or session.is_plan_approved(repo_root, slug=issue["slug"], key=key)
    st = session.set_session_phase(repo_root, "execution" if approved else "planning",
                                   slug=issue["slug"], plan_approved=approved)
    print(f"-> Initialized session blackboard: {sdir} "
          f"(phase: {st.get('phase')}, plan_approved: {str(bool(st.get('plan_approved'))).lower()})")
    if binding:
        print(f"-> Bound agent session {binding['key']} to '{issue['slug']}'.")
    else:
        print("-> No agent session id in the environment; gates fall back to the single in-progress issue.")
    if profile_val:
        print(f"-> Active profile set to '{profile_val}'.")
    if not approved:
        print("-> Edits unlock after the user approves the plan. Call EnterPlanMode, write the plan, then "
              "ExitPlanMode. Outside plan mode, write the plan to a file and run "
              "'along plan approve --plan-file <path>' after the user's explicit yes.")

    if "--worktree" in args:
        from alongkit import worktree
        force_cross = "--force-cross-os" in args
        if not force_cross and worktree.is_cross_os_mount(repo_root):
            print("[Warning] Worktree unavailable on cross-OS mount; degrading to in-place mode.", file=sys.stderr)
            print(f"-> Ready to work on issue '{issue['slug']}'. Active issue bound.")
        else:
            try:
                info = worktree.create_worktree(repo_root, issue["slug"], force_cross_os=force_cross)
                print(f"-> Created isolated worktree: {info.path}")
                print("-> Ready to work in worktree. Run tests and edits there.")
            except RuntimeError as exc:
                if "cross-os" in str(exc).lower():
                    print(f"[Warning] Worktree unavailable on cross-OS mount: {exc}; degrading to in-place mode.", file=sys.stderr)
                    print(f"-> Ready to work on issue '{issue['slug']}'. Active issue bound.")
                else:
                    raise
    else:
        print(f"-> Ready to work on issue '{issue['slug']}'. Active issue bound.")

    sys.exit(0)


def handle_plan_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along plan approve [<slug>] [--plan-file <path>]")
        print("                                     Record the user's approval of the plan (run only after an explicit yes);")
        print("                                     --plan-file writes the approved plan into the blackboard plan.md")
        print("       along plan approve --closeout <slug>... | --closeout --ready")
        print("                                     Record the user's approval to close these issues out (after an explicit yes)")
        print("       along plan status             Show this session's binding, phase and approval")
        sys.exit(0)
    sub = args[0].lower()
    key = session.current_session_key()
    if sub == "approve" and "--closeout" in args:
        if not key:
            print("[Error] No agent session id in the environment: a closeout approval belongs to a session.",
                  file=sys.stderr)
            sys.exit(2)
        if "--ready" in args:
            from alongkit import closeout
            slugs = [i["slug"] for i in closeout.closeout_status(repo_root)["items"] if i["verdict"] == "ready"]
        else:
            slugs = [entities.parse_key(a.lower())[1] for a in args[args.index("--closeout") + 1:]
                     if not a.startswith("-")]
        if not slugs:
            print("[Error] Nothing to approve: name the issues ('--closeout <slug>...') or use '--ready' "
                  "when 'along session list' shows ready issues.", file=sys.stderr)
            sys.exit(2)
        session.record_closeout_approval(repo_root, key, slugs)
        print(f"-> Closeout approved for {', '.join(slugs)} (session: {key}). "
              "Next: 'along session close " + " ".join(slugs) + " [--push]'.")
        sys.exit(0)
    if sub == "approve":
        slug = args[1].lower() if len(args) > 1 and not args[1].startswith("-") else None
        slug = slug or session.get_active_session_slug(repo_root, key)
        plan_file = flag_value(args, "--plan-file")
        if "--plan-file" in args and not plan_file:
            print("[Error] --plan-file needs a path.", file=sys.stderr)
            sys.exit(2)
        if plan_file and not slug:
            print("[Error] --plan-file needs an issue: 'along start <slug>' first, or pass <slug>.", file=sys.stderr)
            sys.exit(2)
        if slug:
            plan_path = plan_file or os.path.join(session.get_session_dir(repo_root, slug), "plan.md")
        else:
            plan_path = None
        refusal, via = session.check_cli_approval(repo_root, key, plan_path)
        if refusal:
            print(f"[Error] Plan approval refused: {refusal}.", file=sys.stderr)
            print("  Call EnterPlanMode, write the plan, then ExitPlanMode. Outside plan mode, write the "
                  "plan to a file and run 'along plan approve --plan-file <path>' after the user's explicit yes.",
                  file=sys.stderr)
            sys.exit(2)
        if slug:
            if plan_file:
                try:
                    plan_text = textio.read_text(plan_file, strict=False)
                except OSError as exc:
                    print(f"[Error] Cannot read --plan-file '{plan_file}': {exc}", file=sys.stderr)
                    sys.exit(2)
                rev = session.record_plan(repo_root, slug, plan_text, "plan approve --plan-file")
                if rev:
                    print(f"-> Recorded plan revision {rev} in .along/.session/{slug}/plan.md")
            if not session.plan_recorded(repo_root, slug):
                print(f"[Error] No plan recorded for '{slug}': .along/.session/{slug}/plan.md is still the scaffold.",
                      file=sys.stderr)
                print("  Write the approved plan to a file and pass '--plan-file <path>', or write it into plan.md.",
                      file=sys.stderr)
                sys.exit(2)
            bound_issue = entities.find_issue_by_slug(repo_root, slug)
            if bound_issue and os.path.isfile(bound_issue.get("file_path", "")):
                try:
                    iss_txt = textio.read_text(bound_issue["file_path"], strict=False)
                    is_stub, stub_reasons = entities.is_issue_stub(iss_txt)
                    if is_stub:
                        print(f"[Error] Plan approval refused: bound issue '{slug}' contains unfilled scaffold placeholders:\n"
                              + "\n".join(f"  - {r}" for r in stub_reasons)
                              + f"\n  Populate '{repo.safe_relpath(bound_issue['file_path'], repo_root)}' with actual requirements before approving the plan.",
                              file=sys.stderr)
                        sys.exit(2)
                except OSError:
                    pass
            session.set_session_phase(repo_root, "execution", slug=slug, plan_approved=True)
            plan_now = textio.read_text(os.path.join(session.get_session_dir(repo_root, slug), "plan.md"), strict=False)
            session.mark_approval(repo_root, key, via, plan_now)
            sha = session.plan_sha256(plan_now)
            trace_extra = f", plan_sha256: {sha[:12]}" if sha else ""
            session.append_trace(repo_root, slug, f"plan approved (along plan approve) approved_via: {via}{trace_extra}")
            session.append_event(repo_root, slug, key, "approve")
            print(f"-> Plan approved for '{slug}' (session: {key or 'none'}, via: {via}).")
        elif key:
            session.record_plan_approval(repo_root, key, via)
            print(f"-> Plan approved for session {key}; it applies to the next 'along start <slug>'.")
        else:
            print("[Error] No issue bound and no agent session id; run 'along start <slug>' first.", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)
    if sub == "status":
        slug, how = session.resolve_active_session(repo_root, key)
        print(f"Session key: {key or 'none (no session id in environment)'}")
        print(f"Issue:       {slug or '-'} ({how})")
        print(f"Phase:       {session.get_session_phase(repo_root, slug=slug, key=key)}")
        print(f"Approved:    {str(session.is_plan_approved(repo_root, slug=slug, key=key)).lower()}")
        sys.exit(0)
    print(f"[Error] Unknown plan subcommand '{sub}'. Use: approve, status.", file=sys.stderr)
    sys.exit(2)


def handle_status_command(repo_root: str, args: List[str]):
    if args and args[0] in ("-h", "--help", "help"):
        print("Usage: along status    Show repository root, active issues and Along state")
        sys.exit(0)
    print("=== Along Repository Status ===")
    print(f"Repo Root: {repo_root}")
    along_dir = os.path.join(repo_root, ".along")
    if not os.path.exists(along_dir):
        print("[Notice] .along/ directory not found in repository.")
        sys.exit(0)

    # Active issues
    issues_dir = os.path.join(along_dir, "ISSUES")
    active_issues = []
    if os.path.exists(issues_dir):
        for f in os.listdir(issues_dir):
            if f.endswith(".md") and os.path.isfile(os.path.join(issues_dir, f)):
                active_issues.append(f)
    print(f"\nActive Issues ({len(active_issues)}):")
    for iss in active_issues:
        print(f"  - {iss}")

    # Declared test policy
    from alongkit import verify
    print(f"\nVerify: {verify.load_policy(repo_root).describe()}")

    # Latest session
    sessions_dir = os.path.join(along_dir, "SESSIONS")
    latest_session = None
    if os.path.exists(sessions_dir):
        all_sessions = []
        for root, _, files in os.walk(sessions_dir):
            for f in files:
                if f.endswith(".md"):
                    all_sessions.append(os.path.join(root, f))
        if all_sessions:
            all_sessions.sort()
            latest_session = all_sessions[-1]

    if latest_session:
        print(f"\nLatest Session: {os.path.basename(latest_session)}")
        session_text = textio.read_text(latest_session, strict=False)
        lines = [l.strip() for l in session_text.splitlines() if l.strip().startswith("summary:")]
        if lines:
            print(f"  {lines[0]}")
    else:
        print("\nLatest Session: None recorded yet")

    # In-flight blackboards
    session_bb_dir = os.path.join(along_dir, ".session")
    if os.path.exists(session_bb_dir):
        bbs = [d for d in os.listdir(session_bb_dir)
               if os.path.isdir(os.path.join(session_bb_dir, d))
               and not d.startswith(".") and d not in session.RESERVED_SESSION_DIRS]
        if bbs:
            print(f"\nActive Blackboards ({len(bbs)}): {', '.join(bbs)}")
    print("\n===============================")
    sys.exit(0)


def handle_history_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along history [append] <slug> [summary]")
        print("  append <slug> [summary]   Append or update a formatted entry in .along/HISTORY.md")
        sys.exit(0)

    subcmd = args[0].lower()
    if subcmd == "append":
        if len(args) < 2:
            print("[Error] Usage: along history append <slug> [summary]", file=sys.stderr)
            sys.exit(1)
        slug = require_entity_name(args[1].lower(), "along history append <slug> [summary]")
        summary = " ".join(args[2:]).strip() if len(args) > 2 else None
        res = lifecycle.append_history_entry(repo_root, slug, summary=summary)
        sys.exit(res)
    else:
        print(f"[Error] Unknown history subcommand '{subcmd}'. Run 'along history --help'.", file=sys.stderr)
        sys.exit(1)
