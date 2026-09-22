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
"""

import sys
import os
import re
import json
import shlex
import shutil
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap

# This engine reads entity front-matter, so it needs ruamel.yaml. Resolve it before
# anything imports it: an engine invoked as `python <path>/<engine>.py` may start
# under an interpreter that has no dependencies prepared, which is exactly how the
# installers and the documented skill commands invoke it.
bootstrap.ensure_deps()

from alongkit import circuit, entities, frontmatter, lifecycle, proc, repo, session, textio
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
    "dash": "along_dash.py",
    "dashboard": "along_dash.py",
    "migrate": "migrate_protocol.py",
    "sanitize": "sanitize_typography.py",
    "typography": "sanitize_typography.py",
    "feedback": "along_feedback.py",
    "diagnostics": "along_feedback.py",
    "telemetry": "along_feedback.py",
    "graph-check": "along_graph_check.py",
    "graphcheck": "along_graph_check.py",
    "graph-sync": "along_graph_sync.py",
    "graphsync": "along_graph_sync.py",
    "graph-build": "along_graph_sync.py",
    "graphbuild": "along_graph_sync.py",
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
  doctor         Validate .along/ structure, .gitattributes, and ADR headers (--entities for entity graph)
  start          Atomically mark issue in-progress, initialize session blackboard, and optional --worktree
  issue create   <type> <slug> --title "Title" [--priority high|medium|low] [--tags "t1,t2"] [--agent <name>] [--milestone <name>]
  issue update   <slug> [--milestone <name>] [--priority <priority>] [--status <status>] [--tags <tags>] [--title <title>]
  issue show     <slug> [--json]
  issue sync     Recompile .along/ISSUES.md projection deterministically from entity files
  issue done     <slug>
  issue list     List active issues in terminal
  milestone sync [<slug>] Recompute target_issues, progress_pct, and status across milestones
  milestone list [--status open|in-progress|completed] [--json]
  milestone show <slug> [--json]
  session create <slug> --summary "Summary" [--issues "slug1,slug2"] [--decisions "ADR-slug"] [--agent <name>] [--milestone <name>]
  session wrap   <slug> [--status done|superseded] [--summary "Summary"] [--dry-run] [-n]
  decision create <slug> --title "Title" --context "Why" --decision "What" --consequences "Tradeoffs"
  decision sync   Recompile .along/CONSTRAINTS.md projection from active ADRs
  scratch init   <slug>
  scratch init   <slug> [--title "Title"] [--steps N] [--restart]
  scratch state  <slug> [--json]
  scratch update <slug> [--step N] [--step-status status] [--inc-retry] [--status status]
  scratch purge  <slug>
  worktree create <slug> [--branch <name>] [--base-ref <ref>]
  worktree remove <slug> [--force] [--keep-branch]
  worktree merge  <slug> [--squash]
  worktree list   [--json]
  worktree status [--json]
  worktree gc
  rules attach   Detect project stack and attach relevant engineering rule packs
  budget         Measure context footprint and check token budgets (--json, --check)
  context-budget Measure context footprint and check token budgets (--json, --check)
  circuit        Systemic anomaly circuit breaker (status, trip, reset, verify)
  run            Execute command behind runtime gate pipeline (along run <cmd...>)

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

    islug = args[2].lower()
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
    islug = args[1].lower()
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

    textio.write_text(dest_file, content, newline="\n", atomic=True)
    os.remove(found_file)
    print(f"-> Moved issue to done: {dest_file}")

    # Update ISSUES.md projection with sliding window
    issues_board = os.path.join(repo_root, ".along", "ISSUES.md")
    if os.path.exists(issues_board):
        entities.sync_issues_board(repo_root, recent_done_limit=RECENT_DONE_LIMIT)
        print("-> Updated .along/ISSUES.md")
    sys.exit(0)


def _issue_sync(repo_root: str):
    entities.sync_issues_board(repo_root, recent_done_limit=RECENT_DONE_LIMIT)
    print(f"-> Recompiled .along/ISSUES.md projection (capped to {RECENT_DONE_LIMIT} recent completed issues).")
    sys.exit(0)


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
        print("Usage: along_exec.py issue [create|update|done|sync|list|show] [args...]")
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
        "sync": lambda: _issue_sync(repo_root),
        "list": lambda: _issue_list(issues_dir),
        "update": lambda: _issue_update(repo_root, args, today),
        "edit": lambda: _issue_update(repo_root, args, today),
        "show": lambda: _issue_show(repo_root, args),
        "get": lambda: _issue_show(repo_root, args),
    }

    handler = dispatch.get(subcmd)
    if not handler:
        print(f"[Error] Unknown issue subcommand '{subcmd}'. Run 'along issue --help'.", file=sys.stderr)
        sys.exit(1)
    handler()


def handle_milestone_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along milestone [sync|list|show] [args...]")
        print("  sync [<slug>]             Recompute target_issues, progress_pct, and status")
        print("  list [--status <status>] [--json]")
        print("  show <slug> [--json]")
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

    else:
        print(f"[Error] Unknown milestone subcommand '{subcmd}'. Run 'along milestone --help'.", file=sys.stderr)
        sys.exit(1)


def handle_start_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along start <slug> [--worktree]")
        print("  Atomically marks issue in-progress, initializes session blackboard,")
        print("  and optionally creates an isolated worktree.")
        sys.exit(0)

    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")

    slug = args[0].lower()
    issue = entities.find_issue_by_slug(repo_root, slug)
    if not issue:
        print(f"[Error] Issue '{slug}' not found in .along/ISSUES/.", file=sys.stderr)
        sys.exit(1)

    updates = {"status": "in-progress", "updated": today}
    fpath, new_fm = entities.update_issue_frontmatter(repo_root, issue["slug"], updates)
    rel_path = repo.normalize_posix(repo.safe_relpath(fpath, repo_root))
    print(f"-> Marked issue in-progress: {rel_path}")

    entities.sync_issues_board(repo_root, recent_done_limit=RECENT_DONE_LIMIT)

    title = new_fm.get("title", issue["slug"].replace("-", " ").capitalize())
    st = session.init_session(repo_root, issue["slug"], title=title)
    st = session.approve_plan(repo_root, issue["slug"])
    sdir = session.get_session_dir(repo_root, issue["slug"])
    print(f"-> Initialized session blackboard: {sdir} (phase: execution, plan_approved: true)")

    if "--worktree" in args:
        from alongkit import worktree
        wt_path = worktree.create_worktree(repo_root, issue["slug"])
        print(f"-> Created isolated worktree: {wt_path}")
        print(f"-> Ready to work in worktree. Run tests and edits there.")
    else:
        print(f"-> Ready to work on issue '{issue['slug']}'. Active issue bound.")

    sys.exit(0)


def handle_session_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along_exec.py session create <slug> --summary \"Summary text\" [--issues \"slug1,slug2\"] [--decisions \"ADR-slug\"]")
        sys.exit(0)

    subcmd = args[0].lower()
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    year = datetime.now().strftime("%Y")
    sessions_dir = os.path.join(repo_root, ".along", "SESSIONS", year)
    os.makedirs(sessions_dir, exist_ok=True)

    if subcmd == "create":
        if len(args) < 2:
            print("[Error] Usage: along_exec.py session create <slug> --summary \"Summary\"", file=sys.stderr)
            sys.exit(1)
        slug = args[1].lower()
        summary = "Work session"
        issues = []
        decisions = []
        explicit_agent = None
        explicit_milestone = None

        i = 2
        while i < len(args):
            if args[i] in ("--summary", "-s") and i + 1 < len(args):
                summary = args[i + 1]
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

        milestone_line = f"milestone: {milestone}\n" if milestone else ""
        target_file = os.path.join(sessions_dir, f"{today}--{slug}.md")
        issues_str = f"[{', '.join(issues)}]" if issues else "[]"
        decisions_str = f"[{', '.join([f'\"{d}\"' for d in decisions])}]" if decisions else "[]"

        content = f"""---
protocol: along
protocol_version: "{CURRENT_PROTOCOL_VERSION}"
date: {today}
slug: {slug}
agent: {agent}
branch: main
commit: pending
summary: {summary}
{milestone_line}issues_advanced: []
issues_completed: {issues_str}
decisions: {decisions_str}
risks_logged: []
spikes_conducted: []
---

# Session: {slug.replace('-', ' ').capitalize()}

## Summary
{summary}

## Work Completed
- Document key tasks and achievements.

## Code Review & Blast Radius
- Automated tests verified and passing.
"""
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
        islug = args[1]
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

        code = lifecycle.execute_wrap(
            repo_root=repo_root,
            slug=islug,
            status=status,
            summary=summary,
            dry_run=dry_run,
            no_verify=no_verify,
            agent=explicit_agent,
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
        slug = first_arg.lower()
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
        bbs = [d for d in os.listdir(session_bb_dir) if os.path.isdir(os.path.join(session_bb_dir, d))]
        if bbs:
            print(f"\nActive Blackboards ({len(bbs)}): {', '.join(bbs)}")
    print("\n===============================")
    sys.exit(0)


def handle_doctor_command(repo_root: str, args: List[str]):
    check_entities = "--entities" in args or (bool(args) and args[0].lower() == "entities")
    if check_entities:
        print("=== Along Entity Graph Validation (Doctor) ===")
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

    print(f"\nDoctor Summary: {errors} errors, {warnings} warnings.")
    sys.exit(1 if errors > 0 else 0)


def handle_scratch_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along scratch [init|state|update|approve|phase|purge] <slug> [options]")
        print("  init   <slug> [--title <title>] [--steps <N>] [--restart]")
        print("  state  <slug> [--json]")
        print("  update <slug> [--step <N>] [--step-status <pending|in-progress|passed|failed>] [--inc-retry] [--status <in-progress|completed|failed>] [--plan-rev <N>] [--phase <inquiry|planning|execution>] [--approve]")
        print("  approve <slug>")
        print("  phase  <slug> <inquiry|planning|execution> [--approve]")
        print("  purge  <slug>")
        sys.exit(0)

    subcmd = args[0].lower()
    if len(args) < 2:
        print("[Error] Usage: along scratch [init|state|update|approve|phase|purge] <slug> [options]", file=sys.stderr)
        sys.exit(1)
    slug = args[1].lower()

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
        st = session.init_session(repo_root, slug, title=title, total_steps=total_steps, force_restart=force_restart)
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

    elif subcmd == "purge":
        if session.purge_session(repo_root, slug):
            print(f"-> Purged session blackboard: {session.get_session_dir(repo_root, slug)}")
        else:
            print(f"-> Session blackboard not found (already clean): {session.get_session_dir(repo_root, slug)}")
        sys.exit(0)


    else:
        print(f"[Error] Unknown scratch subcommand: {subcmd}. Use init, state, update, or purge.", file=sys.stderr)
        sys.exit(1)


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
        slug = sub_args[0]
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
        print("Usage: along_exec.py rules attach")
        sys.exit(0)
    
    subcmd = args[0].lower()
    if subcmd == "attach":
        try:
            from alongkit import rules
            rules.attach_rules(repo_root)
        except ImportError:
            print("[Error] alongkit.rules not found. Cannot attach rules.", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)
    else:
        print(f"[Error] Unknown rules subcommand: {subcmd}", file=sys.stderr)
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


def handle_run_command(repo_root: Optional[str], args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along run <command...>")
        print("       python scripts/along_exec.py run <command...>")
        print("")
        print("Execute a shell command behind the Along runtime lifecycle hook and gate pipeline.")
        print("Commands violating active protocol gates (typography, CLI safety, commit guard)")
        print("are blocked with exit code 2 and an error message on stderr.")
        sys.exit(0)

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


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print_help()
        sys.exit(0)

    cmd = sys.argv[1].lower().strip()
    extra_args = sys.argv[2:]
    repo_root = find_repo_root()

    # 1. Native Entity Management Subcommands
    if cmd == "status":
        handle_status_command(repo_root, extra_args)
    elif cmd == "doctor":
        handle_doctor_command(repo_root, extra_args)
    elif cmd == "circuit":
        handle_circuit_command(repo_root, extra_args)
    elif cmd == "issue":
        handle_issue_command(repo_root, extra_args)
    elif cmd in ("milestone", "milestones"):
        handle_milestone_command(repo_root, extra_args)
    elif cmd in ("start", "begin"):
        handle_start_command(repo_root, extra_args)
    elif cmd == "session":
        handle_session_command(repo_root, extra_args)
    elif cmd == "decision":
        handle_decision_command(repo_root, extra_args)
    elif cmd == "scratch":
        handle_scratch_command(repo_root, extra_args)
    elif cmd == "worktree":
        handle_worktree_command(repo_root, extra_args)
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
        script_file = get_lifecycle_script_path(repo_root, cmd)

        if os.path.exists(script_file):
            header = textio.read_text(script_file, strict=False)[:500]
            if "# Status: unconfigured" in header:
                print(f"[Notice] {script_file} is unconfigured. Please customize it for this repository.")

            print(f"-> Executing .along/scripts/{os.path.basename(script_file)}...")
            full_cmd = lifecycle.build_interpreter_cmd(script_file, extra_args)
            code = proc.run_passthrough(full_cmd, cwd=repo_root)
            sys.exit(code)

        # Auto-Detection and Non-Destructive Synthesis
        detected_cmd, verified = detect_lifecycle_action(repo_root, cmd)

        if detected_cmd and verified:
            status_tag = "verified"
            py_content = lifecycle.render_lifecycle_script(cmd, base_cmd=shlex.split(detected_cmd), status_tag=status_tag)
            synthesize_lifecycle_script(script_file, py_content)
            print(f"-> Running: {detected_cmd}")
            code = proc.run_passthrough(shlex.split(detected_cmd) + extra_args, cwd=repo_root)
            sys.exit(code)
        else:
            status_tag = "unconfigured"
            py_content = lifecycle.render_lifecycle_script(cmd, base_cmd=None, status_tag=status_tag)
            synthesize_lifecycle_script(script_file, py_content)
            print(f"[Notice] Created unconfigured template: {script_file}")
            print(f"Please customize .along/scripts/{cmd}.py for your repository build/test configuration.")
            sys.exit(0)

    print(f"[Error] Unknown command: '{cmd}'. Run 'python scripts/along_exec.py --help' for available commands.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()


