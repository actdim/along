#!/usr/bin/env python3
"""
along_exec.py - Unified Command Router & Lifecycle Dispatcher for Along Protocol.

Dispatches:
1. Project Lifecycle Hooks:
   - build        -> executes .along/scripts/build.py (or auto-detects build command)
   - test         -> executes .along/scripts/test.py (or auto-detects quiet test runner)
   - dev          -> executes .along/scripts/dev.py (or auto-detects dev runner)
2. Along Protocol Tools (Direct Precursor to along CLI):
   - kb-sync      -> runs along_kb_sync.py
   - kb-search    -> runs along_kb_search.py
   - dep-scan     -> runs along_dep_scan.py
   - history-sync -> runs along_history_sync.py
   - commit       -> runs along_commit.py
   - version-bump -> runs along_version_bump.py
   - update       -> runs along_update.py
   - dash         -> runs along_dash.py
   - migrate      -> runs migrate_protocol.py
   - sanitize     -> runs sanitize_typography.py
   - graph-check  -> runs along_graph_check.py (doctor preflight check)
   - graph-sync   -> runs along_graph_sync.py (build or update AST code graph)
   - graph-build  -> alias for graph-sync
   - graph-impact -> runs along_graph_impact.py (semantic blast radius)
   - graph-arch   -> runs along_graph_arch.py (architectural overview)
"""

import sys
import os
import re
import json
import shlex
import shutil
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap

# This engine reads entity front-matter, so it needs ruamel.yaml. Resolve it before
# anything imports it: an engine invoked as `python <path>/<engine>.py` may start
# under an interpreter that has no dependencies prepared, which is exactly how the
# installers and the documented skill commands invoke it.
bootstrap.ensure_deps()

from alongkit import circuit, entities, frontmatter, gates, lifecycle, proc, repo, session, textio, transaction
from alongkit.version import CURRENT_PROTOCOL_VERSION
from alongkit.commands import (
    handle_decision_command,
    handle_issue_command,
    handle_milestone_command,
    handle_scratch_command,
    handle_session_command,
    handle_worktree_command,
)
from alongkit.commands.session import _render_session_log

TOOL_MAPPINGS = {
    "kb-sync": "along_kb_sync.py",
    "kbsync": "along_kb_sync.py",
    "kb-search": "along_kb_search.py",
    "kbsearch": "along_kb_search.py",
    "dep-scan": "along_dep_scan.py",
    "depscan": "along_dep_scan.py",
    "history-sync": "along_history_sync.py",
    "historysync": "along_history_sync.py",
    "commit": "along_commit.py",
    "version-bump": "along_version_bump.py",
    "versionbump": "along_version_bump.py",
    "bump": "along_version_bump.py",
    "update": "along_update.py",
    "init": "along_init.py",
    "dash": "along_dash.py",
    "dashboard": "along_dash.py",
    "migrate": "migrate_protocol.py",
    "sanitize": "sanitize_typography.py",
    "typography": "sanitize_typography.py",
    "feedback": "along_feedback.py",
    "diagnostics": "along_feedback.py",
    "graph-check": "along_graph_check.py",
    "graphcheck": "along_graph_check.py",
    "graph-sync": "along_graph_sync.py",
    "graphsync": "along_graph_sync.py",
    "graph-build": "along_graph_sync.py",
    "graphbuild": "along_graph_sync.py",
    "graph-impact": "along_graph_impact.py",
    "graphimpact": "along_graph_impact.py",
    "graph-arch": "along_graph_arch.py",
    "grapharch": "along_graph_arch.py",
    "wrap": "along_wrap.py",
    "hook": "along_hook.py",
    "hooks": "along_hook.py",
    "resolve": "along_resolve.py",
    "conflict-check": "along_conflict_check.py",
    "conflictcheck": "along_conflict_check.py",
}

LIFECYCLE_ACTIONS = {"build", "test", "dev", "debug"}


# Root discovery, engine resolution, and front-matter editing live in the shared
# package: alongkit.repo and alongkit.frontmatter.
find_repo_root = repo.find_repo_root
resolve_tool_script = repo.resolve_tool_script
has_frontmatter = frontmatter.has_frontmatter
update_frontmatter_fields = frontmatter.update


get_lifecycle_script_path = lifecycle.get_lifecycle_script_path
synthesize_lifecycle_script = lifecycle.synthesize_lifecycle_script
detect_lifecycle_action = lifecycle.detect_lifecycle_action
resolve_output_mode = lifecycle.resolve_output_mode
run_lifecycle_command = lifecycle.run_lifecycle_command


def print_help():
    print("""Along Command Router (along_exec.py)

Usage:
  python scripts/along_exec.py <command> [subcommand] [args...]
  along <command> [subcommand] [args...]
  (or: python scripts/along_exec.py <command> [subcommand] [args...])

Lifecycle Commands (project hooks):
  build          Execute project build (.along/scripts/build.py or auto-detected)
  test           Execute project tests (.along/scripts/test.py or auto-detected)
  dev            Launch project dev server (.along/scripts/dev.py or auto-detected)
  dev-env        Initialize local .venv and install alongkit in editable mode [--reinstall]
  debug          Execute project debug runner (.along/scripts/debug.py or auto-detected)

Entity Management Commands:
  status         Instant terminal summary of repository state, active issues, and recent sessions
  doctor         Validate .along/ structure, .gitattributes, and ADR headers (--entities for entity graph; --entities --fix drops dangling milestone fields)
  start          Mark issue in-progress, initialize blackboard, bind this agent session [--approved] [--worktree]
  plan approve   [<slug>]  Record the user's plan approval for this session (after an explicit yes)
  plan status    Show this session's bound issue, phase and approval
  issue create   <type> <slug> --title "Title" [--priority high|medium|low] [--tags "t1,t2"] [--agent <name>] [--milestone <name>]
  issue update   <slug> [--milestone <name>] [--priority <priority>] [--status <status>] [--tags <tags>] [--title <title>]
  issue show     <slug> [--json]
  issue sync     Recompile .along/ISSUES.md projection deterministically from entity files
  issue done     <slug>
  issue list     List active issues in terminal
  issue rename   <old-key> <new-key>  Rename an issue and rewrite every inbound reference
  issue supersede <old-key> --by <new-key>  Close as superseded (file kept) and move references to the successor
  milestone sync [<slug>] Recompute target_issues, progress_pct, and status across milestones
  milestone list [--status open|in-progress|completed] [--json]
  milestone show <slug> [--json]
  milestone create <slug> --title "Title" [--due YYYY-MM-DD]
  session create <slug> --summary "Summary" [--issues "slug1,slug2"] [--decisions "ADR-slug"] [--agent <name>] [--milestone <name>] [--commit <sha>]
  session wrap   <slug> (--decisions "ADR-a,ADR-b" | --no-decisions) [--status done|superseded] [--summary "Summary"] [--force-reason "..."] [--dry-run] [-n]
  session bindings  List agent-session bindings
  session gc     [--dry-run]  Remove stale or orphaned bindings
  history append <slug> [summary]  Append or update a formatted entry in .along/HISTORY.md
  decision create <slug> --title "Title" --context "Why" --decision "What" --consequences "Tradeoffs"
  decision sync   Recompile .along/CONSTRAINTS.md projection from active ADRs
  scratch init   <slug> [--title "Title"] [--steps N] [--restart] [--mode direct]
  scratch state  <slug> [--json]
  scratch patch  <slug> <json-delta> [--file <path>] [--show]
  scratch phase  <slug> <inquiry|planning|execution> [--approve]
  scratch approve <slug>  Grant plan approval (phase: execution)
  scratch update <slug> [--step N] [--step-status status] [--inc-retry] [--status status]
  scratch fallback <slug> --reason "..."  Single-agent execution, reason kept in execution_trace.md
  scratch purge  <slug> [--force --reason "..."]  Refuses while role-based steps are open
  worktree create <slug> [--branch <name>] [--base-ref <ref>]
  worktree remove <slug> [--force] [--keep-branch]
  worktree merge  <slug> [--squash]
  worktree list   [--json]
  worktree status [--json]
  worktree gc
  git setup      Register Along merge drivers in .git/config and bind .gitattributes [--uninstall] [--dry-run]
  git status     Report merge driver registration and pending projection resync [--json]
  git sync       Recompile projections after a merge handled by the projection driver
  gates check    Commit-time gates outside agent runtimes [--hook pre-commit|commit-msg] [--ci [--range R] [--no-links]] [--json]
  rules          Rule packs management (attach, status, diff, restore)
  tool           Tool nature classification and rules (classify, list, explain)
  budget         Measure context footprint and check token budgets (--json, --check)
  context-budget Measure context footprint and check token budgets (--json, --check)
  circuit        Systemic anomaly circuit breaker (status, trip, reset, verify)
  telemetry status Check pending WAL telemetry spool and endpoint connectivity (--json)
  telemetry flush  Flush spooled telemetry spans to OTLP endpoint (--endpoint <url>)
  run            Execute command behind runtime gate pipeline (along run <cmd...>)
                 Or launch Antigravity supervisor (along run antigravity [options])

Along Protocol Tools:
  wrap           Transactional session and issue wrap engine
  kb-sync        Synchronize and compile Knowledge Base in docs/
  kb-search      Search Knowledge Base and project memory
  dep-scan       Scan multi-project dependencies and AI rules
  history-sync   Reconcile Git commit history and synthesize entities
  commit         Safe Conventional Commits with a typography gate
  version-bump   Increment project version and create release commit
  update         Update Along protocol and skills across workspaces
  dash           Launch executive dashboard and OpenAPI service
  migrate        Run protocol migration and YAML front-matter fixes; prints the plan by
                 default from a script, --apply performs it
  sanitize       Check (default) or repair non-ASCII typography; --write to apply
  feedback       Global diagnostics, error capture, and feedback dispatch (Telegram/Webhook/File)
  graph-check    Check code-review-graph MCP server and repository filters
  graph-sync     Build or incrementally update code-review-graph AST database
  graph-build    Alias for graph-sync (supports --full, --status)
  graph-impact   Determine blast radius and affected flows for symbol or file
  graph-arch     Architectural overview, coupling hotspots, and bridge nodes
  patch          Deterministic AST code patching (replace-func)
  resolve        Semantic and test-gated conflict resolution (--docs, --code)
  conflict-check Predict branch merge conflict risks and AST symbol collisions
""")

RECENT_DONE_LIMIT = entities.RECENT_DONE_LIMIT
compile_issues_board = entities.compile_issues_board


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

    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")

    profile_arg = _flag_value(args, "--profile")
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

    slug = _require_entity_name(args[0].lower(), "along start <slug> [--approved] [--worktree] [--profile <profile>]")
    issue = entities.find_issue_by_slug(repo_root, slug)
    if not issue:
        print(f"[Error] Issue '{slug}' not found in .along/ISSUES/.", file=sys.stderr)
        sys.exit(1)

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

    entities.sync_issues_board(repo_root, recent_done_limit=RECENT_DONE_LIMIT)

    title = new_fm.get("title", issue["slug"].replace("-", " ").capitalize())
    st = session.init_session(repo_root, issue["slug"], title=title, profile=profile_val)
    sdir = session.get_session_dir(repo_root, issue["slug"])
    key = session.current_session_key()
    # Starting an issue is not a plan approval: approval comes from the user (ExitPlanMode,
    # or 'along plan approve' after an explicit yes); --approved is for scripted runs and is
    # held to the same check as 'along plan approve' [bug--plan-approval-self-and-lost].
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
    """`along plan approve [<slug>]` / `along plan status` for this agent session.

    See [feat--plan-approval-exit-plan-mode].
    """
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along plan approve [<slug>] [--plan-file <path>] [--confirm-destructive] [--confirm-external]")
        print("                                     Record the user's approval of the plan (run only after an explicit yes);")
        print("                                     --plan-file writes the approved plan into the blackboard plan.md;")
        print("                                     --confirm-destructive explicitly confirms destructive commands (rm, reset --hard);")
        print("                                     --confirm-external explicitly confirms remote network commands (git push, pr create)")
        print("       along plan approve --closeout <slug>... | --closeout --ready")
        print("                                     Record the user's approval to close these issues out (after an explicit yes)")
        print("       along plan status             Show this session's binding, phase and approval")
        sys.exit(0)
    sub = args[0].lower()
    key = session.current_session_key()
    if sub == "approve" and "--closeout" in args:
        # [feat--parallel-session-closeout] REQ-6: the user approved closing these issues out.
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
        plan_file = _flag_value(args, "--plan-file")
        if "--plan-file" in args and not plan_file:
            print("[Error] --plan-file needs a path.", file=sys.stderr)
            sys.exit(2)
        if plan_file and not slug:
            print("[Error] --plan-file needs an issue: 'along start <slug>' first, or pass <slug>.", file=sys.stderr)
            sys.exit(2)
        # The agent can run this itself: it counts only after a user message newer than the
        # plan. [bug--plan-approval-self-and-lost] REQ-2
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
        confirm_dest = "--confirm-destructive" in args
        confirm_ext = "--confirm-external" in args
        if confirm_dest:
            if via == session.APPROVED_VIA_CLI_UNVERIFIED:
                print("[Error] Destructive operations cannot be confirmed without a verified user prompt in chat.",
                      file=sys.stderr)
                sys.exit(2)
            session.confirm_destructive(repo_root, slug=slug, key=key, via=via)
        if confirm_ext:
            session.confirm_external(repo_root, slug=slug, key=key)
        if slug:
            # [bug--session-records-not-captured] REQ-1: the approved plan is recorded.
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
            session.set_session_phase(repo_root, "execution", slug=slug, plan_approved=True)
            plan_now = textio.read_text(os.path.join(session.get_session_dir(repo_root, slug), "plan.md"), strict=False)
            session.mark_approval(repo_root, key, via, plan_now)
            sha = session.plan_sha256(plan_now)
            trace_extra = f", plan_sha256: {sha[:12]}" if sha else ""
            if confirm_dest:
                trace_extra += ", confirmed_destructive: true"
            if confirm_ext:
                trace_extra += ", confirmed_external: true"
            session.append_trace(repo_root, slug, f"plan approved (along plan approve) approved_via: {via}{trace_extra}")
            session.append_event(repo_root, slug, key, "approve")
            dest_msg = " [destructive confirmed]" if confirm_dest else ""
            ext_msg = " [external confirmed]" if confirm_ext else ""
            print(f"-> Plan approved for '{slug}' (session: {key or 'none'}, via: {via}){dest_msg}{ext_msg}.")
        elif key:
            session.record_plan_approval(repo_root, key, via)
            dest_msg = " [destructive confirmed]" if confirm_dest else ""
            ext_msg = " [external confirmed]" if confirm_ext else ""
            print(f"-> Plan approved for session {key}; it applies to the next 'along start <slug>'{dest_msg}{ext_msg}.")
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
        print(f"Destructive: {str(session.is_destructive_confirmed(repo_root, slug=slug, key=key)).lower()}")
        print(f"External:    {str(session.is_external_confirmed(repo_root, slug=slug, key=key)).lower()}")
        sys.exit(0)
    print(f"[Error] Unknown plan subcommand '{sub}'. Use: approve, status.", file=sys.stderr)
    sys.exit(2)


def _cli_approval_or_exit(repo_root: str, slug: str) -> str:
    """Hold a CLI plan approval of `slug` to the user's last message; its `approved_via`.

    [bug--plan-approval-self-and-lost] REQ-2
    """
    key = session.current_session_key()
    refusal, via = session.check_cli_approval(
        repo_root, key, os.path.join(session.get_session_dir(repo_root, slug), "plan.md"))
    if refusal:
        print(f"[Error] Plan approval refused: {refusal}.", file=sys.stderr)
        sys.exit(2)
    session.append_trace(repo_root, slug, f"plan approved (along scratch; approved_via: {via})")
    return via


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
        slug = _require_entity_name(args[1].lower(), "along history append <slug> [summary]")
        summary = " ".join(args[2:]).strip() if len(args) > 2 else None
        res = lifecycle.append_history_entry(repo_root, slug, summary=summary)
        sys.exit(res)
    else:
        print(f"[Error] Unknown history subcommand '{subcmd}'. Run 'along history --help'.", file=sys.stderr)
        sys.exit(1)


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

    # Declared test policy [bug--test-gate-no-tests-policy]
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


def _doctor_runtime_checks(repo_root: str, errors: int, warnings: int) -> Tuple[int, int]:
    """Runtime section of `along doctor`: who runs, what is enforced, environment hazards.

    See [feat--cowork-runtime-support] and the capability matrix in
    docs/topic--runtime-hooks-and-gates.md.
    """
    from alongkit import runtime

    agent = entities.detect_agent()
    report = runtime.runtime_report(repo_root, agent)
    print(f"\n--- Runtime: {agent} ---")
    tag = "[OK]" if report["enforcement"] == runtime.MECHANICAL else "[WARN]"
    print(f"{tag} Gate enforcement: {report['enforcement']}. {report['explanation']}")
    if report["enforcement"] != runtime.MECHANICAL:
        warnings += 1
    else:
        # Registered is not the same as firing: the hook writes a heartbeat on every run.
        beat = runtime.last_heartbeat(repo_root, agent)
        if beat:
            print(f"[OK] Last {agent} hook run in this repository: {beat}.")
        else:
            print(f"[WARN] No {agent} hook run recorded in this repository yet "
                  "(.along/diagnostics/hook_heartbeat.json). If this session already used tools, "
                  "the runtime is not loading the hooks; restart it or check its hook settings.")
            warnings += 1

    if report["python_supported"]:
        print(f"[OK] Python {report['python']} is supported (>= 3.10).")
    else:
        print(f"[FAIL] Python {report['python']} is below the supported minimum 3.10.")
        errors += 1

    if report["stale_index_lock"]:
        print("[WARN] .git/index.lock exists: git writes will fail. If no git process is running, the "
              "folder likely forbids deletes (Claude Cowork without delete permission): grant delete "
              "permission for the folder, then remove the lock.")
        warnings += 1

    symlinks = proc.git(["config", "--get", "core.symlinks"], cwd=repo_root)
    core_symlinks = symlinks.stdout.strip() if symlinks.ok else None
    if runtime.is_cross_os_mount(repo_root, fs_type=report["fs_type"], core_symlinks=core_symlinks):
        fs = report["fs_type"] or "unknown fs"
        print(f"[WARN] Repository is on a cross-OS or VM-mounted filesystem ({fs}, core.symlinks="
              f"{core_symlinks or 'unset'}): do not run 'along worktree' from this environment.")
        warnings += 1
    return errors, warnings


def _doctor_zombie_docs_checks(repo_root: str, warnings: int) -> Tuple[int, List[dict]]:
    """Scan docs/ directories for abandoned zombie stubs."""
    zombies = []
    today = datetime.now().date()
    ignored = set(repo.IGNORED_DIRS) | set(repo.PROVIDER_DIRS)

    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in ignored]
        if os.path.basename(root) != "docs":
            continue
        for f in files:
            if not f.endswith(".md") or f.lower() in ("index.md", "readme.md"):
                continue
            fpath = os.path.join(root, f)
            try:
                content = textio.read_text(fpath, strict=False)
                fm, body, _ = frontmatter.try_parse(content)
                if not fm or fm.get("protocol") != "along":
                    continue
                created_str = str(fm.get("created", ""))
                age_days = None
                if created_str:
                    try:
                        c_date = datetime.strptime(created_str[:10], "%Y-%m-%d").date()
                        age_days = (today - c_date).days
                    except ValueError:
                        pass
                body_lines = [
                    line.strip()
                    for line in (body or "").splitlines()
                    if line.strip() and not line.strip().startswith("#")
                ]
                is_placeholder = (
                    "Document system components and engineering guidelines here" in (body or "")
                    or len(body_lines) < 3
                )
                if is_placeholder and (age_days is None or age_days >= 7):
                    rel = repo.safe_relpath(fpath, repo_root).replace("\\", "/")
                    zombies.append({
                        "path": rel,
                        "lines": len(body_lines),
                        "created": created_str or "unknown",
                        "age_days": age_days,
                    })
            except (OSError, UnicodeDecodeError, ValueError, KeyError, AttributeError):
                continue

    if zombies:
        print(f"\n[WARN: zombie-stub] Detected {len(zombies)} abandoned zombie stub(s) in documentation:")
        for z in zombies:
            age_disp = f"{z['age_days']}d old" if z['age_days'] is not None else "unknown age"
            print(f"  - {z['path']}: {z['lines']} content line(s), created {z['created']} ({age_disp}). Populate with real content or prune.")
        warnings += len(zombies)
    else:
        print("[OK] Knowledge Base articles clean: no abandoned zombie stubs detected.")

    return warnings, zombies


def handle_doctor_command(repo_root: str, args: List[str]):
    if args and args[0] in ("-h", "--help", "help"):
        print("Usage: along doctor [entities|docs|--entities|--docs] [--fix]")
        print("  (no args)            Report protocol, hooks, runtime, bindings, doc quality and blackboard health")
        print("  entities [--fix]     Validate entity schemas and references; --fix drops dangling milestone fields")
        print("  docs                 Validate documentation quality and detect abandoned zombie stubs")
        sys.exit(0)
    check_entities = "--entities" in args or (bool(args) and args[0].lower() == "entities")
    if check_entities:
        print("=== Along Entity Graph Validation (Doctor) ===")
        if "--fix" in args:
            fixed = entities.drop_dangling_milestones(repo_root)
            if fixed:
                print(f"-> Removed {len(fixed)} dangling milestone field(s):")
                for rel in fixed:
                    print(f"  - {rel}")
            else:
                print("-> No dangling milestone fields to remove.")
        report = entities.validate_entities(repo_root)
        print(f"Scanned {report['scanned']} entities across .along/.")
        errs = report["errors"]
        warns = report["warnings"]
        if errs:
            print(f"\n[FAIL] Found {len(errs)} entity schema error(s):")
            for path, msg in errs:
                print(f"  - {path}: {msg}")
        else:
            print("\n[OK] All entity schemas, enums, mandatory fields, and graph references valid.")

        if warns:
            print(f"\n[WARN] Found {len(warns)} entity warning(s):")
            for path, msg in warns:
                print(f"  - {path}: {msg}")

        print(f"\nEntity Doctor Summary: {len(errs)} errors, {len(warns)} warnings.")
        sys.exit(1 if len(errs) > 0 else 0)

    check_docs = "--docs" in args or (bool(args) and args[0].lower() == "docs")
    if check_docs:
        print("=== Along Knowledge Base Quality Validation (Doctor) ===")
        warns, zombies = _doctor_zombie_docs_checks(repo_root, 0)
        print(f"\nDocs Doctor Summary: 0 errors, {len(zombies)} warning(s).")
        sys.exit(0)

    print("=== Along Protocol Diagnostics (Doctor) ===")
    errors = 0
    warnings = 0

    along_dir = os.path.join(repo_root, ".along")
    if not os.path.exists(along_dir):
        print("[FAIL] Missing .along/ directory.")
        errors += 1
    else:
        print("[OK] .along/ directory exists.")

    # Check .gitattributes
    gitattributes_file = os.path.join(repo_root, ".gitattributes")
    if not os.path.exists(gitattributes_file):
        print("[WARN] Missing .gitattributes (recommended for merge=union on HISTORY.md/DECISIONS.md).")
        warnings += 1
    else:
        ga_content = textio.read_text(gitattributes_file, strict=False)
        if "merge=union" in ga_content:
            print("[OK] .gitattributes configured with merge=union.")
        else:
            print("[WARN] .gitattributes exists but lacks merge=union for .along/ files.")
            warnings += 1

    # Check Along merge drivers (along git setup)
    from alongkit import merge as along_merge
    driver_info = along_merge.status(repo_root)
    if driver_info["git"]:
        if along_merge.is_configured(driver_info):
            print("[OK] Along merge drivers registered (projection, frontmatter).")
        else:
            print("[WARN] Along merge drivers not fully registered. Run `along git setup`.")
            warnings += 1
        if driver_info["pending_resync"]:
            print("[WARN] Projections kept as 'ours' in a merge; run `along git sync`: "
                  + ", ".join(driver_info["pending_resync"]))
            warnings += 1

        # Check Git release tag push configuration and release tag integrity [bug--release-tags-not-pushed]
        follow_tags = proc.git(["config", "--local", "--get", "push.followTags"], cwd=repo_root)
        if not follow_tags.ok or follow_tags.stdout.strip().lower() != "true":
            print("[WARN] Git push.followTags is not configured (release tags will not be pushed by default). "
                  "Run `along git setup` (or `git config push.followTags true`).")
            warnings += 1
        else:
            print("[OK] Git push.followTags is configured.")

        remote_origin = proc.git(["remote", "get-url", "origin"], cwd=repo_root)
        if remote_origin.ok:
            remote_tags_res = proc.git(["ls-remote", "--tags", "origin"], cwd=repo_root, check=False)
            if remote_tags_res.ok:
                remote_tag_lines = remote_tags_res.stdout.splitlines()
                remote_tags = set()
                for rline in remote_tag_lines:
                    rparts = rline.split()
                    if len(rparts) >= 2 and rparts[1].startswith("refs/tags/"):
                        rtag = rparts[1][len("refs/tags/"):].split("^{}")[0]
                        remote_tags.add(rtag)

                local_tags_res = proc.git(
                    ["for-each-ref", "--format=%(refname:short) %(objecttype)", "refs/tags/v*"],
                    cwd=repo_root,
                    check=False,
                )
                if local_tags_res.ok:
                    local_release_tags = [
                        tline.split()[0]
                        for tline in local_tags_res.stdout.splitlines()
                        if tline.strip() and tline.split()[-1] == "tag"
                    ]
                    unpushed_tags = [t for t in local_release_tags if t not in remote_tags]
                    if unpushed_tags:
                        print(f"[WARN] Local release tag(s) not present on origin: {', '.join(unpushed_tags)}. "
                              "Push with: git push origin --tags")
                        warnings += 1

        release_commits = proc.git(["log", "--grep=^release: v", "--format=%H %s"], cwd=repo_root, check=False)
        if release_commits.ok:
            for rline in release_commits.stdout.splitlines():
                if not rline.strip():
                    continue
                rparts = rline.split(maxsplit=1)
                if len(rparts) < 2:
                    continue
                sha, subject = rparts
                m = re.match(r"^release:\s+(v\d+\.\d+\.\d+)\b", subject)
                if m:
                    expected_tag = m.group(1)
                    tag_check = proc.git(
                        ["tag", "-l", "--format=%(refname:short) %(objecttype)", expected_tag],
                        cwd=repo_root,
                        check=False,
                    )
                    has_tag = tag_check.ok and tag_check.stdout.strip().startswith(expected_tag)
                    if not has_tag:
                        print(f"[WARN] Release commit {sha[:7]} ({subject}) has no matching annotated tag '{expected_tag}'. "
                              f"Create with: git tag -a {expected_tag} -m \"release: {expected_tag}\" {sha[:7]}")
                        warnings += 1

    # Check per-machine diagnostics committed before the directory ignored itself
    from alongkit import gitgates
    tracked_diag = gitgates.tracked_diagnostics(repo_root)
    if tracked_diag:
        print(f"[WARN] {len(tracked_diag)} per-machine diagnostics file(s) tracked in git "
              f"({', '.join(tracked_diag[:3])}{', ...' if len(tracked_diag) > 3 else ''}). "
              "Run `along migrate --apply` (or `git rm --cached` them) and commit.")
        warnings += 1

    # Orphan blackboards: no session bound, issue closed or missing
    # [bug--session-records-not-captured] REQ-8.
    orphans = lifecycle.orphan_blackboards(repo_root)
    if orphans:
        print(f"[WARN] {len(orphans)} orphan blackboard(s) in .along/.session/: "
              + ", ".join(f"{slug} ({why})" for slug, why in orphans)
              + ". Run `along scratch purge <slug>`: it archives the record into the session log first.")
        warnings += 1
    else:
        print("[OK] No orphan blackboards.")

    # Stale bindings and in-progress issues nobody is bound to
    # [feat--parallel-session-closeout] REQ-9.
    stale = session.gc_bindings(repo_root, dry_run=True)
    if stale:
        print(f"[WARN] {len(stale)} stale session binding(s) (older than {session.BINDING_MAX_AGE_HOURS} h "
              f"or without a blackboard): {', '.join(stale)}. Run `along session gc`.")
        warnings += 1
    bound = {str(b.get("slug")) for b in session.list_bindings(repo_root) if b.get("slug")}
    unbound = [i["slug"] for i in entities.scan_issues(repo_root) if i.get("status") == "in-progress"
               and i["slug"] not in bound]
    if unbound:
        print(f"[WARN] {len(unbound)} issue(s) in progress with no session bound: {', '.join(unbound)}. "
              "Resume with `along start <slug>`, close them out (`along session list`), or set them back "
              "to open (`along issue update <slug> --status open`).")
        warnings += 1

    # Check uncommitted changes belonging to wrapped issues [bug--wrapped-work-left-uncommitted] REQ-2
    from alongkit import closeout
    c_status = closeout.closeout_status(repo_root)
    wrapped_work = c_status["repository"].get("wrapped", {})
    if wrapped_work:
        total_wrapped_files = sum(len(files) for files in wrapped_work.values())
        print(f"[WARN] {total_wrapped_files} uncommitted file(s) belong to wrapped issue(s):")
        for wkey, wfiles in sorted(wrapped_work.items()):
            wslug = entities.parse_key(wkey)[1]
            print(f"  - {wkey} ({len(wfiles)} file(s)):")
            for wf in wfiles:
                print(f"      {wf}")
            paths_arg = " ".join(wfiles)
            print(f"    Commit with: along commit -i {wslug} --paths {paths_arg}")
            print(f"    Or close out: along session close {wslug}")
        warnings += 1

    # Check DECISIONS
    dec_dir = os.path.join(along_dir, "DECISIONS")
    dec_file = os.path.join(along_dir, "DECISIONS.md")
    if os.path.isdir(dec_dir):
        adr_count = len([f for f in os.listdir(dec_dir) if f.endswith(".md")])
        print(f"[OK] .along/DECISIONS/ modular ADR directory exists ({adr_count} records).")
    elif os.path.exists(dec_file):
        dec_content = textio.read_text(dec_file, strict=False)
        if "## ADR-" in dec_content:
            print("[OK] .along/DECISIONS.md uses decentralized ADR-YYYY-MM-DD--<slug> format.")
        else:
            print("[WARN] .along/DECISIONS.md uses legacy sequential numbering.")
            warnings += 1

    # Check obsolete CONTEXT.md
    context_file = os.path.join(along_dir, "CONTEXT.md")
    if os.path.exists(context_file):
        print("[WARN] .along/CONTEXT.md detected (deprecated in v2.2.0, recommend removal).")
        warnings += 1

    # Check AGENTS.md
    agents_file = os.path.join(repo_root, "AGENTS.md")
    if os.path.exists(agents_file):
        print("[OK] AGENTS.md exists.")
    else:
        print("[FAIL] Missing AGENTS.md at repository root.")
        errors += 1

    # Nested contexts outside any nested git repository: possibly created per manifest folder
    # by older versions. Reported only; consolidation is the repository owner's decision.
    nested = repo.find_unmarked_nested_contexts(repo_root)
    if nested:
        shown = ", ".join(repo.normalize_posix(os.path.relpath(p, repo_root)) for p in nested[:10])
        more = f" (+{len(nested) - 10} more)" if len(nested) > 10 else ""
        print(f"[WARN] {len(nested)} nested .along/ without .git found (possibly created by older Along "
              f"versions): {shown}{more}. Consolidate them into the root by hand, or mark an intentional "
              "one with '\"subproject\": {\"intentional\": true}' in its .along/config.json.")
        warnings += 1

    # Check VISION: one file in .along/, no unresolved imported section, no root copy
    from alongkit import scaffold
    if scaffold.find_root_file(repo_root, scaffold.VISION_FILENAME) and os.path.isdir(along_dir):
        print("[WARN] Root VISION.md coexists with .along/. Run `along migrate --apply` to reconcile.")
        warnings += 1
    if scaffold.find_imported_vision_markers(repo_root):
        print("[WARN] .along/VISION.md has an unresolved 'along:imported-vision needs-restructure' "
              "section. Decompose it (scope/non-goals/roadmap stay; architecture -> docs/; "
              "backlog -> ISSUES/MILESTONES) and remove the markers.")
        warnings += 1
    for note in scaffold.find_root_notes(repo_root):
        print(f"[WARN] Root note {os.path.basename(note)} duplicates the Knowledge Base; route it "
              "into docs/topic--*.md, .along/VISION.md or entities (see /along-init).")
        warnings += 1

    # Check along CLI availability on PATH
    along_cmd = shutil.which("along") or (shutil.which("along.cmd") if sys.platform == "win32" else None)
    if along_cmd:
        print(f"[OK] 'along' CLI executable found on PATH: {along_cmd}")
    else:
        user_along_bin = os.path.join(os.path.expanduser("~"), ".along", "bin")
        print("[WARN] 'along' CLI is not found on PATH.")
        if sys.platform == "win32":
            print(f"       To fix: re-run install.ps1, or add '{user_along_bin}' to your User PATH.")
        else:
            print(f"       To fix: add 'export PATH=\"{user_along_bin}:$PATH\"' to your shell profile (~/.bashrc or ~/.zshrc).")
        warnings += 1

    # Check code-review-graph MCP server
    try:
        from along_graph_check import run_graph_check
        gc = run_graph_check(repo_root)
        if gc["status"] == "healthy":
            print(f"[OK] code-review-graph MCP server ready ({gc['package']}).")
        elif gc["status"] == "degraded":
            print(f"[WARN] code-review-graph MCP server: {gc['summary']}")
            warnings += 1
        else:
            print(f"[FAIL] code-review-graph MCP server: {gc['summary']}")
            errors += 1
    except (OSError, ValueError, AttributeError, RuntimeError) as exc:
        print(f"[WARN] Could not run MCP health check: {exc}")
        warnings += 1

    # Check global user pack repository (~/.along/user-pack/)
    user_pack_dir = os.path.expanduser("~/.along/user-pack")
    if os.path.isdir(user_pack_dir):
        if os.path.isdir(os.path.join(user_pack_dir, ".git")):
            remote_check = proc.git(["remote", "get-url", "origin"], cwd=user_pack_dir, check=False)
            if not remote_check.ok or not remote_check.stdout.strip():
                print("[WARN] Global user pack (~/.along/user-pack) has no git remote configured.")
                warnings += 1
            st_check = proc.git(["status", "--porcelain"], cwd=user_pack_dir, check=False)
            if st_check.ok and st_check.stdout.strip():
                print("[WARN] Global user pack (~/.along/user-pack) has uncommitted changes.")
                warnings += 1
            else:
                print("[OK] Global user pack (~/.along/user-pack) repository clean.")
        else:
            print("[WARN] Global user pack (~/.along/user-pack) is not a git repository.")
            warnings += 1

    # Check Systemic Anomaly Circuit Breaker
    try:
        cb_state, cb_anomaly = circuit.get_breaker_state(repo_root)
        if cb_state == circuit.CircuitState.TRIPPED:
            sig = cb_anomaly.signature if cb_anomaly else "Unknown anomaly"
            cls_name = cb_anomaly.anomaly_class.value if cb_anomaly else "Systemic Anomaly"
            print(f"[FAIL] Systemic Anomaly Circuit Breaker is TRIPPED ({cls_name}: {sig}).")
            print("       Run 'along circuit status' for human remediation steps or 'along circuit reset'.")
            errors += 1
        else:
            print("[OK] Systemic Anomaly Circuit Breaker: CLOSED (normal operation).")
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"[WARN] Could not check circuit breaker status: {exc}")
        warnings += 1

    # Declared test policy: `tests: none` stays visible as debt [bug--test-gate-no-tests-policy].
    from alongkit import verify
    policy = verify.load_policy(repo_root)
    problems = verify.policy_problems(repo_root, policy)
    if problems:
        print("[FAIL] Verify policy invalid: " + "; ".join(problems))
        errors += 1
    elif policy.tests == verify.TESTS_NONE:
        print(f"[WARN] Verify: {policy.describe()}")
        warnings += 1
    else:
        print(f"[OK] Verify: {policy.describe()}")

    # Gate friction [feat--gate-friction-and-bypass-accountability] REQ-4, REQ-5.
    from alongkit import gatestats
    from alongkit.hooks import config as hook_config
    shadowed = hook_config.load_config(repo_root).overridden_gates()
    if shadowed:
        print(f"[WARN] Gates set to shadow by config: {', '.join(shadowed)}")
        warnings += 1
    for row in gatestats.most_bypassed(gatestats.collect(repo_root)):
        print(f"[WARN] Gate '{row.gate}' bypassed {row.bypassed}x vs blocked {row.blocked}x "
              f"({row.bypass_ratio * 100:.0f}%): review whether it is wrong or too strict ('along gates stats').")
        warnings += 1

    # Gate strictness profiles [feat--gate-strictness-profiles] REQ-5
    from alongkit import profiles
    active_prof, prof_source = profiles.resolve_active_profile_with_source(repo_root)
    h_config = hook_config.load_config(repo_root)
    gate_table = hook_config.load_gate_profiles_table(repo_root)
    counts = {"block": 0, "warn": 0, "off": 0}
    matrix_rows = []
    width = max((len(gid) for gid in gate_table), default=20)
    for gid in sorted(gate_table.keys()):
        mode = h_config.get_gate_mode(gid)
        sev = "block" if mode == hook_config.HookMode.ENFORCE else ("off" if mode == hook_config.HookMode.OFF else "warn")
        counts[sev] += 1
        matrix_rows.append((gid, sev))
    print(f"\n--- Gate Strictness Profile: {active_prof} (source: {prof_source}) ---")
    print(f"[OK] Gate strictness profile: {active_prof} (source: {prof_source}) - "
          f"{counts['block']} block, {counts['warn']} warn, {counts['off']} off.")
    print(f"Gate strictness matrix ({len(matrix_rows)} gates):")
    for gid, sev in matrix_rows:
        print(f"  {gid.ljust(width)}  [{sev.upper()}]")

    # Documentation Routing Tree Compliance [gate: doc-routing-compliance]
    from alongkit import repochecks
    doc_candidates = []
    for d_root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in repo.IGNORED_DIRS and not d.startswith(".")]
        for f in files:
            if f.lower() in ("readme.md", "agents.md"):
                doc_candidates.append(os.path.relpath(os.path.join(d_root, f), repo_root).replace("\\", "/"))
    doc_findings = repochecks.check_doc_routing_compliance(
        doc_candidates,
        lambda p: textio.read_text(os.path.join(repo_root, p), strict=False),
        {},
    )
    if doc_findings:
        print(f"[WARN] Documentation Routing Tree: {len(doc_findings)} issue(s) detected [gate: doc-routing-compliance]:")
        for loc, msg in doc_findings:
            print(f"       - {loc}: {msg}")
        warnings += 1
    else:
        print("[OK] Documentation Routing Tree: README.md overview boundaries and AGENTS.md references clean.")

    warnings, _ = _doctor_zombie_docs_checks(repo_root, warnings)

    errors, warnings = _doctor_runtime_checks(repo_root, errors, warnings)

    print(f"\nDoctor Summary: {errors} errors, {warnings} warnings.")
    sys.exit(1 if errors > 0 else 0)


def _flag_value(args: List[str], flag: str) -> Optional[str]:
    """Value following `flag` in `args`, or None."""
    if flag in args:
        idx = args.index(flag)
        if idx + 1 < len(args) and not args[idx + 1].startswith("--"):
            return args[idx + 1]
    return None


def handle_git_command(repo_root: str, args: List[str]):
    from alongkit import merge

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
        kb_script = resolve_tool_script("along_kb_sync.py", repo_root)
        done = merge.resync(repo_root, kb_script=kb_script)
        for path in done:
            print(f"   -> Recompiled {path}")
        print("-> Projections synchronized.")
        sys.exit(0)

    print(f"[Error] Unknown git subcommand: {subcmd}. Use setup, status, or sync.", file=sys.stderr)
    sys.exit(1)


def handle_gates_command(repo_root: str, args: List[str]):
    import argparse
    from alongkit import gitgates

    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along gates check [--hook {pre-commit,commit-msg}] [--ci] [--range COMMIT_RANGE] [--no-links] [--json] [hook_args...]")
        print("  Run the commit-time gate subset outside agent runtimes (git hooks, CI).")
        print("       along gates stats [--since YYYY-MM-DD]")
        print("  Per-gate counts of blocks, shadow warnings and recorded bypasses.")
        sys.exit(0)

    subcmd = args[0].lower()
    if subcmd == "stats":
        # [feat--gate-friction-and-bypass-accountability] REQ-5
        from alongkit import gatestats
        print(gatestats.format_table(gatestats.collect(repo_root, _flag_value(args, "--since"))))
        sys.exit(0)
    if subcmd != "check":
        print(f"[Error] Unknown gates subcommand: {subcmd}. Use check or stats.", file=sys.stderr)
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
        kb_script = None if opts.no_links else resolve_tool_script("along_kb_sync.py", repo_root)
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


def handle_rules_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along rules [attach|status|diff|restore]")
        print("Subcommands:")
        print("  attach [--on-conflict preserve|overwrite|diff] [--force]")
        print("                  Detect project stack and attach relevant engineering rule packs")
        print("  status [--json] Audit installed rule packs against Along global templates")
        print("  diff [rule]     Display unified diff of local rule modifications against template")
        print("  restore [rule]  Restore pristine Along template for rule (backs up modified copy)")
        sys.exit(0)
    
    subcmd = args[0].lower()
    try:
        from alongkit import rules
    except ImportError:
        print("[Error] alongkit.rules not found.", file=sys.stderr)
        sys.exit(1)

    if subcmd == "attach":
        on_conflict = "preserve"
        if "--overwrite" in args or "--force" in args:
            on_conflict = "overwrite"
        elif "--diff" in args:
            on_conflict = "diff"
        elif "--strategy" in args:
            idx = args.index("--strategy")
            if idx + 1 < len(args):
                on_conflict = args[idx + 1].lower()
        elif "--on-conflict" in args:
            idx = args.index("--on-conflict")
            if idx + 1 < len(args):
                on_conflict = args[idx + 1].lower()

        rules.attach_rules(repo_root, on_conflict=on_conflict)
        sys.exit(0)
    elif subcmd == "status":
        as_json = "--json" in args
        results = rules.audit_rules(repo_root)
        if as_json:
            import json
            print(json.dumps(results, indent=2))
        else:
            if not results:
                print("No rule packs configured or required.")
            else:
                print(f"Along Rule Packs Audit ({len(results)} rules):")
                for r in results:
                    status_tag = f"[{r['status'].upper()}]"
                    print(f"  {status_tag:<14} {r['rule']:<28} - {r['detail']}")
        sys.exit(0)
    elif subcmd == "diff":
        target_rule = args[1] if len(args) > 1 and not args[1].startswith("-") else None
        if not target_rule:
            audits = rules.audit_rules(repo_root)
            modified = [a["rule"] for a in audits if "modified" in a["status"]]
            if not modified:
                print("No modified rule packs found.")
                sys.exit(0)
            for r in modified:
                d = rules.diff_rule(repo_root, r)
                if d:
                    print(f"\n--- Diff: {r} ---")
                    print(d)
            sys.exit(0)
        else:
            d = rules.diff_rule(repo_root, target_rule)
            if d:
                print(d)
            else:
                print(f"No differences found for '{target_rule}'.")
            sys.exit(0)
    elif subcmd == "restore":
        target_rule = args[1] if len(args) > 1 and not args[1].startswith("-") else None
        restored = rules.restore_rule(repo_root, target_rule)
        if not restored:
            print("No rules restored (already pristine or template not found).")
        else:
            print(f"Successfully restored {len(restored)} rule pack(s): {', '.join(restored)}")
        sys.exit(0)
    else:
        print(f"[Error] Unknown rules subcommand: {subcmd}. Available: attach, status, diff, restore.", file=sys.stderr)
        sys.exit(1)


def handle_tool_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along tool [classify|list|explain]")
        print("Subcommands:")
        print("  classify <pattern> <class> [--global]")
        print("                  Record tool nature classification in repo or global user pack")
        print("  list [--json]   List classified tools, defaults, and active rules across layers")
        print("  explain \"<cmd>\" Explain tool nature classification and matching rules")
        sys.exit(0)

    subcmd = args[0].lower()
    from alongkit.hooks import toolnature

    if subcmd == "classify":
        if len(args) < 3:
            print("[Error] Missing arguments for 'along tool classify'.", file=sys.stderr)
            print("Usage: along tool classify <pattern> <class> [--global]", file=sys.stderr)
            sys.exit(1)
        pattern = args[1]
        tool_class = args[2]
        is_global = "--global" in args
        try:
            msg = toolnature.classify_tool(pattern, tool_class, repo_root=repo_root, is_global=is_global)
            print(f"-> {msg}")
            sys.exit(0)
        except ValueError as e:
            print(f"[Error] {e}", file=sys.stderr)
            sys.exit(1)

    elif subcmd == "list":
        is_json = "--json" in args
        tools = toolnature.list_tools(repo_root=repo_root)
        if is_json:
            print(json.dumps(tools, indent=2))
            sys.exit(0)
        print("=== Classified Tools & Nature Rules ===")
        print(f"{'Tool':<20} {'Default':<18} {'Rules':<6} {'Layer'}")
        print("-" * 55)
        for t in tools:
            name = t["tool"]
            default_cls = t["default"]
            num_rules = len(t["rules"])
            layer = t["layer"]
            print(f"{name:<20} {default_cls:<18} {num_rules:<6} {layer}")
        sys.exit(0)

    elif subcmd == "explain":
        if len(args) < 2:
            print("[Error] Missing command to explain.", file=sys.stderr)
            print("Usage: along tool explain \"<command>\"", file=sys.stderr)
            sys.exit(1)
        cmd_to_explain = args[1]
        explanation = toolnature.explain_command(cmd_to_explain, repo_root=repo_root)
        print(explanation)
        sys.exit(0)

    else:
        print(f"[Error] Unknown tool subcommand: '{subcmd}'. Available: classify, list, explain.", file=sys.stderr)
        sys.exit(1)


def handle_budget_command(repo_root: str, args: List[str]):
    if "-h" in args or "--help" in args or "help" in args:
        print("Usage:")
        print("  along budget [--json] [--check]")
        print("  along budget check-prompt <file|payload> [--json] [--check] [--allow-oversized]")
        sys.exit(0)
    try:
        from alongkit import budget
    except ImportError:
        print("[Error] alongkit.budget not found.", file=sys.stderr)
        sys.exit(1)

    sub = args[0].lower() if args else ""
    if sub == "check-prompt":
        as_json = "--json" in args
        check_mode = "--check" in args
        allow_oversized = "--allow-oversized" in args
        non_flags = [a for a in args[1:] if not a.startswith("--")]

        if non_flags and non_flags[0] != "-":
            target = non_flags[0]
            # If target looks like a relative path and exists relative to repo_root, resolve it
            if not os.path.isabs(target) and not os.path.exists(target):
                repo_rel = os.path.join(repo_root, target)
                if os.path.exists(repo_rel):
                    target = repo_rel
        else:
            if not sys.stdin.isatty():
                target = sys.stdin.read()
            else:
                print("[Error] Missing payload or file for check-prompt.", file=sys.stderr)
                print("Usage: along budget check-prompt <file|payload> [--json] [--check] [--allow-oversized]", file=sys.stderr)
                sys.exit(1)

        report = budget.check_prompt(target, allow_oversized=allow_oversized)
        if as_json:
            import json
            print(json.dumps(report, indent=2))
        else:
            print(budget.format_prompt_budget_text(report))

        if check_mode and not report.get("passed", True):
            sys.exit(1)
        sys.exit(0)

    as_json = "--json" in args
    check_mode = "--check" in args

    # Limits are configurable per repo [debt--agents-md-budget-project-specifics].
    report = budget.measure_context(repo_root, limits=budget.config_limits(repo_root))

    if as_json:
        import json
        print(json.dumps(report, indent=2))
    else:
        print(budget.format_budget_text(report))

    if check_mode and not report.get("all_passed", True):
        sys.exit(1)
    sys.exit(0)


def handle_patch_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along patch replace-func <target_file> <function_name> <replacement_code_file>")
        sys.exit(0)

    subcmd = args[0].lower()
    if subcmd == "replace-func":
        if len(args) < 4:
            print("[Error] Usage: along patch replace-func <target_file> <function_name> <replacement_code_file>", file=sys.stderr)
            sys.exit(1)
        target_file = args[1]
        func_name = args[2]
        repl_file = args[3]

        if not os.path.isabs(target_file):
            target_file = os.path.normpath(os.path.join(repo_root, target_file))
        if not os.path.isabs(repl_file):
            repl_file = os.path.normpath(os.path.join(repo_root, repl_file))

        from alongkit import patcher
        try:
            patcher.replace_function_in_file(target_file, func_name, repl_file)
            print(f"-> [AST Patch] Successfully replaced '{func_name}' in {repo.safe_relpath(target_file, repo_root)}.")
            sys.exit(0)
        except patcher.PatcherError as exc:
            print(f"[Error] AST Patch failed: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"[Error] Unknown patch subcommand: '{subcmd}'. Available: replace-func", file=sys.stderr)
        sys.exit(1)


def handle_devenv_command(repo_root: str, args: List[str]):
    from alongkit import devenv
    reinstall = "--reinstall" in args
    success, msg = devenv.setup_dev_environment(repo_root, reinstall=reinstall)
    if not success:
        print(f"[Error] Dev environment setup failed: {msg}", file=sys.stderr)
        sys.exit(1)
    print(f"-> {msg}")
    sys.exit(0)


def handle_circuit_command(repo_root: str, args: List[str]):
    sub = args[0].lower() if args else "status"

    if sub in ("status", "info"):
        as_json = "--json" in args
        state, anomaly = circuit.get_breaker_state(repo_root)
        if as_json:
            out = {
                "state": state.value,
                "anomaly": anomaly.to_dict() if anomaly else None,
            }
            print(json.dumps(out, indent=2))
        else:
            if state == circuit.CircuitState.TRIPPED and anomaly:
                print(circuit.format_escalation_report(anomaly))
            else:
                print(f"[Circuit Breaker] Status: {state.value.upper()} (Normal Operation)")
        sys.exit(0 if state != circuit.CircuitState.TRIPPED else 1)

    elif sub == "trip":
        cls_num = 1
        reason = "Manual circuit breaker trip requested"
        idx = 1
        while idx < len(args):
            arg = args[idx]
            if arg in ("--class", "-c") and idx + 1 < len(args):
                try:
                    cls_num = int(args[idx + 1])
                except ValueError:
                    print(f"[Error] --class expects an integer (1-5), got '{args[idx + 1]}'", file=sys.stderr)
                    sys.exit(1)
                idx += 2
            elif arg in ("--reason", "-r", "--sig") and idx + 1 < len(args):
                reason = args[idx + 1]
                idx += 2
            else:
                idx += 1

        cls_map = {
            1: circuit.AnomalyClass.CLASS_1_VCS_CORRUPTION,
            2: circuit.AnomalyClass.CLASS_2_OS_CONTENTION,
            3: circuit.AnomalyClass.CLASS_3_GLOBAL_ENV,
            4: circuit.AnomalyClass.CLASS_4_PROCESS_CASCADE,
            5: circuit.AnomalyClass.CLASS_5_SYNTAX_CHURN,
        }
        selected_cls = cls_map.get(cls_num, circuit.AnomalyClass.CLASS_1_VCS_CORRUPTION)
        now_iso = datetime.now(timezone.utc).isoformat()
        rem_map = {
            1: circuit.REMEDIATION_CLASS_1,
            2: circuit.REMEDIATION_CLASS_2,
            3: circuit.REMEDIATION_CLASS_3,
            4: circuit.REMEDIATION_CLASS_4,
            5: circuit.REMEDIATION_CLASS_5,
        }
        anomaly = circuit.AnomalyMatch(
            anomaly_class=selected_cls,
            signature=reason,
            detail="Tripped manually via along circuit trip",
            impact="Automated tool execution is halted.",
            remediation=rem_map.get(cls_num, circuit.REMEDIATION_CLASS_1),
            timestamp=now_iso,
        )
        circuit.trip_breaker(repo_root, anomaly)
        sys.exit(0)

    elif sub == "reset":
        force = "--force" in args or "-f" in args
        success, msg = circuit.reset_breaker(repo_root, force=force)
        if success:
            print(f"[OK] {msg}")
            sys.exit(0)
        else:
            print(f"[FAIL] {msg}", file=sys.stderr)
            sys.exit(1)

    elif sub in ("verify", "check", "probe"):
        healthy, issues = circuit.run_health_probe(repo_root)
        if healthy:
            print("[OK] Environment health probe PASSED. No systemic anomalies detected.")
            sys.exit(0)
        else:
            print("[FAIL] Environment health probe FAILED:")
            for iss in issues:
                print(f"  - {iss}")
            sys.exit(1)

    elif sub in ("-h", "--help", "help"):
        print("Usage: along circuit [status|trip|reset|verify] [options]")
        print("")
        print("Commands:")
        print("  status [--json]           Display current circuit breaker state and active anomaly report")
        print("  trip [--class N] [-r MSG] Manually trip the circuit breaker with a specified anomaly class (1-5)")
        print("  reset [--force]           Verify environment health probe and reset circuit breaker to CLOSED")
        print("  verify                    Execute environment health probe without altering breaker state")
        sys.exit(0)

    else:
        print(f"[Error] Unknown circuit subcommand: '{sub}'. Run 'along circuit --help'.", file=sys.stderr)
        sys.exit(1)


def _get_active_telemetry_endpoint(explicit_endpoint: Optional[str] = None) -> str:
    if explicit_endpoint:
        return explicit_endpoint
    env_traces = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    if env_traces:
        return env_traces
    along_ep = os.environ.get("ALONG_TELEMETRY_ENDPOINT")
    if along_ep:
        return along_ep
    env_otlp = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if env_otlp:
        return f"{env_otlp.rstrip('/')}/v1/traces"
    return "http://localhost:4318/v1/traces"


def _test_endpoint_connectivity(endpoint: str, timeout: float = 1.5) -> Tuple[bool, str]:
    import urllib.error
    import urllib.request
    from alongkit.telemetry.otlp import build_otlp_payload

    payload = build_otlp_payload(service_name="actdim-along", resource_attrs={}, spans=[])
    data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    req = urllib.request.Request(
        url=endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            return True, f"HTTP {status}"
    except urllib.error.HTTPError as exc:
        return True, f"HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", str(exc))
        return False, str(reason)


def _telemetry_status(repo_root: str, args: List[str]):
    as_json = "--json" in args
    explicit_endpoint = None
    idx = 0
    while idx < len(args):
        if args[idx] in ("--endpoint", "-e") and idx + 1 < len(args):
            explicit_endpoint = args[idx + 1]
            idx += 2
        else:
            idx += 1

    endpoint = _get_active_telemetry_endpoint(explicit_endpoint)
    spool_dir = os.path.join(repo_root, ".along", "telemetry", "spool")

    wal_files: List[Tuple[str, int]] = []
    total_bytes = 0
    if os.path.isdir(spool_dir):
        try:
            for entry in sorted(os.scandir(spool_dir), key=lambda e: e.name):
                if entry.is_file() and entry.name.endswith(".wal"):
                    size = entry.stat().st_size
                    wal_files.append((entry.name, size))
                    total_bytes += size
        except OSError:
            pass

    connected, conn_detail = _test_endpoint_connectivity(endpoint, timeout=1.5)

    if as_json:
        result = {
            "wal_count": len(wal_files),
            "total_bytes": total_bytes,
            "endpoint": endpoint,
            "connected": connected,
            "endpoint_status": conn_detail,
            "spool_dir": spool_dir,
            "wal_files": [{"name": name, "size_bytes": sz} for name, sz in wal_files],
        }
        print(json.dumps(result, indent=2))
    else:
        conn_str = f"connected ({conn_detail})" if connected else f"unreachable ({conn_detail})"
        print("Along Telemetry Status:")
        print(f"  Endpoint:      {endpoint} [{conn_str}]")
        print(f"  Spool Dir:     {spool_dir}")
        print(f"  Pending WALs:  {len(wal_files)} file(s)")
        print(f"  Spooled Size:  {total_bytes} bytes")
        if wal_files:
            print("  WAL Files:")
            for name, sz in wal_files:
                print(f"    - {name} ({sz} bytes)")
    sys.exit(0)


def _telemetry_flush(repo_root: str, args: List[str]):
    explicit_endpoint = None
    idx = 0
    while idx < len(args):
        if args[idx] in ("--endpoint", "-e") and idx + 1 < len(args):
            explicit_endpoint = args[idx + 1]
            idx += 2
        else:
            idx += 1

    endpoint = _get_active_telemetry_endpoint(explicit_endpoint)
    spool_dir = os.path.join(repo_root, ".along", "telemetry", "spool")

    wal_paths: List[str] = []
    if os.path.isdir(spool_dir):
        try:
            for entry in sorted(os.scandir(spool_dir), key=lambda e: e.name):
                if entry.is_file() and entry.name.endswith(".wal"):
                    wal_paths.append(entry.path)
        except OSError:
            pass

    if not wal_paths:
        print("No pending telemetry spans in spool.")
        sys.exit(0)

    from alongkit.telemetry.otlp import OTLPExporter

    all_spans: List[Dict[str, Any]] = []
    valid_wal_paths: List[str] = []
    for p in wal_paths:
        try:
            with open(p, "r", encoding="utf-8") as f:
                file_has_spans = False
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            span_dict = json.loads(line)
                            all_spans.append(span_dict)
                            file_has_spans = True
                        except json.JSONDecodeError:
                            pass
                if file_has_spans:
                    valid_wal_paths.append(p)
                else:
                    try:
                        os.remove(p)
                    except OSError:
                        pass
        except OSError:
            pass

    if not all_spans:
        print("No pending telemetry spans in spool.")
        sys.exit(0)

    exporter = OTLPExporter(endpoint=endpoint, timeout=5.0)
    success = exporter.export(all_spans, spool_on_failure=False)
    if success:
        for p in valid_wal_paths:
            try:
                os.remove(p)
            except OSError:
                pass
        print(f"Successfully flushed {len(all_spans)} telemetry span(s) to {endpoint}.")
        sys.exit(0)
    else:
        print(
            f"[Error] Failed to flush {len(all_spans)} telemetry span(s) to {endpoint}: network or endpoint failure.",
            file=sys.stderr,
        )
        sys.exit(1)


def handle_telemetry_command(repo_root: Optional[str], args: List[str]):
    effective_root = repo_root or find_repo_root() or os.getcwd()
    sub = args[0].lower() if args else "status"

    if sub in ("-h", "--help", "help"):
        print("Usage: along telemetry [status|flush] [options]")
        print("")
        print("Commands:")
        print("  status [--json] [--endpoint <url>]  Report pending WAL spool files and endpoint connectivity")
        print("  flush  [--endpoint <url>]           Export pending spans from WAL spool to OTLP endpoint")
        sys.exit(0)

    if sub == "status":
        _telemetry_status(effective_root, args[1:])
    elif sub == "flush":
        _telemetry_flush(effective_root, args[1:])
    else:
        print(f"[Error] Unknown telemetry subcommand: '{sub}'. Run 'along telemetry --help'.", file=sys.stderr)
        sys.exit(1)


def handle_run_command(repo_root: Optional[str], args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along run [antigravity|agy] [options] | along run <command...>")
        print("       python scripts/along_exec.py run [antigravity|agy] [options] | run <command...>")
        print("")
        print("Agent Runtime Runner:")
        print("  along run antigravity [--dry-run] [-i|--issue <slug>] [--run-id <id>] [--endpoint <url>] [--binary <path>]")
        print("  Supervise Antigravity agent process, enforce workspace containment, and capture telemetry.")
        print("")
        print("Lifecycle Command Proxy:")
        print("  Execute a shell command behind the Along runtime lifecycle hook and gate pipeline.")
        print("  Commands violating active protocol gates (typography, CLI safety, commit guard)")
        print("  are blocked with exit code 2 and an error message on stderr.")
        sys.exit(0)

    # 1. Antigravity Agent Runtime Runner
    if args[0].lower() in ("antigravity", "agy"):
        sub_args = args[1:]
        dry_run = False
        issue_slug = None
        run_id = None
        endpoint = None
        binary = None
        pass_args: List[str] = []

        i = 0
        while i < len(sub_args):
            arg = sub_args[i]
            if arg in ("--dry-run", "-n"):
                dry_run = True
                i += 1
            elif arg in ("--issue", "-i") and i + 1 < len(sub_args):
                issue_slug = sub_args[i + 1]
                i += 2
            elif arg in ("--run-id",) and i + 1 < len(sub_args):
                run_id = sub_args[i + 1]
                i += 2
            elif arg in ("--endpoint", "-e") and i + 1 < len(sub_args):
                endpoint = sub_args[i + 1]
                i += 2
            elif arg in ("--binary", "-b") and i + 1 < len(sub_args):
                binary = sub_args[i + 1]
                i += 2
            elif arg in ("-h", "--help", "help"):
                print("Usage: along run antigravity [options] [-- <agent-args...>]")
                print("Options:")
                print("  --dry-run, -n          Preview configured environment and parameters without spawning")
                print("  -i, --issue <slug>     Bind run to specific active issue (defaults to in-progress issue)")
                print("  --run-id <id>          Explicit run ID for telemetry grouping")
                print("  -e, --endpoint <url>   OTLP telemetry collector endpoint")
                print("  -b, --binary <path>    Explicit path to Antigravity binary executable")
                sys.exit(0)
            elif arg == "--":
                pass_args.extend(sub_args[i + 1:])
                break
            else:
                pass_args.append(arg)
                i += 1

        from alongkit.runner import AntigravityRunner
        runner = AntigravityRunner(
            repo_root=repo_root,
            issue_slug=issue_slug,
            run_id=run_id,
            otel_endpoint=endpoint,
            binary_path=binary,
            dry_run=dry_run,
            extra_args=pass_args,
        )
        try:
            code = runner.run()
        except RuntimeError as exc:
            sys.stderr.write(f"[Along Runner Error] {exc}\n")
            sys.exit(1)
        sys.exit(code)

    from alongkit.hooks import HookEvent, HookEventType, evaluate_event, load_config
    config = load_config(repo_root)

    cmd_str = " ".join(args)
    effective_root = repo_root or os.getcwd()
    event = HookEvent(
        event_type=HookEventType.PRE_TOOL_USE,
        tool_name="run_command",
        tool_args={"CommandLine": cmd_str},
        workspace_root=effective_root,
        runtime="generic",
    )

    result = evaluate_event(event, repo_root=repo_root, config=config)
    if result.is_denied:
        sys.stderr.write(f"[Along Gate Error] {result.reason}\n")
        sys.exit(2)

    # Resolve arguments for direct execution
    exec_args = list(args)
    if len(exec_args) == 1 and not shutil.which(exec_args[0]):
        try:
            split_args = shlex.split(exec_args[0], posix=(os.name != "nt"))
            if split_args and shutil.which(split_args[0]):
                exec_args = split_args
        except ValueError:
            pass

    code = proc.run_passthrough(exec_args, cwd=repo_root)
    sys.exit(code)


HELP_FLAGS = ("-h", "--help")


def _wants_help(args: List[str]) -> bool:
    """True when -h/--help appears anywhere before a `--` separator."""
    for arg in args:
        if arg == "--":
            return False
        if arg in HELP_FLAGS:
            return True
    return False


#: Commands that read or write the Along board of a context. They work inside an installation
#: only: just `along init` starts one, so nothing else ever creates a `.along/` by side effect.
#: [bug--along-install-marker-ambiguous]
_BOARD_COMMANDS = frozenset({
    "issue", "milestone", "milestones", "start", "begin", "session", "plan", "decision",
    "scratch", "worktree", "wrap", "commit",
})


def _require_installation(cmd: str, repo_root: str) -> None:
    """Exit 2 when a board command runs where Along is not installed."""
    if cmd in _BOARD_COMMANDS and not repo.is_installed(repo_root):
        print(f"[Error] Along is not installed in {repo_root} (no .along/ with Along state). "
              "Run 'along init' there, or run the command inside an installed context.",
              file=sys.stderr)
        sys.exit(2)


def _require_entity_name(name: str, usage: str) -> str:
    """Exit 2 when an entity name looks like a flag ([bug--subcommand-help-as-argument])."""
    if not name or name.startswith("-"):
        print(f"[Error] Invalid name '{name}': entity names cannot start with '-'.", file=sys.stderr)
        print(f"Usage: {usage}", file=sys.stderr)
        sys.exit(2)
    return name


def _print_router_help(cmd: str, handler, repo_root: str, args: List[str]) -> None:
    """Print a router's usage (narrowed to the named subcommand) and exit 0, writing nothing.

    Routers check -h/--help only in args[0]; elsewhere it was taken as a slug
    ([bug--subcommand-help-as-argument]).
    """
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            handler(repo_root, ["--help"])
        except SystemExit:
            pass
    lines = buf.getvalue().splitlines()
    sub = args[0].lower() if args and args[0] not in HELP_FLAGS else None
    matched = []
    if sub:
        for line in lines:
            tokens = [t for t in line.split() if t != "Usage:"][:3]
            if sub in tokens:
                matched.append(line)
    if matched:
        if not any("Usage:" in line for line in matched):
            print(f"Usage: along {cmd} {sub} [args...]")
        print("\n".join(matched))
        print(f"Run 'along {cmd} --help' for all subcommands.")
    else:
        print("\n".join(lines))
    sys.exit(0)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print_help()
        sys.exit(0)

    cmd = sys.argv[1].lower().strip()
    extra_args = sys.argv[2:]
    repo_root = find_repo_root()

    # Routers that parse their own arguments; run/kb/graph/tools pass args through to child commands.
    native_routers = {
        "status": handle_status_command,
        "doctor": handle_doctor_command,
        "circuit": handle_circuit_command,
        "telemetry": handle_telemetry_command,
        "issue": handle_issue_command,
        "milestone": handle_milestone_command,
        "milestones": handle_milestone_command,
        "start": handle_start_command,
        "begin": handle_start_command,
        "session": handle_session_command,
        "plan": handle_plan_command,
        "decision": handle_decision_command,
        "scratch": handle_scratch_command,
        "worktree": handle_worktree_command,
        "git": handle_git_command,
        "gates": handle_gates_command,
        "rules": handle_rules_command,
        "budget": handle_budget_command,
        "context-budget": handle_budget_command,
        "patch": handle_patch_command,
        "history": handle_history_command,
    }
    if cmd in native_routers and _wants_help(extra_args):
        _print_router_help(cmd, native_routers[cmd], repo_root, extra_args)
    _require_installation(cmd, repo_root)

    # 1. Native Entity Management Subcommands
    if cmd == "status":
        handle_status_command(repo_root, extra_args)
    elif cmd == "history":
        handle_history_command(repo_root, extra_args)
    elif cmd == "doctor":
        handle_doctor_command(repo_root, extra_args)
    elif cmd == "circuit":
        handle_circuit_command(repo_root, extra_args)
    elif cmd == "telemetry":
        handle_telemetry_command(repo_root, extra_args)
    elif cmd == "issue":
        handle_issue_command(repo_root, extra_args)
    elif cmd in ("milestone", "milestones"):
        handle_milestone_command(repo_root, extra_args)
    elif cmd in ("start", "begin"):
        handle_start_command(repo_root, extra_args)
    elif cmd == "session":
        handle_session_command(repo_root, extra_args)
    elif cmd == "plan":
        handle_plan_command(repo_root, extra_args)
    elif cmd == "decision":
        handle_decision_command(repo_root, extra_args)
    elif cmd == "scratch":
        handle_scratch_command(repo_root, extra_args)
    elif cmd == "worktree":
        handle_worktree_command(repo_root, extra_args)
    elif cmd == "git":
        handle_git_command(repo_root, extra_args)
    elif cmd == "gates":
        handle_gates_command(repo_root, extra_args)
    elif cmd == "rules":
        handle_rules_command(repo_root, extra_args)
    elif cmd in ("tool", "tools"):
        handle_tool_command(repo_root, extra_args)
    elif cmd in ("budget", "context-budget"):
        handle_budget_command(repo_root, extra_args)
    elif cmd == "patch":
        handle_patch_command(repo_root, extra_args)
    elif cmd in ("dev-env", "devenv"):
        handle_devenv_command(repo_root, extra_args)
    elif cmd == "run":
        handle_run_command(repo_root, extra_args)
    elif cmd == "kb":
        sub = extra_args[0].lower() if extra_args else "sync"
        mapped = "along_kb_sync.py" if sub == "sync" else "along_kb_search.py"
        script_path = resolve_tool_script(mapped, repo_root)
        if script_path:
            code = proc.run_passthrough([sys.executable, script_path] + extra_args[1:], cwd=repo_root)
            sys.exit(code)
    elif cmd == "graph":
        sub = extra_args[0].lower() if extra_args else "check"
        sub_map = {
            "check": "along_graph_check.py",
            "sync": "along_graph_sync.py",
            "build": "along_graph_sync.py",
            "impact": "along_graph_impact.py",
            "arch": "along_graph_arch.py",
            "architecture": "along_graph_arch.py",
        }
        mapped = sub_map.get(sub, "along_graph_check.py")
        args_tail = extra_args[1:] if sub in sub_map else extra_args
        script_path = resolve_tool_script(mapped, repo_root)
        if script_path:
            code = proc.run_passthrough([sys.executable, script_path] + args_tail, cwd=repo_root)
            sys.exit(code)

    # 2. Check if command is an Along Protocol Tool
    if cmd in TOOL_MAPPINGS:
        script_name = TOOL_MAPPINGS[cmd]
        script_path = resolve_tool_script(script_name, repo_root)
        if not script_path:
            print(f"[Error] Could not locate Along tool script: {script_name}", file=sys.stderr)
            print(f"Searched in local scripts/ and global Along home.", file=sys.stderr)
            sys.exit(1)

        # For dash, use uv run if available
        if script_name == "along_dash.py":
            uv_bin = shutil.which("uv")
            if uv_bin:
                full_cmd = [uv_bin, "run", script_path] + extra_args
                code = proc.run_passthrough(full_cmd, cwd=repo_root)
                sys.exit(code)

        full_cmd = [sys.executable, script_path] + extra_args
        code = proc.run_passthrough(full_cmd, cwd=repo_root)
        sys.exit(code)

    # 3. Check if command is a Lifecycle Hook (build / test / dev / debug)
    if cmd in LIFECYCLE_ACTIONS:
        output_mode, extra_args = resolve_output_mode(cmd, extra_args)
        script_file = get_lifecycle_script_path(repo_root, cmd)
        if not os.path.exists(script_file):
            # A nested context without a hook runs the enclosing context's hook instead of
            # synthesizing one that may test nothing [bug--lifecycle-test-false-pass] REQ-3.
            enclosing = lifecycle.enclosing_hook(repo_root, cmd)
            if enclosing:
                repo_root, script_file = enclosing
                print(f"-> No .along/scripts/{cmd} hook here; using the enclosing context's: {script_file}")

        if os.path.exists(script_file):
            if gates.is_unconfigured_hook(script_file):
                print(f"[Warning] {script_file} is unconfigured: nothing is verified. "
                      "Please customize it for this repository.", file=sys.stderr)

            print(f"-> Executing .along/scripts/{os.path.basename(script_file)}...")
            full_cmd = lifecycle.build_interpreter_cmd(script_file, extra_args)
            sys.exit(run_lifecycle_command(cmd, full_cmd, repo_root, output_mode))

        # Auto-Detection and Non-Destructive Synthesis
        detected_cmd, verified = detect_lifecycle_action(repo_root, cmd)

        # A hook is Along state: written only into an installation. Elsewhere the detected
        # command runs once and nothing is created [bug--along-install-marker-ambiguous].
        if not repo.is_installed(repo_root):
            if not (detected_cmd and verified):
                print(f"[Error] No {cmd} command detected in {repo_root}, and Along is not installed "
                      "there (no hook is written outside an installation).", file=sys.stderr)
                sys.exit(2)
            print(f"-> Along is not installed in {repo_root}: running {detected_cmd} without writing a hook.")
            sys.exit(run_lifecycle_command(cmd, shlex.split(detected_cmd) + extra_args,
                                           repo_root, output_mode))

        if detected_cmd and verified:
            status_tag = "verified"
            py_content = lifecycle.render_lifecycle_script(cmd, base_cmd=shlex.split(detected_cmd), status_tag=status_tag)
            synthesize_lifecycle_script(script_file, py_content)
            print(f"-> Running: {detected_cmd}")
            sys.exit(run_lifecycle_command(cmd, shlex.split(detected_cmd) + extra_args,
                                           repo_root, output_mode))
        else:
            status_tag = "unconfigured"
            py_content = lifecycle.render_lifecycle_script(cmd, base_cmd=None, status_tag=status_tag)
            synthesize_lifecycle_script(script_file, py_content)
            print(f"[Warning] Created unconfigured template: {script_file} "
                  "(nothing is verified until it is configured)", file=sys.stderr)
            print(f"Please customize .along/scripts/{cmd}.py for your repository build/test configuration.")
            sys.exit(0)

    print(f"[Error] Unknown command: '{cmd}'. Run 'python scripts/along_exec.py --help' for available commands.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()


