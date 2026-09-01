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
"""

import sys
import os
import re
import json
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

from alongkit import entities, frontmatter, proc, repo
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
}

LIFECYCLE_ACTIONS = {"build", "test", "dev", "debug"}


# Root discovery, engine resolution, and front-matter editing live in the shared
# package: alongkit.repo and alongkit.frontmatter.
find_repo_root = repo.find_repo_root
resolve_tool_script = repo.resolve_tool_script
has_frontmatter = frontmatter.has_frontmatter
update_frontmatter_fields = frontmatter.update


def try_record_incident(component: str, error_message: str, stack_trace: str = "", command: str = "", repo_root: str = ""):
    """Safely traps and records internal Along exceptions into ~/.along/diagnostics/ without crashing."""
    try:
        feedback_script = resolve_tool_script("along_feedback.py", repo_root)
        if feedback_script and os.path.exists(feedback_script):
            scripts_dir = os.path.dirname(feedback_script)
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)
            import along_feedback
            along_feedback.DiagnosticsStore.record_incident(
                component=component,
                error_message=error_message,
                event_type="script_crash",
                stack_trace=stack_trace,
                command=command,
                repo_root=repo_root
            )
    except Exception:
        pass


def get_lifecycle_script_path(repo_root: str, action: str) -> str:
    scripts_dir = os.path.join(repo_root, ".along", "scripts")
    for ext in [".py", ".sh", ".ps1", ".bat"]:
        p = os.path.join(scripts_dir, f"{action}{ext}")
        if os.path.exists(p):
            return p
    return os.path.join(scripts_dir, f"{action}.py")


def synthesize_lifecycle_script(script_path: str, content: str):
    os.makedirs(os.path.dirname(script_path), exist_ok=True)
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(content)
    try:
        os.chmod(script_path, 0o755)
    except Exception:
        pass
    print(f"-> Created lifecycle hook: {script_path}")


def detect_lifecycle_action(repo_root: str, action: str) -> Tuple[Optional[str], bool]:
    # Node.js
    pkg_json = os.path.join(repo_root, "package.json")
    if os.path.exists(pkg_json):
        try:
            with open(pkg_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            scripts = data.get("scripts", {})
            if action == "build" and "build" in scripts:
                return "npm run build", True
            elif action == "test":
                return "npm test -- --silent" if "test" in scripts else "npm test", True
            elif action == "dev":
                cmd = "npm run dev" if "dev" in scripts else ("npm start" if "start" in scripts else None)
                if cmd:
                    return cmd, True
        except Exception:
            pass

    # Rust
    if os.path.exists(os.path.join(repo_root, "Cargo.toml")):
        if action == "build":
            return "cargo build", True
        elif action == "test":
            return "cargo test -q", True
        elif action == "dev":
            return "cargo run", True

    # .NET
    if glob_files(repo_root, "*.csproj") or os.path.exists(os.path.join(repo_root, "Directory.Build.props")):
        if action == "build":
            return "dotnet build -v q", True
        elif action == "test":
            return "dotnet test -v q", True
        elif action == "dev":
            return "dotnet run", True

    # Python
    if os.path.exists(os.path.join(repo_root, "pyproject.toml")) or os.path.exists(os.path.join(repo_root, "setup.py")):
        if action == "build":
            return "python -m build", True
        elif action == "test":
            return "pytest -q" if shutil.which("pytest") else "python -m unittest discover tests -q", True
        elif action == "dev":
            for main_file in ["main.py", "app.py", "server.py"]:
                if os.path.exists(os.path.join(repo_root, main_file)):
                    return f"python {main_file}", True

    return None, False


def glob_files(root: str, pattern: str) -> bool:
    import glob
    return bool(glob.glob(os.path.join(root, pattern)))


def print_help():
    print("""Along Command Router (along_exec.py) [v2.2.0]

Usage:
  python scripts/along_exec.py <command> [subcommand] [args...]

Lifecycle Commands (project hooks):
  build          Execute project build (.along/scripts/build.py or auto-detected)
  test           Execute project tests (.along/scripts/test.py or auto-detected)
  dev            Launch project dev server (.along/scripts/dev.py or auto-detected)

Entity Management Commands:
  status         Instant terminal summary of repository state, active issues, and recent sessions
  doctor         Validate .along/ structure, .gitattributes, and ADR headers
  issue create   <type> <slug> --title "Title" [--priority high|medium|low] [--tags "t1,t2"]
  issue sync     Recompile .along/ISSUES.md projection deterministically from entity files
  issue done     <slug>
  issue list     List active issues in terminal
  session create <slug> --summary "Summary" [--issues "slug1,slug2"] [--decisions "ADR-slug"]
  decision add   <slug> --title "Title" --context "Why" --decision "What" --consequences "Tradeoffs"
  decision create <slug> --title "Title" --context "Why" --decision "What" --consequences "Tradeoffs"
  scratch init   <slug>
  scratch purge  <slug>

Along Protocol Tools:
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
""")


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
            print("[Error] Usage: along_exec.py issue create <type> <slug> --title \"Title\" [--priority high|medium|low] [--tags \"tag1,tag2\"]", file=sys.stderr)
            sys.exit(1)
        itype = args[1].lower()
        islug = args[2].lower()
        title = islug.replace("-", " ").capitalize()
        priority = "medium"
        tags = []

        i = 3
        while i < len(args):
            if args[i] in ("--title", "-t") and i + 1 < len(args):
                title = args[i + 1]
                i += 2
            elif args[i] in ("--priority", "-p") and i + 1 < len(args):
                priority = args[i + 1]
                i += 2
            elif args[i] in ("--tags",) and i + 1 < len(args):
                tags = [t.strip() for t in args[i + 1].split(",") if t.strip()]
                i += 2
            else:
                i += 1

        target_file = os.path.join(issues_dir, f"{itype}--{islug}.md")
        tags_str = f"[{', '.join(tags)}]" if tags else "[]"
        content = f"""---
protocol: along
slug: {islug}
type: {itype}
status: open
priority: {priority}
created: {today}
updated: {today}
agent: antigravity
tags: {tags_str}
milestone: v2.1.0-along
blocked_by: []
related: []
---

# {title}

Describe the feature, requirements, and background context here.

## Acceptance Criteria
- [ ] Task requirement 1
- [ ] Automated tests passing
"""
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"-> Created issue: {target_file}")

        # Update ISSUES.md
        issues_board = os.path.join(repo_root, ".along", "ISSUES.md")
        if os.path.exists(issues_board):
            with open(issues_board, "r", encoding="utf-8") as f:
                b_content = f.read()
            entry = f"- [ ] `({itype})` [{islug}](file://.along/ISSUES/{itype}--{islug}.md)"
            if entry not in b_content:
                b_content = b_content.replace("## Active\n", f"## Active\n{entry}\n")
                with open(issues_board, "w", encoding="utf-8") as f:
                    f.write(b_content)
                print(f"-> Updated .along/ISSUES.md")
        sys.exit(0)

    elif subcmd == "done":
        if len(args) < 2:
            print("[Error] Usage: along_exec.py issue done <slug>", file=sys.stderr)
            sys.exit(1)
        islug = args[1].lower()
        
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

        content = update_frontmatter_fields(
            content,
            {"status": "done", "updated": today, "completed": today},
            place_after={"completed": "status"},
        )

        with open(dest_file, "w", encoding="utf-8") as f:
            f.write(content)
        os.remove(found_file)
        print(f"-> Moved issue to done: {dest_file}")

        # Update ISSUES.md
        issues_board = os.path.join(repo_root, ".along", "ISSUES.md")
        if os.path.exists(issues_board):
            with open(issues_board, "r", encoding="utf-8") as f:
                b_content = f.read()
            # Remove from Active
            b_content = re.sub(rf'- \[[ ~]\] `\(\w+\)` \[{re.escape(islug)}\]\([^\)]+\)\n?', '', b_content)
            # Add to Done
            itype = filename.split("--")[0]
            done_entry = f"- [x] `({itype})` [{islug}](file://.along/ISSUES/done/{filename})"
            if done_entry not in b_content:
                b_content = b_content.replace("## Done (recent)\n", f"## Done (recent)\n{done_entry}\n")
            with open(issues_board, "w", encoding="utf-8") as f:
                f.write(b_content)
            print(f"-> Updated .along/ISSUES.md")
        sys.exit(0)

    elif subcmd == "sync":
        active_items = []
        done_items = []

        if os.path.exists(issues_dir):
            for f in sorted(os.listdir(issues_dir)):
                if f.endswith(".md") and os.path.isfile(os.path.join(issues_dir, f)):
                    parts = f[:-3].split("--", 1)
                    itype = parts[0]
                    islug = parts[1] if len(parts) > 1 else f[:-3]
                    active_items.append(f"- [ ] `({itype})` [{islug}](file://.along/ISSUES/{f})")

        if os.path.exists(done_dir):
            for f in sorted(os.listdir(done_dir), reverse=True):
                if f.endswith(".md") and os.path.isfile(os.path.join(done_dir, f)):
                    parts = f[:-3].split("--", 1)
                    itype = parts[0]
                    islug = parts[1] if len(parts) > 1 else f[:-3]
                    done_items.append(f"- [x] `({itype})` [{islug}](file://.along/ISSUES/done/{f})")

        board_content = f"""# Active Issues

## Active
{chr(10).join(active_items) if active_items else "<!-- No active issues -->"}

## Backlog
<!-- Planned or deferred issues -->

## Done (recent)
{chr(10).join(done_items) if done_items else "<!-- No completed issues -->"}
"""
        issues_board = os.path.join(repo_root, ".along", "ISSUES.md")
        with open(issues_board, "w", encoding="utf-8") as f:
            f.write(board_content)
        print(f"-> Recompiled .along/ISSUES.md projection ({len(active_items)} active, {len(done_items)} done).")
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
            else:
                i += 1

        target_file = os.path.join(sessions_dir, f"{today}--{slug}.md")
        issues_str = f"[{', '.join(issues)}]" if issues else "[]"
        decisions_str = f"[{', '.join([f'\"{d}\"' for d in decisions])}]" if decisions else "[]"

        content = f"""---
protocol: along
date: {today}
slug: {slug}
agent: antigravity
branch: main
commit: pending
summary: {summary}
milestone: v2.2.0-along
issues_advanced: []
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
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"-> Created session log: {target_file}")

        # Update HISTORY.md
        history_file = os.path.join(repo_root, ".along", "HISTORY.md")
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                h_content = f.read()
            entry = f"{today} - {slug} - antigravity - {summary} - [.along/SESSIONS/{year}/{today}--{slug}.md](file://.along/SESSIONS/{year}/{today}--{slug}.md)"
            if entry not in h_content:
                h_content = h_content.strip() + f"\n{entry}\n"
                with open(history_file, "w", encoding="utf-8") as f:
                    f.write(h_content)
                print(f"-> Appended history entry to .along/HISTORY.md")
        sys.exit(0)


def handle_decision_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along_exec.py decision create <slug> --title \"Title\" --context \"Context\" --decision \"Decision\" --consequences \"Tradeoffs\"")
        sys.exit(0)

    subcmd = args[0].lower()
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")

    if subcmd in ("create", "add"):
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

    print(f"\nDoctor Summary: {errors} errors, {warnings} warnings.")
    sys.exit(1 if errors > 0 else 0)


def handle_scratch_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along_exec.py scratch [init|purge] <slug>")
        sys.exit(0)

    subcmd = args[0].lower()
    if len(args) < 2:
        print("[Error] Usage: along_exec.py scratch [init|purge] <slug>", file=sys.stderr)
        sys.exit(1)
    slug = args[1].lower()
    scratch_dir = os.path.join(repo_root, ".along", ".session", slug)

    if subcmd == "init":
        os.makedirs(scratch_dir, exist_ok=True)
        plan_file = os.path.join(scratch_dir, "plan.md")
        if not os.path.exists(plan_file):
            with open(plan_file, "w", encoding="utf-8") as f:
                f.write(f"# Living Plan: {slug}\n\n## Steps\n- [ ] Step 1: Initialize\n")
        print(f"-> Initialized scratchpad: {scratch_dir}")
        sys.exit(0)
    elif subcmd == "purge":
        if os.path.exists(scratch_dir):
            shutil.rmtree(scratch_dir)
            print(f"-> Purged scratchpad: {scratch_dir}")
        else:
            print(f"-> Scratchpad not found (already clean): {scratch_dir}")
        sys.exit(0)


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
            if script_file.endswith(".py"):
                code = proc.run_passthrough([sys.executable, script_file] + extra_args, cwd=repo_root)
            else:
                code = proc.run_passthrough([script_file] + extra_args, cwd=repo_root, shell=True)
            sys.exit(code)

        # Auto-Detection and Non-Destructive Synthesis
        detected_cmd, verified = detect_lifecycle_action(repo_root, cmd)

        if detected_cmd and verified:
            status_tag = "verified"
            py_content = f'''#!/usr/bin/env python3
# Status: {status_tag}
# Auto-generated by Along for {cmd}
import sys, subprocess, os

def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cmd = "{detected_cmd}"
    extra = " ".join(sys.argv[1:])
    full_cmd = f"{{cmd}} {{extra}}".strip()
    print(f"-> Running: {{full_cmd}}")
    res = subprocess.run(full_cmd, shell=True, cwd=repo_root)
    sys.exit(res.returncode)

if __name__ == "__main__":
    main()
'''
            synthesize_lifecycle_script(script_file, py_content)
            print(f"-> Running: {detected_cmd}")
            code = proc.run_passthrough(f"{detected_cmd} {' '.join(extra_args)}".strip(), shell=True, cwd=repo_root)
            sys.exit(code)
        else:
            status_tag = "unconfigured"
            py_content = f'''#!/usr/bin/env python3
# Status: {status_tag}
# Template for {cmd} in this repository
import sys, subprocess, os

def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print("[Notice] Please configure {cmd} command in .along/scripts/{cmd}.py")

if __name__ == "__main__":
    main()
'''
            synthesize_lifecycle_script(script_file, py_content)
            print(f"[Notice] Created unconfigured template: {script_file}")
            print(f"Please customize .along/scripts/{cmd}.py for your repository build/test configuration.")
            sys.exit(0)

    print(f"[Error] Unknown command: '{cmd}'. Run 'python scripts/along_exec.py --help' for available commands.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()


