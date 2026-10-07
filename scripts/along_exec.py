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
  decision create <slug> --title "Title" --context "Why" --decision "What" --consequences "Tradeoffs"
  decision sync   Recompile .along/CONSTRAINTS.md projection from active ADRs
  scratch init   <slug> [--title "Title"] [--steps N] [--restart] [--mode direct]
  scratch state  <slug> [--json]
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
""")

RECENT_DONE_LIMIT = entities.RECENT_DONE_LIMIT
compile_issues_board = entities.compile_issues_board


def _issue_create(repo_root: str, args: List[str], issues_dir: str, today: str):
    if len(args) < 3:
        print("[Error] Usage: along_exec.py issue create <type> <slug> --title \"Title\" [--priority high|medium|low] [--tags \"tag1,tag2\"] [--agent <name>] [--milestone <name>]", file=sys.stderr)
        sys.exit(1)
    itype = args[1].lower()
    if itype not in entities.ISSUE_TYPES:
        print(f"[Error] Invalid issue type '{itype}'. Allowed types: {', '.join(entities.ISSUE_TYPES)}", file=sys.stderr)
        sys.exit(1)

    islug = _require_entity_name(args[2].lower(), "along issue create <type> <slug> --title \"Title\"")
    if not entities.is_valid_slug(islug):
        print(f"[Error] Invalid issue slug '{islug}'. Slug must be 2-5 lowercase kebab-case words (e.g. my-feature-name).", file=sys.stderr)
        sys.exit(1)

    existing_issue = entities.find_issue_by_slug(repo_root, islug)
    if existing_issue:
        rel_existing = os.path.relpath(existing_issue["file_path"], repo_root)
        print(f"[Error] An issue with slug '{islug}' already exists: {rel_existing}", file=sys.stderr)
        sys.exit(1)

    title = islug.replace("-", " ").capitalize()
    priority = "medium"
    tags = []
    explicit_agent = None
    explicit_milestone = None
    no_milestone = False

    i = 3
    while i < len(args):
        if args[i] in ("--title", "-t") and i + 1 < len(args):
            title = args[i + 1]
            i += 2
        elif args[i] in ("--priority", "-p") and i + 1 < len(args):
            priority = args[i + 1].lower()
            i += 2
        elif args[i] in ("--tags",) and i + 1 < len(args):
            tags = [t.strip() for t in args[i + 1].split(",") if t.strip()]
            i += 2
        elif args[i] in ("--agent", "-a") and i + 1 < len(args):
            explicit_agent = args[i + 1]
            i += 2
        elif args[i] in ("--milestone", "-m") and i + 1 < len(args):
            explicit_milestone = args[i + 1]
            i += 2
        elif args[i] in ("--no-milestone",):
            no_milestone = True
            i += 1
        else:
            i += 1

    if priority not in entities.PRIORITIES:
        print(f"[Error] Invalid priority '{priority}'. Allowed priorities: {', '.join(entities.PRIORITIES)}", file=sys.stderr)
        sys.exit(1)

    agent = entities.detect_agent(explicit_agent)

    milestone = None
    if no_milestone:
        milestone = None
    elif explicit_milestone:
        if explicit_milestone.lower() in ("none", "null", "~", ""):
            milestone = None
        else:
            clean_m = explicit_milestone[:-3] if explicit_milestone.endswith(".md") else explicit_milestone
            m_path = os.path.join(repo_root, ".along", "MILESTONES", f"{clean_m}.md")
            if not os.path.exists(m_path):
                print(f"[Error] Milestone '{explicit_milestone}' does not exist in .along/MILESTONES/.", file=sys.stderr)
                sys.exit(1)
            milestone = clean_m
    else:
        milestone = entities.resolve_in_progress_milestone(repo_root)

    inferred = entities.infer_issue_type(f"{islug} {title}")
    if itype == "feat" and inferred in ("bug", "debt"):
        print(f"-> [Notice] Title/slug matches {inferred} keywords. Consider using type '{inferred}' instead of 'feat'.")

    milestone_line = f"milestone: {milestone}\n" if milestone else ""
    target_file = os.path.join(issues_dir, f"{itype}--{islug}.md")
    tags_str = f"[{', '.join(tags)}]" if tags else "[]"
    content = f"""---
protocol: along
protocol_version: "{CURRENT_PROTOCOL_VERSION}"
slug: {islug}
type: {itype}
status: open
priority: {priority}
created: {today}
updated: {today}
agent: {agent}
tags: {tags_str}
{milestone_line}blocked_by: []
related: []
---

# {title}

Describe the feature, requirements, and background context here.

## Acceptance Criteria
- [ ] Task requirement 1
- [ ] Automated tests passing
"""
    textio.write_text(target_file, content, newline="\n", atomic=True)
    print(f"-> Created issue: {target_file}")

    # Keep the milestone's target_issues in sync with the new assignment.
    if milestone:
        try:
            entities.sync_milestones(repo_root, milestone)
            print(f"-> Synchronized milestone {milestone}.")
        except ValueError:
            pass

    # Update ISSUES.md
    issues_board = os.path.join(repo_root, ".along", "ISSUES.md")
    if os.path.exists(issues_board):
        entities.sync_issues_board(repo_root, recent_done_limit=RECENT_DONE_LIMIT)
        print("-> Updated .along/ISSUES.md")
    sys.exit(0)


def _issue_done(repo_root: str, args: List[str], issues_dir: str, done_dir: str, today: str):
    if len(args) < 2:
        print("[Error] Usage: along_exec.py issue done <slug> [--status done|superseded|cancelled|duplicate] [--superseded-by <key>] [--duplicate-of <key>]", file=sys.stderr)
        sys.exit(1)
    islug = _require_entity_name(args[1].lower(), "along issue done|cancel <slug> [--status ...]")
    target_status = "done"
    superseded_by = None
    duplicate_of = None

    i = 2
    while i < len(args):
        if args[i] in ("--status", "-s") and i + 1 < len(args):
            target_status = args[i + 1].lower()
            i += 2
        elif args[i] in ("--superseded-by",) and i + 1 < len(args):
            superseded_by = args[i + 1].strip()
            i += 2
        elif args[i] in ("--duplicate-of",) and i + 1 < len(args):
            duplicate_of = args[i + 1].strip()
            i += 2
        else:
            i += 1

    if target_status not in entities.CLOSED_ISSUE_STATUSES:
        print(f"[Error] Invalid closing status '{target_status}'. Allowed statuses: {', '.join(entities.CLOSED_ISSUE_STATUSES)}", file=sys.stderr)
        sys.exit(1)

    # Locate issue file
    found_file = None
    for f in os.listdir(issues_dir):
        if f.endswith(f"--{islug}.md") and os.path.isfile(os.path.join(issues_dir, f)):
            found_file = os.path.join(issues_dir, f)
            break

    if not found_file:
        print(f"[Error] Issue '{islug}' not found in {issues_dir}", file=sys.stderr)
        sys.exit(1)

    filename = os.path.basename(found_file)
    dest_file = os.path.join(done_dir, filename)

    content = textio.read_text(found_file)

    if not has_frontmatter(content):
        print(
            f"[Error] {filename} has no parseable YAML front-matter. "
            "Refusing to close it silently: fix the entity header, then retry.",
            file=sys.stderr,
        )
        sys.exit(1)

    if content.startswith("\ufeff"):
        content = content.lstrip("\ufeff")
        print(
            f"-> [Notice] Normalized a UTF-8 BOM in {filename}. "
            "The protocol requires BOM-free UTF-8. To avoid producing one: PowerShell 7+ "
            "has -Encoding utf8NoBOM; Windows PowerShell 5.1 has no such value, so use "
            "[IO.File]::WriteAllText(path, text, (New-Object System.Text.UTF8Encoding($false)))."
        )

    updates = {"status": target_status, "updated": today, "completed": today}
    if superseded_by:
        updates["superseded_by"] = superseded_by
    if duplicate_of:
        updates["duplicate_of"] = duplicate_of

    content = update_frontmatter_fields(
        content,
        updates,
        place_after={"completed": "status"},
    )

    # Adjust sibling issue links in the markdown body:
    # [Text](feat--foo.md) or [Text](./feat--foo.md) becomes [Text](../feat--foo.md)
    block = frontmatter.split(content)
    if block:
        sibling_link_re = re.compile(
            r'(\[[^\]]+\]\()(?:\./)?(?<!\.\./)((?:feat|bug|debt|task|docs)--[a-z0-9-]+\.md\b)'
        )
        body_lines = block.body.splitlines(keepends=True)
        adjusted_body_lines = []
        in_fence = False
        for line in body_lines:
            stripped = line.strip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_fence = not in_fence
                adjusted_body_lines.append(line)
                continue
            if in_fence:
                adjusted_body_lines.append(line)
                continue
            adjusted_body_lines.append(sibling_link_re.sub(r'\1../\2', line))
        content = block.open_delim + block.raw + block.close_delim + "".join(adjusted_body_lines)

    # [bug--session-records-not-captured] REQ-4: the issue's blackboard (or, without one, the
    # completion itself) goes into today's session log in the same transaction; the blackboard
    # is purged once that committed.
    _itype, bare_slug = entities.parse_key(filename[:-3])
    has_blackboard = session.load_state(repo_root, bare_slug) is not None
    tx = transaction.FileTransaction(repo_root, label=f"issue-done-{bare_slug}")
    try:
        tx.protect(found_file)
        tx.protect(dest_file)
        textio.write_text(dest_file, content, newline="\n", atomic=True)
        os.remove(found_file)
        print(f"-> Moved issue to done: {dest_file}")

        if has_blackboard:
            session.append_trace(repo_root, bare_slug, "archived by issue done")
        if has_blackboard or target_status == "done":
            log_path = lifecycle.write_session_record(
                repo_root, tx, bare_slug, today=today, completed=(target_status == "done"))
            print(f"-> Recorded in session log: {repo.safe_relpath(log_path, repo_root)}")

        # Update ISSUES.md projection with sliding window
        issues_board = os.path.join(repo_root, ".along", "ISSUES.md")
        if os.path.exists(issues_board):
            tx.protect(issues_board)
            entities.sync_issues_board(repo_root, recent_done_limit=RECENT_DONE_LIMIT)
            print("-> Updated .along/ISSUES.md")
        tx.commit()
    except (OSError, ValueError, frontmatter.FrontmatterError) as exc:
        print(f"[Error] issue done failed: {exc}", file=sys.stderr)
        tx.rollback()
        sys.exit(1)
    if has_blackboard and lifecycle.purge_archived(repo_root, bare_slug, complete=True):
        print(f"-> Purged session blackboard: .along/.session/{bare_slug}")
    sys.exit(0)


def _issue_reopen(repo_root: str, args: List[str], issues_dir: str, done_dir: str, today: str):
    """`along issue reopen <slug>`: back from done/ to ISSUES/, `status: open`.

    The closing fields (`completed`, `superseded_by`, `duplicate_of`) are removed, sibling
    links rewritten for done/ are restored, and ISSUES.md is recompiled, in one transaction.
    Session logs that list the issue as completed stay as they are (history).
    See [feat--parallel-session-closeout] REQ-7.
    """
    if len(args) < 2 or args[1].startswith("-"):
        print("[Error] Usage: along issue reopen <slug>", file=sys.stderr)
        sys.exit(1)
    _itype, islug = entities.parse_key(args[1].lower())
    if any(f.endswith(f"--{islug}.md") for f in os.listdir(issues_dir) if os.path.isfile(os.path.join(issues_dir, f))):
        print(f"[Error] Issue '{islug}' is already open in {issues_dir}.", file=sys.stderr)
        sys.exit(1)
    found = next((os.path.join(done_dir, f) for f in sorted(os.listdir(done_dir))
                  if f.endswith(f"--{islug}.md")), None) if os.path.isdir(done_dir) else None
    if not found:
        print(f"[Error] Issue '{islug}' not found in {done_dir}", file=sys.stderr)
        sys.exit(1)
    dest = os.path.join(issues_dir, os.path.basename(found))
    content = textio.read_text(found)
    if not has_frontmatter(content):
        print(f"[Error] {os.path.basename(found)} has no parseable YAML front-matter.", file=sys.stderr)
        sys.exit(1)
    content = frontmatter.update(content, {"status": "open", "updated": today},
                                 remove=("completed", "superseded_by", "duplicate_of"))
    block = frontmatter.split(content)
    if block:
        back = re.compile(r'(\[[^\]]+\]\()\.\./((?:feat|bug|debt|task|docs)--[a-z0-9-]+\.md\b)')
        body, in_fence = [], False
        for line in block.body.splitlines(keepends=True):
            if line.strip().startswith(("```", "~~~")):
                in_fence = not in_fence
            body.append(line if in_fence else back.sub(r"\1\2", line))
        content = block.bom + block.open_delim + block.raw + block.close_delim + "".join(body)
    tx = transaction.FileTransaction(repo_root, label=f"issue-reopen-{islug}")
    try:
        tx.protect(found)
        tx.protect(dest)
        textio.write_text(dest, content, newline="\n", atomic=True)
        os.remove(found)
        board = os.path.join(repo.state_dir(repo_root), "ISSUES.md")
        if os.path.exists(board):
            tx.protect(board)
            entities.sync_issues_board(repo_root, recent_done_limit=RECENT_DONE_LIMIT)
        tx.commit()
    except (OSError, ValueError, frontmatter.FrontmatterError) as exc:
        print(f"[Error] issue reopen failed: {exc}", file=sys.stderr)
        tx.rollback()
        sys.exit(1)
    print(f"-> Reopened {repo.safe_relpath(dest, repo_root)} (status: open). Resume with 'along start {islug}'.")
    sys.exit(0)


def _issue_sync(repo_root: str):
    entities.sync_issues_board(repo_root, recent_done_limit=RECENT_DONE_LIMIT)
    print(f"-> Recompiled .along/ISSUES.md projection (capped to {RECENT_DONE_LIMIT} recent completed issues).")
    if not gates.entity_integrity_gate(repo_root, "Issue Sync"):
        sys.exit(1)
    sys.exit(0)


def _issue_rename(repo_root: str, args: List[str]):
    if len(args) < 3:
        print("[Error] Usage: along issue rename <old-key> <new-key>", file=sys.stderr)
        sys.exit(1)
    for name in args[1:3]:
        _require_entity_name(name, "along issue rename <old-key> <new-key>")
    try:
        result = entities.rename_issue(repo_root, args[1].lower(), args[2].lower())
    except ValueError as exc:
        print(f"[Error] {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"-> Renamed {result['old_key']} -> {result['new_key']}: "
          f"{repo.normalize_posix(repo.safe_relpath(result['file_path'], repo_root))}")
    _report_rewritten(repo_root, result["rewritten"])
    sys.exit(0)


def _issue_supersede(repo_root: str, args: List[str]):
    by = None
    for i, arg in enumerate(args):
        if arg == "--by" and i + 1 < len(args):
            by = args[i + 1].lower()
    if len(args) < 2 or args[1].startswith("-") or not by:
        print("[Error] Usage: along issue supersede <old-key> --by <new-key>", file=sys.stderr)
        sys.exit(1)
    try:
        result = entities.supersede_issue(repo_root, args[1].lower(), by)
    except ValueError as exc:
        print(f"[Error] {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"-> Superseded {result['old_key']} by {result['new_key']}: "
          f"{repo.normalize_posix(repo.safe_relpath(result['file_path'], repo_root))}")
    _report_rewritten(repo_root, result["rewritten"])
    sys.exit(0)


def _issue_delete(repo_root: str, args: List[str]):
    """`along issue delete <slug>`: remove an issue created by mistake [bug--cli-entity-sync-defects]."""
    if len(args) < 2:
        print("[Error] Usage: along issue delete <slug>", file=sys.stderr)
        sys.exit(1)
    slug = _require_entity_name(args[1].lower(), "along issue delete <slug>")
    try:
        result = entities.delete_issue(repo_root, slug)
    except ValueError as exc:
        print(f"[Error] {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"-> Deleted {result['key']}: {repo.normalize_posix(repo.safe_relpath(result['file_path'], repo_root))}")
    _report_rewritten(repo_root, result["rewritten"])
    sys.exit(0)


def _report_rewritten(repo_root: str, paths: List[str]):
    if not paths:
        print("-> No inbound references to rewrite.")
        return
    print(f"-> Rewrote inbound references in {len(paths)} file(s):")
    for path in paths:
        print(f"   - {repo.normalize_posix(repo.safe_relpath(path, repo_root))}")


def _issue_list(issues_dir: str):
    print(f"-> Active issues in {issues_dir}:")
    count = 0
    for f in os.listdir(issues_dir):
        if f.endswith(".md") and os.path.isfile(os.path.join(issues_dir, f)):
            print(f"   - {f}")
            count += 1
    print(f"Total active issues: {count}")
    sys.exit(0)


def _issue_update(repo_root: str, args: List[str], today: str):
    if len(args) < 2:
        print("[Error] Usage: along issue update <slug> [--milestone <name>] [--priority <high|medium|low>] [--status <status>] [--tags <t1,t2>] [--title <title>]", file=sys.stderr)
        sys.exit(1)
    raw_slug = args[1].lower()
    issue = entities.find_issue_by_slug(repo_root, raw_slug)
    if not issue:
        print(f"[Error] Issue '{raw_slug}' not found in .along/ISSUES/.", file=sys.stderr)
        sys.exit(1)

    updates: Dict[str, Any] = {"updated": today}
    milestone_updated = False
    target_milestone_slug = None

    i = 2
    while i < len(args):
        flag = args[i]
        val = args[i + 1] if i + 1 < len(args) else None
        if flag in ("--milestone", "-m") and val:
            if val in ("~", "none", "null", ""):
                updates["milestone"] = None
            else:
                m_resolved = entities.resolve_milestone_by_query(repo_root, val)
                if not m_resolved:
                    print(f"[Error] Milestone '{val}' not found or ambiguous in .along/MILESTONES/.", file=sys.stderr)
                    sys.exit(1)
                updates["milestone"] = m_resolved["slug"]
                target_milestone_slug = m_resolved["slug"]
            milestone_updated = True
            i += 2
        elif flag in ("--priority", "-p") and val:
            pval = val.lower()
            if pval not in entities.PRIORITIES:
                print(f"[Error] Invalid priority '{pval}'. Allowed: {', '.join(entities.PRIORITIES)}", file=sys.stderr)
                sys.exit(1)
            updates["priority"] = pval
            i += 2
        elif flag in ("--status", "-s") and val:
            sval = val.lower()
            if sval not in entities.ISSUE_STATUSES:
                print(f"[Error] Invalid status '{sval}'. Allowed: {', '.join(entities.ISSUE_STATUSES)}", file=sys.stderr)
                sys.exit(1)
            updates["status"] = sval
            i += 2
        elif flag in ("--tags",) and val:
            updates["tags"] = [t.strip() for t in val.split(",") if t.strip()]
            i += 2
        elif flag in ("--title", "-t") and val:
            updates["title"] = val
            i += 2
        else:
            i += 1

    fpath, new_fm = entities.update_issue_frontmatter(repo_root, issue["slug"], updates)
    rel_path = repo.normalize_posix(repo.safe_relpath(fpath, repo_root))
    print(f"-> Updated issue {issue['slug']}: {rel_path}")
    for k, v in updates.items():
        if k != "updated":
            print(f"   {k}: {v}")

    if milestone_updated:
        old_m = issue["frontmatter"].get("milestone")
        if old_m and old_m != target_milestone_slug:
            try:
                entities.sync_milestones(repo_root, old_m)
            except ValueError:
                pass
        if target_milestone_slug:
            try:
                entities.sync_milestones(repo_root, target_milestone_slug)
            except ValueError:
                pass
        print("-> Synchronized affected milestone(s).")

    entities.sync_issues_board(repo_root, recent_done_limit=RECENT_DONE_LIMIT)
    sys.exit(0)


def _issue_show(repo_root: str, args: List[str]):
    if len(args) < 2:
        print("[Error] Usage: along issue show <slug> [--json]", file=sys.stderr)
        sys.exit(1)
    raw_slug = args[1].lower()
    summary = entities.get_issue_summary(repo_root, raw_slug)
    if not summary:
        print(f"[Error] Issue '{raw_slug}' not found in .along/ISSUES/.", file=sys.stderr)
        sys.exit(1)

    if "--json" in args:
        import json
        print(json.dumps(summary, indent=2))
    else:
        print(f"=== Issue: {summary['slug']} ({summary['type']}) ===")
        print(f"Title:     {summary['title']}")
        print(f"Status:    {summary['status']}")
        print(f"Priority:  {summary['priority']}")
        print(f"Milestone: {summary.get('milestone') or 'none'}")
        print(f"Agent:     {summary.get('agent') or 'unknown'}")
        print(f"Tags:      {', '.join(summary.get('tags') or [])}")
        print(f"Path:      {summary['file_path']}")
        if summary.get("body"):
            print("\n--- Summary / Body ---")
            lines = summary["body"].splitlines()
            preview = lines[:25]
            print("\n".join(preview))
            if len(lines) > 25:
                print(f"... ({len(lines) - 25} more lines)")
    sys.exit(0)


def handle_issue_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along_exec.py issue [create|update|done|cancel|delete|reopen|sync|list|show|rename|supersede] [args...]")
        print("  create <type> <slug> --title \"Title\" [--priority high|medium|low] [--tags \"t1,t2\"] [--agent <name>] [--milestone <name>|--no-milestone]")
        print("  update <slug> [--milestone <name>] [--priority <high|medium|low>] [--status <status>] [--tags <t1,t2>] [--title <title>]")
        print("  done   <slug> [--status done|superseded|cancelled|duplicate] [--superseded-by <key>] [--duplicate-of <key>]")
        print("  cancel <slug>             Close as cancelled (moved to done/)")
        print("  delete <slug>             Remove an issue created by mistake (refused once sessions, commits")
        print("                            or parent/superseded_by/duplicate_of references name it)")
        print("  reopen <slug>")
        print("  sync                      Recompile the .along/ISSUES.md board")
        print("  list")
        print("  show   <slug> [--json]")
        print("  rename <old-key> <new-key>")
        print("  supersede <old-key> --by <new-key>")
        sys.exit(0)

    subcmd = args[0].lower()
    issues_dir = os.path.join(repo_root, ".along", "ISSUES")
    done_dir = os.path.join(issues_dir, "done")
    os.makedirs(issues_dir, exist_ok=True)
    os.makedirs(done_dir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")

    dispatch = {
        "create": lambda: _issue_create(repo_root, args, issues_dir, today),
        "done": lambda: _issue_done(repo_root, args, issues_dir, done_dir, today),
        "close": lambda: _issue_done(repo_root, args, issues_dir, done_dir, today),
        "cancel": lambda: _issue_done(repo_root, args[:2] + ["--status", "cancelled"] + args[2:],
                                      issues_dir, done_dir, today),
        "delete": lambda: _issue_delete(repo_root, args),
        "reopen": lambda: _issue_reopen(repo_root, args, issues_dir, done_dir, today),
        "sync": lambda: _issue_sync(repo_root),
        "list": lambda: _issue_list(issues_dir),
        "update": lambda: _issue_update(repo_root, args, today),
        "edit": lambda: _issue_update(repo_root, args, today),
        "show": lambda: _issue_show(repo_root, args),
        "get": lambda: _issue_show(repo_root, args),
        "rename": lambda: _issue_rename(repo_root, args),
        "supersede": lambda: _issue_supersede(repo_root, args),
    }

    handler = dispatch.get(subcmd)
    if not handler:
        print(f"[Error] Unknown issue subcommand '{subcmd}'. Run 'along issue --help'.", file=sys.stderr)
        sys.exit(1)
    handler()


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
        target = args[1] if len(args) > 1 and not args[1].startswith("-") else None
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
        as_json = "--json" in args
        filter_status = None
        for i in range(1, len(args)):
            if args[i] in ("--status", "-s") and i + 1 < len(args):
                filter_status = args[i + 1].lower()

        milestones = entities.scan_milestones(repo_root)
        if filter_status:
            milestones = [m for m in milestones if m["status"] == filter_status]

        if as_json:
            import json
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
        m = entities.resolve_milestone_by_query(repo_root, query)
        if not m:
            print(f"[Error] Milestone '{query}' not found in .along/MILESTONES/.", file=sys.stderr)
            sys.exit(1)

        fm = m["frontmatter"]
        target_keys = fm.get("target_issues", [])
        all_issues = entities.scan_issues(repo_root, include_done=True)
        assigned = []
        for iss in all_issues:
            key = entities.canonical_key(iss["type"], iss["slug"])
            if key in target_keys or iss["slug"] in target_keys or str(iss["frontmatter"].get("milestone")) in (m["slug"], os.path.basename(m["file_path"])[:-3]):
                assigned.append(iss)

        if "--json" in args:
            import json
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
        mslug = _require_entity_name(args[1].lower().strip(),
                                     "along milestone create <slug> --title \"Title\" [--due YYYY-MM-DD]")
        title = mslug.replace("-", " ").capitalize()
        due_date = None

        i = 2
        while i < len(args):
            if args[i] in ("--title", "-t") and i + 1 < len(args):
                title = args[i + 1]
                i += 2
            elif args[i] in ("--due", "--due-date", "-d") and i + 1 < len(args):
                due_date = args[i + 1]
                i += 2
            else:
                i += 1

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


def handle_start_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along start <slug> [--approved] [--worktree] [--allow-root <path>]... [--write-scope <path>]...")
        print("  Atomically marks issue in-progress, initializes session blackboard, binds this")
        print("  agent session to the issue, and optionally creates an isolated worktree.")
        print("  The plan stays unapproved until the user approves it; --approved is for scripted runs.")
        print("  --allow-root / --write-scope add to the issue's allowed_roots / write_scope")
        print("  frontmatter, read by [gate: workspace-containment].")
        sys.exit(0)

    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")

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

    slug = _require_entity_name(args[0].lower(), "along start <slug> [--approved] [--worktree]")
    issue = entities.find_issue_by_slug(repo_root, slug)
    if not issue:
        print(f"[Error] Issue '{slug}' not found in .along/ISSUES/.", file=sys.stderr)
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
    st = session.init_session(repo_root, issue["slug"], title=title)
    sdir = session.get_session_dir(repo_root, issue["slug"])
    key = session.current_session_key()
    # Starting an issue is not a plan approval: approval comes from the user (ExitPlanMode,
    # or 'along plan approve' after an explicit yes); --approved is for scripted runs.
    # See [feat--plan-approval-exit-plan-mode] and [bug--session-state-cross-session-leak].
    binding = session.bind_session(repo_root, issue["slug"], key=key,
                                   approved=True if "--approved" in args else None)
    approved = "--approved" in args or session.is_plan_approved(repo_root, slug=issue["slug"], key=key)
    st = session.set_session_phase(repo_root, "execution" if approved else "planning",
                                   slug=issue["slug"], plan_approved=approved)
    print(f"-> Initialized session blackboard: {sdir} "
          f"(phase: {st.get('phase')}, plan_approved: {str(bool(st.get('plan_approved'))).lower()})")
    if binding:
        print(f"-> Bound agent session {binding['key']} to '{issue['slug']}'.")
    else:
        print("-> No agent session id in the environment; gates fall back to the single in-progress issue.")
    if not approved:
        print("-> Present the plan to the user. Edits unlock after approval "
              "(Claude Code: ExitPlanMode; otherwise 'along plan approve' after the user's explicit yes).")

    if "--worktree" in args:
        from alongkit import worktree
        wt_path = worktree.create_worktree(repo_root, issue["slug"])
        print(f"-> Created isolated worktree: {wt_path}")
        print(f"-> Ready to work in worktree. Run tests and edits there.")
    else:
        print(f"-> Ready to work on issue '{issue['slug']}'. Active issue bound.")

    sys.exit(0)


def _git_head_facts(repo_root: str) -> Tuple[Optional[str], Optional[str]]:
    """(branch, short commit) of the repository or worktree, or None where unknown."""
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
    """What the session log may truthfully say about tests.

    The CLI does not run tests, so it never claims they passed. When the runtime hooks
    recorded a test run after the last edit, the log says so and leaves the result to the
    author. See [bug--session-create-unsafe-yaml].

    A green `along test` run recorded for the current working tree counts too, in this
    context or an enclosing one (a run from the root covers a subproject's log).
    [bug--cli-entity-sync-defects] REQ-2
    """
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
    """One line per named issue (key, title, status) instead of a placeholder."""
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
    """Session log document with front-matter emitted by ruamel, never by string formatting.

    Issues are filed by their actual status: closed ones under `issues_completed`, the rest
    under `issues_advanced`, as canonical keys. [bug--cli-entity-sync-defects] REQ-2
    """
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


def handle_plan_command(repo_root: str, args: List[str]):
    """`along plan approve [<slug>]` / `along plan status` for this agent session.

    See [feat--plan-approval-exit-plan-mode].
    """
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
            session.append_trace(repo_root, slug, "plan approved (along plan approve)")
            session.append_event(repo_root, slug, key, "approve")
            print(f"-> Plan approved for '{slug}' (session: {key or 'none'}).")
        elif key:
            session.record_plan_approval(repo_root, key)
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
    if subcmd == "bindings":
        rows = session.list_bindings(repo_root)
        if not rows:
            print("No agent-session bindings.")
        for b in rows:
            print(f"{b.get('key')}: {b.get('slug') or '-'} (approved: "
                  f"{str(bool(b.get('plan_approved'))).lower()}, updated: {b.get('updated')})")
        sys.exit(0)
    if subcmd == "gc":
        removed = session.gc_bindings(repo_root, dry_run="--dry-run" in args)
        verb = "Would remove" if "--dry-run" in args else "Removed"
        print(f"-> {verb} {len(removed)} stale binding(s){': ' + ', '.join(removed) if removed else ''}.")
        sys.exit(0)
    if subcmd == "list":
        # [feat--parallel-session-closeout] REQ-4: readiness of every open piece of work.
        from alongkit import closeout
        status = closeout.closeout_status(repo_root)
        if "--json" in args:
            import json
            print(json.dumps(status, indent=2))
        else:
            print(closeout.format_closeout_status(status))
        sys.exit(0)
    if subcmd == "close":
        # [feat--parallel-session-closeout] REQ-5: one step for every finished piece of work.
        from alongkit import closeout
        names = [a for a in args[1:] if not a.startswith("-")]
        if not names and "--ready" not in args and not closeout.load_run(repo_root):
            print("[Error] Usage: along session close <slug>... | --ready [--dry-run] [--push]", file=sys.stderr)
            sys.exit(2)
        sys.exit(closeout.run_closeout(repo_root, keys=names, ready="--ready" in args,
                                       dry_run="--dry-run" in args, push="--push" in args))
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    year = datetime.now().strftime("%Y")
    sessions_dir = os.path.join(repo_root, ".along", "SESSIONS", year)

    if subcmd == "create":
        if len(args) < 2:
            print("[Error] Usage: along_exec.py session create <slug> --summary \"Summary\"", file=sys.stderr)
            sys.exit(1)
        slug = _require_entity_name(args[1].lower(), "along session create <slug> --summary \"Summary\"")
        # Only after the name is valid: a rejected name leaves no directory behind.
        os.makedirs(sessions_dir, exist_ok=True)
        summary = "Work session"
        issues = []
        decisions = []
        explicit_agent = None
        explicit_milestone = None
        explicit_commit = None

        i = 2
        while i < len(args):
            if args[i] in ("--summary", "-s") and i + 1 < len(args):
                summary = args[i + 1]
                i += 2
            elif args[i] == "--commit" and i + 1 < len(args):
                explicit_commit = args[i + 1]
                i += 2
            elif args[i] in ("--issues", "-i") and i + 1 < len(args):
                issues = [iss.strip() for iss in args[i + 1].split(",") if iss.strip()]
                i += 2
            elif args[i] in ("--decisions", "-d") and i + 1 < len(args):
                decisions = [d.strip() for d in args[i + 1].split(",") if d.strip()]
                i += 2
            elif args[i] in ("--agent", "-a") and i + 1 < len(args):
                explicit_agent = args[i + 1]
                i += 2
            elif args[i] in ("--milestone", "-m") and i + 1 < len(args):
                explicit_milestone = args[i + 1]
                i += 2
            else:
                i += 1

        agent = entities.detect_agent(explicit_agent)

        milestone = None
        if explicit_milestone:
            clean_m = explicit_milestone[:-3] if explicit_milestone.endswith(".md") else explicit_milestone
            m_path = os.path.join(repo_root, ".along", "MILESTONES", f"{clean_m}.md")
            if not os.path.exists(m_path):
                print(f"[Error] Milestone '{explicit_milestone}' does not exist in .along/MILESTONES/.", file=sys.stderr)
                sys.exit(1)
            milestone = clean_m
        else:
            milestone = entities.resolve_in_progress_milestone(repo_root)

        target_file = os.path.join(sessions_dir, f"{today}--{slug}.md")
        content = _render_session_log(
            repo_root, today=today, slug=slug, agent=agent, summary=summary,
            milestone=milestone, issues=issues, decisions=decisions, commit=explicit_commit,
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
        if len(args) < 2:
            print("[Error] Usage: along session wrap <slug> [--status done|superseded|cancelled|duplicate] [--summary \"Summary\"] [--dry-run] [-n]", file=sys.stderr)
            sys.exit(1)
        islug = _require_entity_name(args[1], "along session wrap <slug> [--status ...] [--summary \"Summary\"]")
        status = "done"
        summary = None
        dry_run = False
        no_verify = False
        explicit_agent = None

        i = 2
        while i < len(args):
            if args[i] in ("--status", "-s") and i + 1 < len(args):
                status = args[i + 1].lower()
                i += 2
            elif args[i] in ("--summary", "-m") and i + 1 < len(args):
                summary = args[i + 1]
                i += 2
            elif args[i] == "--dry-run":
                dry_run = True
                i += 1
            elif args[i] in ("-n", "--no-verify"):
                no_verify = True
                i += 1
            elif args[i] in ("--agent", "-a") and i + 1 < len(args):
                explicit_agent = args[i + 1]
                i += 2
            else:
                i += 1

        # Same contract as `along wrap` [feat--wrap-session-log-from-blackboard].
        raw_decisions = _flag_value(args, "--decisions") or _flag_value(args, "-d")
        if (raw_decisions is None) == ("--no-decisions" not in args):
            print("[Error] Answer whether architectural decisions were made: "
                  "--decisions ADR-a,ADR-b or --no-decisions (exactly one).", file=sys.stderr)
            sys.exit(2)
        decisions = [] if raw_decisions is None else [d.strip() for d in raw_decisions.split(",") if d.strip()]

        code = lifecycle.execute_wrap(
            repo_root=repo_root,
            slug=islug,
            status=status,
            summary=summary,
            dry_run=dry_run,
            no_verify=no_verify,
            agent=explicit_agent,
            decisions=decisions,
            force_reason=_flag_value(args, "--force-reason"),
        )
        sys.exit(code)


def handle_decision_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along_exec.py decision [create|sync] [args...]")
        print("  create <slug> --title \"Title\" --context \"Context\" --decision \"Decision\" --consequences \"Tradeoffs\"")
        print("  sync   Recompile .along/DECISIONS.md and .along/CONSTRAINTS.md projections from ADRs")
        sys.exit(0)

    subcmd = args[0].lower()
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")

    from alongkit import entities

    if subcmd == "sync":
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
            print("[Error] Usage: along_exec.py decision create <slug> --title \"Title\" --context \"Why\" --decision \"What\" --consequences \"Consequences\"", file=sys.stderr)
            sys.exit(1)
        first_arg = args[1].lstrip("#")
        slug = _require_entity_name(first_arg.lower(), "along decision create <slug> --title \"Title\"")
        title = slug.replace("-", " ").capitalize()
        context = ""
        decision = ""
        consequences = ""

        i = 2
        while i < len(args):
            if args[i] in ("--title", "-t") and i + 1 < len(args):
                title = args[i + 1]
                i += 2
            elif args[i] == "--context" and i + 1 < len(args):
                context = args[i + 1]
                i += 2
            elif args[i] == "--decision" and i + 1 < len(args):
                decision = args[i + 1]
                i += 2
            elif args[i] == "--consequences" and i + 1 < len(args):
                consequences = args[i + 1]
                i += 2
            else:
                if i == 2 and not args[i].startswith("-"):
                    title = args[i]
                    i += 1
                else:
                    i += 1

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
               and not d.startswith(".") and d != session.BINDINGS_DIRNAME]
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


def handle_doctor_command(repo_root: str, args: List[str]):
    if args and args[0] in ("-h", "--help", "help"):
        print("Usage: along doctor [entities|--entities] [--fix]")
        print("  (no args)            Report protocol, hooks, runtime, bindings and blackboard health")
        print("  entities [--fix]     Validate entity schemas and references; --fix drops dangling milestone fields")
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


def handle_scratch_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along scratch [init|state|update|approve|phase|purge] <slug> [options]")
        print("  init   <slug> [--title <title>] [--steps <N>] [--restart]")
        print("  state  <slug> [--json]")
        print("  update <slug> [--step <N>] [--step-status <pending|in-progress|passed|failed>] [--inc-retry] [--status <in-progress|completed|failed>] [--plan-rev <N>] [--phase <inquiry|planning|execution>] [--approve]")
        print("  approve <slug>")
        print("  phase  <slug> <inquiry|planning|execution> [--approve]")
        print("  fallback <slug> --reason <text>     Run single-agent; the reason goes to execution_trace.md")
        print("  purge  <slug> [--force --reason <text>]   Refuses while role-based steps are open")
        print("  init creates a role-based (along-team) blackboard; add '--mode direct' to opt out.")
        sys.exit(0)

    subcmd = args[0].lower()
    if len(args) < 2:
        print("[Error] Usage: along scratch [init|state|update|approve|phase|purge] <slug> [options]", file=sys.stderr)
        sys.exit(1)
    slug = _require_entity_name(args[1].lower(), f"along scratch {subcmd} <slug> [options]")

    if subcmd == "init":
        title = None
        total_steps = None
        force_restart = False
        i = 2
        while i < len(args):
            if args[i] in ("--title", "-t") and i + 1 < len(args):
                title = args[i + 1]
                i += 2
            elif args[i] in ("--steps", "-s") and i + 1 < len(args):
                try:
                    total_steps = int(args[i + 1])
                except ValueError:
                    print(f"[Error] --steps expects an integer, got '{args[i + 1]}'", file=sys.stderr)
                    sys.exit(1)
                i += 2
            elif args[i] in ("--restart", "--force", "-f"):
                force_restart = True
                i += 1
            else:
                i += 1
        # The step-loop blackboard is along-team's; gates hold it to the loop unless
        # --mode direct is asked for [feat--along-team-step-enforcement].
        mode = "direct" if "direct" in args[2:] and "--mode" in args[2:] else "role-based"
        st = session.init_session(repo_root, slug, title=title, total_steps=total_steps,
                                  force_restart=force_restart, execution_mode=mode)
        sdir = session.get_session_dir(repo_root, slug)
        print(f"-> Initialized session blackboard: {sdir}")
        print(session.format_state_summary(st))
        sys.exit(0)

    elif subcmd == "state":
        as_json = "--json" in args
        st = session.load_state(repo_root, slug)
        if not st:
            print(f"[Error] No session blackboard found for '{slug}'. Run 'along scratch init {slug}' first.", file=sys.stderr)
            sys.exit(1)
        if as_json:
            import json
            print(json.dumps(st, indent=2))
        else:
            print(session.format_state_summary(st))
        sys.exit(0)

    elif subcmd in ("approve", "plan-approve"):
        if not session.plan_recorded(repo_root, slug):
            print(f"[Error] No plan recorded for '{slug}': plan.md is still the scaffold. "
                  f"Use 'along plan approve {slug} --plan-file <path>' or write the plan into plan.md.",
                  file=sys.stderr)
            sys.exit(2)
        st = session.approve_plan(repo_root, slug)
        print(f"-> Granted plan approval for session: {slug} (phase: execution, plan_approved: true)")
        print(session.format_state_summary(st))
        sys.exit(0)

    elif subcmd == "phase":
        if len(args) < 3:
            print("[Error] Usage: along scratch phase <slug> <inquiry|planning|execution> [--approve]", file=sys.stderr)
            sys.exit(1)
        phase_val = args[2].lower()
        approve_flag = "--approve" in args
        try:
            st = session.set_session_phase(repo_root, phase_val, slug=slug, plan_approved=True if approve_flag else None)
        except ValueError as exc:
            print(f"[Error] {exc}", file=sys.stderr)
            sys.exit(1)
        print(f"-> Set session phase for {slug} to '{phase_val}' (plan_approved: {st.get('plan_approved', False)})")
        print(session.format_state_summary(st))
        sys.exit(0)

    elif subcmd == "update":
        current_step = None
        step_status = None
        status = None
        plan_rev = None
        phase_val = None
        plan_approved = None
        inc_retry = False
        i = 2
        while i < len(args):
            if args[i] in ("--step",) and i + 1 < len(args):
                try:
                    current_step = int(args[i + 1])
                except ValueError:
                    print(f"[Error] --step expects an integer, got '{args[i + 1]}'", file=sys.stderr)
                    sys.exit(1)
                i += 2
            elif args[i] in ("--step-status",) and i + 1 < len(args):
                step_status = args[i + 1].lower()
                i += 2
            elif args[i] in ("--status",) and i + 1 < len(args):
                status = args[i + 1].lower()
                i += 2
            elif args[i] in ("--phase",) and i + 1 < len(args):
                phase_val = args[i + 1].lower()
                i += 2
            elif args[i] in ("--approve", "--plan-approved"):
                plan_approved = True
                i += 1
            elif args[i] in ("--plan-rev", "--revision") and i + 1 < len(args):
                try:
                    plan_rev = int(args[i + 1])
                except ValueError:
                    print(f"[Error] --plan-rev expects an integer, got '{args[i + 1]}'", file=sys.stderr)
                    sys.exit(1)
                i += 2
            elif args[i] in ("--inc-retry", "--retry"):
                inc_retry = True
                i += 1
            else:
                i += 1
        st, retry_exhausted = session.update_state(
            repo_root, slug,
            current_step=current_step,
            step_status=step_status,
            status=status,
            phase=phase_val,
            plan_approved=plan_approved,
            plan_revision=plan_rev,
            increment_retry=inc_retry,
        )
        if retry_exhausted:
            step_num = st.get("current_step", 1)
            limit = st.get("retry_limit", session.DEFAULT_RETRY_LIMIT)
            print(f"[ALERT] Step {step_num} has exceeded the retry budget ({limit} retries)!", file=sys.stderr)
            print("Execution halted. Please inspect failures or escalate to human review.", file=sys.stderr)
            sys.exit(2)
        print(session.format_state_summary(st))
        sys.exit(0)

    elif subcmd == "fallback":
        reason = _flag_value(args, "--reason")
        if not reason:
            print("[Error] Usage: along scratch fallback <slug> --reason \"why one agent does all roles\"", file=sys.stderr)
            sys.exit(2)
        session.record_fallback(repo_root, slug, reason)
        print(f"-> '{slug}' now runs single-agent (direct); reason recorded in {session.TRACE_FILENAME}.")
        sys.exit(0)

    elif subcmd == "purge":
        problems = session.completion_problems(repo_root, slug)
        if problems and "--force" not in args:
            print(f"[Error] Refusing to purge role-based blackboard '{slug}':", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            print("  Finish the steps (with reviews/step-N.md), or 'along scratch purge <slug> --force --reason \"...\"'.",
                  file=sys.stderr)
            sys.exit(2)
        reason = _flag_value(args, "--reason")
        if problems:
            if not reason:
                print("[Error] --force needs --reason \"...\"; it is kept in the session log.", file=sys.stderr)
                sys.exit(2)
            reason = f"open problems ({'; '.join(problems)}): {reason}"
            print(f"-> Forced purge of '{slug}' with {reason}")
        if not session.load_state(repo_root, slug):
            print(f"-> Session blackboard not found (already clean): {session.get_session_dir(repo_root, slug)}")
            sys.exit(0)
        # [bug--session-records-not-captured] REQ-3: the record goes into the session log first.
        log_path = lifecycle.archive_and_purge(repo_root, slug, reason=reason, source="scratch purge")
        if log_path:
            print(f"-> Archived blackboard into {repo.safe_relpath(log_path, repo_root)}")
        if not os.path.isdir(session.get_session_dir(repo_root, slug)):
            print(f"-> Purged session blackboard: {session.get_session_dir(repo_root, slug)}")
        sys.exit(0)


    else:
        print(f"[Error] Unknown scratch subcommand: {subcmd}. Use init, state, update, or purge.", file=sys.stderr)
        sys.exit(1)


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
        sys.exit(0)

    subcmd = args[0].lower()
    if subcmd != "check":
        print(f"[Error] Unknown gates subcommand: {subcmd}. Use check.", file=sys.stderr)
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


def handle_worktree_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along worktree [create|remove|merge|list|status|gc] [args...]")
        print("Subcommands:")
        print("  create <slug> [--branch <name>] [--base-ref <ref>]")
        print("  remove <slug> [--force] [--keep-branch]")
        print("  merge  <slug> [--squash]")
        print("  list   [--json]")
        print("  status [--json]")
        print("  gc")
        sys.exit(0)

    subcmd = args[0].lower().strip()
    sub_args = args[1:]

    from alongkit import worktree

    if subcmd == "create":
        if not sub_args:
            print("[Error] Usage: along worktree create <slug> [--branch <name>] [--base-ref <ref>]", file=sys.stderr)
            sys.exit(1)
        slug = _require_entity_name(sub_args[0], "along worktree create <slug> [--branch <name>] [--base-ref <ref>]")
        branch = None
        base_ref = None
        i = 1
        while i < len(sub_args):
            if sub_args[i] == "--branch" and i + 1 < len(sub_args):
                branch = sub_args[i + 1]
                i += 2
            elif sub_args[i] == "--base-ref" and i + 1 < len(sub_args):
                base_ref = sub_args[i + 1]
                i += 2
            else:
                i += 1
        try:
            info = worktree.create_worktree(repo_root, slug, branch=branch, base_ref=base_ref)
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
        slug = sub_args[0]
        force = "--force" in sub_args or "-f" in sub_args
        keep_branch = "--keep-branch" in sub_args
        removed = worktree.remove_worktree(repo_root, slug, force=force, delete_branch=not keep_branch)
        if removed:
            print(f"-> Successfully removed worktree for '{slug}'.")
            sys.exit(0)
        else:
            print(f"[Warning] Worktree for '{slug}' was unlinked from Git but directory removal is deferred due to active file locks.", file=sys.stderr)
            print("Run 'along worktree gc' once open handles are closed.", file=sys.stderr)
            sys.exit(0)

    elif subcmd == "merge":
        if not sub_args:
            print("[Error] Usage: along worktree merge <slug> [--squash]", file=sys.stderr)
            sys.exit(1)
        slug = sub_args[0]
        strategy = "squash" if "--squash" in sub_args or "-s" in sub_args or len(sub_args) == 1 else "ff"
        res = worktree.merge_worktree(repo_root, slug, strategy=strategy)
        if res.ok:
            print(f"-> Successfully merged worktree branch 'along/{slug}' into current branch.")
            if res.stdout.strip():
                print(res.stdout.strip())
            sys.exit(0)
        else:
            print(f"[Error] Worktree merge failed: {res.stderr or res.stdout}", file=sys.stderr)
            sys.exit(1)

    elif subcmd in ("list", "status"):
        as_json = "--json" in sub_args
        items = worktree.list_worktrees(repo_root)
        if as_json:
            import json
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

    elif subcmd == "gc":
        cleaned = worktree.gc_worktrees(repo_root)
        print(f"-> Pruned worktrees and cleaned {cleaned} deferred items.")
        sys.exit(0)

    else:
        print(f"[Error] Unknown worktree subcommand: {subcmd}. Available: create, remove, merge, list, status, gc.", file=sys.stderr)
        sys.exit(1)


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


def handle_budget_command(repo_root: str, args: List[str]):
    if "-h" in args or "--help" in args or "help" in args:
        print("Usage: along_exec.py context-budget [--json] [--check]")
        sys.exit(0)
    try:
        from alongkit import budget
    except ImportError:
        print("[Error] alongkit.budget not found.", file=sys.stderr)
        sys.exit(1)

    as_json = "--json" in args
    check_mode = "--check" in args

    report = budget.measure_context(repo_root)

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
    }
    if cmd in native_routers and _wants_help(extra_args):
        _print_router_help(cmd, native_routers[cmd], repo_root, extra_args)
    _require_installation(cmd, repo_root)

    # 1. Native Entity Management Subcommands
    if cmd == "status":
        handle_status_command(repo_root, extra_args)
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
    elif cmd in ("budget", "context-budget"):
        handle_budget_command(repo_root, extra_args)
    elif cmd == "patch":
        handle_patch_command(repo_root, extra_args)
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


