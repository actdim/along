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
"""

import sys
import os
import re
import json
import shlex
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap

# This engine reads entity front-matter, so it needs ruamel.yaml. Resolve it before
# anything imports it: an engine invoked as `python <path>/<engine>.py` may start
# under an interpreter that has no dependencies prepared, which is exactly how the
# installers and the documented skill commands invoke it.
bootstrap.ensure_deps()

from alongkit import diagnostics, entities, frontmatter, lifecycle, proc, repo, session
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
    "wrap": "along_wrap.py",
}

LIFECYCLE_ACTIONS = {"build", "test", "dev", "debug"}


# Root discovery, engine resolution, and front-matter editing live in the shared
# package: alongkit.repo and alongkit.frontmatter.
find_repo_root = repo.find_repo_root
resolve_tool_script = repo.resolve_tool_script
has_frontmatter = frontmatter.has_frontmatter
update_frontmatter_fields = frontmatter.update


try_record_incident = diagnostics.try_record_incident


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

Entity Management Commands:
  status         Instant terminal summary of repository state, active issues, and recent sessions
  doctor         Validate .along/ structure, .gitattributes, and ADR headers (--entities for entity graph)
  issue create   <type> <slug> --title "Title" [--priority high|medium|low] [--tags "t1,t2"] [--agent <name>] [--milestone <name>]
  issue sync     Recompile .along/ISSUES.md projection deterministically from entity files
  issue done     <slug>
  issue list     List active issues in terminal
  session create <slug> --summary "Summary" [--issues "slug1,slug2"] [--decisions "ADR-slug"] [--agent <name>] [--milestone <name>]
  session wrap   <slug> [--status done|superseded] [--summary "Summary"] [--dry-run] [-n]
  decision create <slug> --title "Title" --context "Why" --decision "What" --consequences "Tradeoffs"
  decision sync   Recompile .along/CONSTRAINTS.md projection from active ADRs
  scratch init   <slug>
  scratch init   <slug> [--title "Title"] [--steps N] [--restart]
  scratch state  <slug> [--json]
  scratch update <slug> [--step N] [--step-status status] [--inc-retry] [--status status]
  scratch purge  <slug>
  rules attach   Detect project stack and attach relevant engineering rule packs
  budget         Measure context footprint and check token budgets (--json, --check)
  context-budget Measure context footprint and check token budgets (--json, --check)

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
  patch          Deterministic AST code patching (replace-func)
""")

RECENT_DONE_LIMIT = entities.RECENT_DONE_LIMIT
compile_issues_board = entities.compile_issues_board


def handle_issue_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along_exec.py issue [create|done|list] [args...]")
        sys.exit(0)

    subcmd = args[0].lower()
    from datetime import datetime

    issues_dir = os.path.join(repo_root, ".along", "ISSUES")
    done_dir = os.path.join(issues_dir, "done")
    os.makedirs(issues_dir, exist_ok=True)
    os.makedirs(done_dir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")

    if subcmd == "create":
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
            else:
                i += 1

        if priority not in entities.PRIORITIES:
            print(f"[Error] Invalid priority '{priority}'. Allowed priorities: {', '.join(entities.PRIORITIES)}", file=sys.stderr)
            sys.exit(1)

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
        with open(target_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        print(f"-> Created issue: {target_file}")

        # Update ISSUES.md
        issues_board = os.path.join(repo_root, ".along", "ISSUES.md")
        if os.path.exists(issues_board):
            with open(issues_board, "r", encoding="utf-8") as f:
                b_content = f.read()
            entry = f"- [ ] `({itype})` [{islug}](ISSUES/{itype}--{islug}.md)"
            if entry not in b_content:
                b_content = b_content.replace("## Active\n", f"## Active\n{entry}\n")
                with open(issues_board, "w", encoding="utf-8", newline="\n") as f:
                    f.write(b_content)
                print(f"-> Updated .along/ISSUES.md")
        sys.exit(0)

    elif subcmd in ("done", "close"):
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

        with open(found_file, "r", encoding="utf-8") as f:
            content = f.read()

        if not has_frontmatter(content):
            print(
                f"[Error] {filename} has no parseable YAML front-matter. "
                "Refusing to close it silently: fix the entity header, then retry.",
                file=sys.stderr,
            )
            sys.exit(1)

        if content.startswith("\ufeff"):
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
            content = block.bom + block.open_delim + block.raw + block.close_delim + "".join(adjusted_body_lines)

        with open(dest_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        os.remove(found_file)
        print(f"-> Moved issue to done: {dest_file}")

        # Update ISSUES.md projection with sliding window
        issues_board = os.path.join(repo_root, ".along", "ISSUES.md")
        if os.path.exists(issues_board):
            board_content = compile_issues_board(repo_root, recent_done_limit=RECENT_DONE_LIMIT)
            with open(issues_board, "w", encoding="utf-8", newline="\n") as f:
                f.write(board_content)
            print(f"-> Updated .along/ISSUES.md")
        sys.exit(0)

    elif subcmd == "sync":
        board_content = compile_issues_board(repo_root, recent_done_limit=RECENT_DONE_LIMIT)
        issues_board = os.path.join(repo_root, ".along", "ISSUES.md")
        with open(issues_board, "w", encoding="utf-8", newline="\n") as f:
            f.write(board_content)
        print(f"-> Recompiled .along/ISSUES.md projection (capped to {RECENT_DONE_LIMIT} recent completed issues).")
        sys.exit(0)

    elif subcmd == "list":
        print(f"-> Active issues in {issues_dir}:")
        count = 0
        for f in os.listdir(issues_dir):
            if f.endswith(".md") and os.path.isfile(os.path.join(issues_dir, f)):
                print(f"   - {f}")
                count += 1
        print(f"Total active issues: {count}")
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
        with open(target_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        print(f"-> Created session log: {target_file}")

        # Update HISTORY.md
        history_file = os.path.join(repo_root, ".along", "HISTORY.md")
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                h_content = f.read()
            entry = f"{today} - {slug} - {agent} - {summary} - [.along/SESSIONS/{year}/{today}--{slug}.md](./SESSIONS/{year}/{today}--{slug}.md)"
            if entry not in h_content:
                h_content = h_content.strip() + f"\n{entry}\n"
                with open(history_file, "w", encoding="utf-8", newline="\n") as f:
                    f.write(h_content)
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
        print("  sync   Recompile .along/CONSTRAINTS.md projection from active ADRs")
        sys.exit(0)

    subcmd = args[0].lower()
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")

    if subcmd == "sync":
        from alongkit import entities
        entities.sync_constraints(repo_root)
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

        dec_file = os.path.join(repo_root, ".along", "DECISIONS.md")
        entry = f"""
## ADR-{today}--{slug} - {title}
- Date: {today}
- Status: accepted
- Context: {context}
- Decision: {decision}
- Consequences: {consequences}
"""
        with open(dec_file, "a", encoding="utf-8") as f:
            f.write(entry)
        print(f"-> Appended ADR-{today}--{slug} to .along/DECISIONS.md")

        # Automatically recompile CONSTRAINTS.md projection
        from alongkit import entities
        entities.sync_constraints(repo_root)
        print("-> Updated .along/CONSTRAINTS.md projection.")
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
        with open(latest_session, "r", encoding="utf-8", errors="ignore") as f:
            lines = [l.strip() for l in f.readlines() if l.strip().startswith("summary:")]
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
        with open(gitattributes_file, "r", encoding="utf-8", errors="ignore") as f:
            ga_content = f.read()
        if "merge=union" in ga_content:
            print("[OK] .gitattributes configured with merge=union.")
        else:
            print("[WARN] .gitattributes exists but lacks merge=union for .along/ files.")
            warnings += 1

    # Check DECISIONS.md
    dec_file = os.path.join(along_dir, "DECISIONS.md")
    if os.path.exists(dec_file):
        with open(dec_file, "r", encoding="utf-8", errors="ignore") as f:
            dec_content = f.read()
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

    print(f"\nDoctor Summary: {errors} errors, {warnings} warnings.")
    sys.exit(1 if errors > 0 else 0)


def handle_scratch_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along scratch [init|state|update|purge] <slug> [options]")
        print("  init   <slug> [--title <title>] [--steps <N>] [--restart]")
        print("  state  <slug> [--json]")
        print("  update <slug> [--step <N>] [--step-status <pending|in-progress|passed|failed>] [--inc-retry] [--status <in-progress|completed|failed>] [--plan-rev <N>]")
        print("  purge  <slug>")
        sys.exit(0)

    subcmd = args[0].lower()
    if len(args) < 2:
        print("[Error] Usage: along scratch [init|state|update|purge] <slug> [options]", file=sys.stderr)
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
                    pass
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

    elif subcmd == "update":
        current_step = None
        step_status = None
        status = None
        plan_rev = None
        inc_retry = False
        i = 2
        while i < len(args):
            if args[i] in ("--step",) and i + 1 < len(args):
                try:
                    current_step = int(args[i + 1])
                except ValueError:
                    pass
                i += 2
            elif args[i] in ("--step-status",) and i + 1 < len(args):
                step_status = args[i + 1].lower()
                i += 2
            elif args[i] in ("--status",) and i + 1 < len(args):
                status = args[i + 1].lower()
                i += 2
            elif args[i] in ("--plan-rev", "--revision") and i + 1 < len(args):
                try:
                    plan_rev = int(args[i + 1])
                except ValueError:
                    pass
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
    elif cmd == "issue":
        handle_issue_command(repo_root, extra_args)
    elif cmd == "session":
        handle_session_command(repo_root, extra_args)
    elif cmd == "decision":
        handle_decision_command(repo_root, extra_args)
    elif cmd == "scratch":
        handle_scratch_command(repo_root, extra_args)
    elif cmd == "rules":
        handle_rules_command(repo_root, extra_args)
    elif cmd in ("budget", "context-budget"):
        handle_budget_command(repo_root, extra_args)
    elif cmd == "patch":
        handle_patch_command(repo_root, extra_args)
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
            with open(script_file, "r", encoding="utf-8", errors="ignore") as f:
                header = f.read(500)
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


