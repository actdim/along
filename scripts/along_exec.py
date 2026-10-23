#!/usr/bin/env python3
"""along_exec.py - Unified Command Router & Lifecycle Dispatcher for Along Protocol."""


import os
import shlex
import shutil
import sys
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap

# Ensure runtime dependencies (ruamel.yaml) before importing engines
bootstrap.ensure_deps()

from alongkit import entities, frontmatter, gates, lifecycle, proc, repo
from alongkit.commands import (
    handle_brief_command,
    handle_budget_command,
    handle_decision_command,
    handle_devenv_command,
    handle_doctor_command,
    handle_env_command,
    handle_gates_command,
    handle_git_command,
    handle_history_command,
    handle_issue_command,
    handle_lint_command,
    handle_milestone_command,
    handle_orchestrate_command,
    handle_patch_command,
    handle_plan_command,
    handle_rules_command,
    handle_run_command,
    handle_scratch_command,
    handle_session_command,
    handle_start_command,
    handle_status_command,
    handle_team_command,
    handle_telemetry_command,
    handle_worktree_command,
)
from alongkit.commands.lifecycle import _cli_approval_or_exit
from alongkit.commands.session import _render_session_log
from alongkit.commands.telemetry import _get_active_telemetry_endpoint

# Backward compatibility exports
find_repo_root = repo.find_repo_root
resolve_tool_script = repo.resolve_tool_script
has_frontmatter = frontmatter.has_frontmatter
update_frontmatter_fields = frontmatter.update

get_lifecycle_script_path = lifecycle.get_lifecycle_script_path
synthesize_lifecycle_script = lifecycle.synthesize_lifecycle_script
detect_lifecycle_action = lifecycle.detect_lifecycle_action
resolve_output_mode = lifecycle.resolve_output_mode
run_lifecycle_command = lifecycle.run_lifecycle_command

RECENT_DONE_LIMIT = entities.RECENT_DONE_LIMIT
compile_issues_board = entities.compile_issues_board

TOOL_MAPPINGS = {
    "brief": "along_brief.py",
    "kb-sync": "along_kb_sync.py", "kbsync": "along_kb_sync.py",
    "kb-search": "along_kb_search.py", "kbsearch": "along_kb_search.py",
    "dep-scan": "along_dep_scan.py", "depscan": "along_dep_scan.py",
    "history-sync": "along_history_sync.py", "historysync": "along_history_sync.py",
    "commit": "along_commit.py",
    "version-bump": "along_version_bump.py", "versionbump": "along_version_bump.py", "bump": "along_version_bump.py",
    "update": "along_update.py",
    "init": "along_init.py",
    "dash": "along_dash.py", "dashboard": "along_dash.py",
    "migrate": "migrate_protocol.py",
    "sanitize": "sanitize_typography.py", "typography": "sanitize_typography.py",
    "feedback": "along_feedback.py", "diagnostics": "along_feedback.py",
    "graph-check": "along_graph_check.py", "graphcheck": "along_graph_check.py",
    "graph-sync": "along_graph_sync.py", "graphsync": "along_graph_sync.py",
    "graph-build": "along_graph_sync.py", "graphbuild": "along_graph_sync.py",
    "graph-impact": "along_graph_impact.py", "graphimpact": "along_graph_impact.py",
    "graph-arch": "along_graph_arch.py", "grapharch": "along_graph_arch.py",
    "wrap": "along_wrap.py",
    "hook": "along_hook.py", "hooks": "along_hook.py",
    "resolve": "along_resolve.py",
    "conflict-check": "along_conflict_check.py", "conflictcheck": "along_conflict_check.py",
    "env": "along_env.py",
}

LIFECYCLE_ACTIONS = {"build", "test", "dev", "debug"}
HELP_FLAGS = ("-h", "--help")

_BOARD_COMMANDS = frozenset({
    "issue", "milestone", "milestones", "start", "begin", "session", "plan", "decision",
    "scratch", "worktree", "wrap", "commit", "brief", "orchestrate", "team",
})


def print_help():
    print("""Along Command Router (along_exec.py)

Usage:
  python scripts/along_exec.py <command> [subcommand] [args...]
  along <command> [subcommand] [args...]

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
  lint           Commit-time checks on demand (alias of 'gates check')
  rules          Rule packs management (attach, status, diff, restore)
  brief          Generate deterministic role-based brief (along brief <slug> --role <role>)
  orchestrate    Execute cross-runtime multi-agent loop (along orchestrate <slug> [options])
  team           Along team multi-agent orchestration (along team orchestrate <slug> [options])
  env            Isolated Docker environment management (up, down, status, logs, shell, update)
  budget         Measure context footprint and check token budgets (--json, --check)
  context-budget Measure context footprint and check token budgets (--json, --check)
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
  migrate        Run protocol migration and YAML front-matter fixes
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


def _wants_help(args: List[str]) -> bool:
    """True when -h/--help appears anywhere before a `--` separator."""
    for arg in args:
        if arg == "--":
            return False
        if arg in HELP_FLAGS:
            return True
    return False


def _require_installation(cmd: str, repo_root: str) -> None:
    """Exit 2 when a board command runs where Along is not installed."""
    if cmd in _BOARD_COMMANDS and not repo.is_installed(repo_root):
        print(f"[Error] Along is not installed in {repo_root} (no .along/ with Along state). "
              "Run 'along init' there, or run the command inside an installed context.",
              file=sys.stderr)
        sys.exit(2)


def _print_router_help(cmd: str, handler, repo_root: str, args: List[str]) -> None:
    """Print a router's usage (narrowed to the named subcommand) and exit 0, writing nothing."""
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

    native_routers = {
        "status": handle_status_command,
        "doctor": handle_doctor_command,
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
        "lint": handle_lint_command,
        "rules": handle_rules_command,
        "env": handle_env_command,
        "budget": handle_budget_command,
        "context-budget": handle_budget_command,
        "patch": handle_patch_command,
        "history": handle_history_command,
        "dev-env": handle_devenv_command,
        "devenv": handle_devenv_command,
        "run": handle_run_command,
        "brief": handle_brief_command,
        "orchestrate": handle_orchestrate_command,
        "team": handle_team_command,
    }

    if cmd in native_routers and _wants_help(extra_args):
        _print_router_help(cmd, native_routers[cmd], repo_root, extra_args)

    _require_installation(cmd, repo_root)

    # 1. Native Entity & System Management Subcommands
    if cmd in native_routers:
        native_routers[cmd](repo_root, extra_args)
        sys.exit(0)

    if cmd == "kb":
        sub = extra_args[0].lower() if extra_args else "sync"
        mapped = "along_kb_sync.py" if sub == "sync" else "along_kb_search.py"
        script_path = resolve_tool_script(mapped, repo_root)
        if script_path:
            code = proc.run_passthrough([sys.executable, script_path] + extra_args[1:], cwd=repo_root)
            sys.exit(code)

    if cmd == "graph":
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
            print("Searched in local scripts/ and global Along home.", file=sys.stderr)
            sys.exit(1)

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

        detected_cmd, verified = detect_lifecycle_action(repo_root, cmd)

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


def cli_entry():
    """Top-level CLI entry point with clean error formatting to prevent raw traceback leakage."""
    try:
        main()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        if os.environ.get("ALONG_DEBUG"):
            raise
        sys.stderr.write(f"[Along Error] {exc}\n")
        sys.stderr.write("Suggestion: run 'along --help' or 'along doctor' for diagnostic guidance.\n")
        sys.exit(1)


if __name__ == "__main__":
    cli_entry()
