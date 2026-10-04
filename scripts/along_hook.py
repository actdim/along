#!/usr/bin/env python3
"""
scripts/along_hook.py - Universal CLI entry point for runtime lifecycle hooks.

Receives agent lifecycle hook payloads on stdin, dispatches them through the Along
Gate Pipeline (Typography, Projection Protection, CLI Safety), and formats
runtime-specific responses.

Usage:
  python scripts/along_hook.py --runtime antigravity --event PreToolUse
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import sys

# Ensure repository scripts directory is on sys.path
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from alongkit import bootstrap, proc, repo

# Fail open: a missing dependency is a setup fault, and exit 2 would block every tool.
bootstrap.ensure_deps(missing_exit_code=0)

from alongkit.hooks import (
    HookEvent,
    HookEventType,
    HooksConfig,
    evaluate_event,
    get_adapter,
    load_config,
)


_GIT_HOOK_STATUS_TEXT = {
    "installed": "installed",
    "installed-chained-previous": "installed; existing hook kept as <hook>.pre-along and run first",
    "updated": "updated",
    "present": "already up to date",
    "removed": "removed",
    "removed-restored-previous": "removed; previous hook restored",
    "absent": "not installed",
}


def _install_git_hooks(args) -> int:
    repo_root = args.repo_root or repo.find_repo_root()
    if not repo_root:
        sys.stderr.write("[Along Hook] Error: cannot locate repository root.\n")
        return 1
    from alongkit import gitgates

    report = gitgates.install_hooks(repo_root, uninstall=args.uninstall, dry_run=args.dry_run)
    statuses = set(report.values())
    if statuses == {"not-a-git-repo"}:
        sys.stderr.write(f"[Along Hook] Error: not a git repository: {repo_root}\n")
        return 1
    if statuses == {"skipped-core-hooksPath"}:
        print("-> [Along Hook] core.hooksPath is set (husky, lefthook, ...); nothing was written.")
        print("   Add these commands to your hook manager instead:")
        print("     pre-commit: along gates check --hook pre-commit")
        print('     commit-msg: along gates check --hook commit-msg "$1"')
        return 0
    prefix = "[DRY-RUN] " if args.dry_run else ""
    for name, status in report.items():
        print(f"-> [Along Hook] {prefix}git {name}: {_GIT_HOOK_STATUS_TEXT.get(status, status)}")
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "install":
        parser = argparse.ArgumentParser(
            prog="along hook install",
            description="Install or update runtime lifecycle hook configuration.",
        )
        parser.add_argument(
            "--runtime",
            default="antigravity",
            choices=["antigravity", "claude", "codex", "cursor", "all"],
            help="Target runtime (antigravity, claude, codex, cursor, all)",
        )
        parser.add_argument("--global", dest="is_global", action="store_true", help="Install hooks globally in user home")
        parser.add_argument("--target-home", default=None, help="Target home directory for global installation")
        parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
        parser.add_argument("--repo-root", default=None, help="Path to repository root (for local install)")
        parser.add_argument("--git", action="store_true",
                            help="Install git pre-commit/commit-msg hooks (opt-in; runtime-agnostic gates)")
        parser.add_argument("--uninstall", action="store_true", help="With --git: remove the Along git hooks")
        args = parser.parse_args(sys.argv[2:])

        if args.git:
            return _install_git_hooks(args)

        repo_root = None
        if not args.is_global:
            repo_root = args.repo_root or repo.find_repo_root()
            if not repo_root:
                sys.stderr.write("[Along Hook] Error: cannot locate repository root.\n")
                return 1

        from alongkit.hooks.config import (
            install_antigravity_hooks,
            install_claude_hooks,
            install_codex_hooks,
            install_cursor_hooks,
        )

        statuses = []
        if args.runtime in ("antigravity", "all"):
            status, msg = install_antigravity_hooks(
                repo_root, dry_run=args.dry_run, is_global=args.is_global, target_home=args.target_home
            )
            print(f"-> [Along Hook] {msg}")
            statuses.append(status)

        if args.runtime in ("claude", "all"):
            status, msg = install_claude_hooks(
                repo_root, dry_run=args.dry_run, is_global=args.is_global, target_home=args.target_home
            )
            print(f"-> [Along Hook] {msg}")
            statuses.append(status)

        if args.runtime in ("codex", "all"):
            status, msg = install_codex_hooks(
                repo_root, dry_run=args.dry_run, is_global=args.is_global, target_home=args.target_home
            )
            print(f"-> [Along Hook] {msg}")
            statuses.append(status)

        if args.runtime in ("cursor", "all"):
            status, msg = install_cursor_hooks(
                repo_root, dry_run=args.dry_run, is_global=args.is_global, target_home=args.target_home
            )
            print(f"-> [Along Hook] {msg}")
            statuses.append(status)

        return 0 if all(s in ("installed", "present", "dry-run") for s in statuses) else 1


    if len(sys.argv) > 1 and sys.argv[1] == "attribution":
        parser = argparse.ArgumentParser(
            prog="along hook attribution",
            description="Turn off AI commit attribution (Co-Authored-By) in installed runtimes "
                        "(Claude Code settings.json, Cursor cli-config.json). Hooks are not touched.",
        )
        parser.add_argument("--runtime", default="all", choices=["claude", "cursor", "all"],
                            help="Runtime(s) to reconcile")
        parser.add_argument("--claude-home", default=None, help="Claude Code home (default: ~/.claude)")
        parser.add_argument("--cursor-home", default=None, help="Cursor home (default: ~/.cursor)")
        parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
        parser.add_argument("--repo-root", default=None, help="Repository whose .along/config.json may opt out")
        args = parser.parse_args(sys.argv[2:])

        from alongkit.hooks.config import reconcile_attribution
        results = reconcile_attribution(
            claude_home=args.claude_home, cursor_home=args.cursor_home,
            dry_run=args.dry_run, repo_root=args.repo_root or repo.find_repo_root(),
            runtimes=("claude", "cursor") if args.runtime == "all" else (args.runtime,),
        )
        for _, msg in results:
            print(f"-> [Along Attribution] {msg}")
        if not results:
            print("-> [Along Attribution] no Claude Code or Cursor home found; nothing to do")
        return 0 if all(s != "failed" for s, _ in results) else 1


    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        parser = argparse.ArgumentParser(
            prog="along hook verify",
            description="Verify bi-directional traceability between prose rules and runtime gates.",
        )
        parser.add_argument("--repo-root", default=None, help="Path to repository root")
        parser.add_argument("--strict", action="store_true", help="Fail if any gate is undocumented")
        args = parser.parse_args(sys.argv[2:])

        repo_root = args.repo_root or repo.find_repo_root()
        from alongkit.hooks.traceability import audit_traceability, format_traceability_report
        report = audit_traceability(repo_root)
        print(format_traceability_report(report))
        if not report.is_clean:
            return 1
        if args.strict and report.undocumented_gates:
            return 1
        return 0


    if len(sys.argv) > 1 and sys.argv[1] == "run":
        run_args = sys.argv[2:]
        if not run_args or run_args[0] in ("-h", "--help", "help"):
            print("Usage: along_hook.py run <command...>")
            print("       along run <command...>")
            return 0
        repo_root = repo.find_repo_root()
        config = load_config(repo_root)
        cmd_str = " ".join(run_args)
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
            return 2
        exec_args = list(run_args)
        if len(exec_args) == 1 and not shutil.which(exec_args[0]):
            try:
                split_args = shlex.split(exec_args[0], posix=(os.name != "nt"))
                if split_args and shutil.which(split_args[0]):
                    exec_args = split_args
            except ValueError:
                pass
        return proc.run_passthrough(exec_args, cwd=repo_root)

    if len(sys.argv) > 1 and sys.argv[1] == "eval":
        parser = argparse.ArgumentParser(
            prog="along hook eval",
            description="Evaluate declarative gates against an incoming event payload.",
        )
        parser.add_argument(
            "event",
            help="Lifecycle event trigger name (PreToolUse, PostToolUse, PreInvocation, PostInvocation, Stop)",
        )
        parser.add_argument(
            "payload",
            nargs="?",
            default=None,
            help="Event JSON or command payload (can also be passed via --payload or stdin)",
        )
        parser.add_argument(
            "--payload",
            "-p",
            dest="payload_opt",
            default=None,
            help="Event JSON or command string payload",
        )
        parser.add_argument(
            "--runtime",
            default="generic",
            help="Target agent runtime (antigravity, claude, codex, cursor, opencode, generic)",
        )
        parser.add_argument(
            "--mode",
            choices=["enforce", "shadow"],
            default=None,
            help="Override execution governance mode (enforce vs shadow)",
        )
        parser.add_argument(
            "--repo-root",
            default=None,
            help="Path to repository root (auto-detected if omitted)",
        )
        args = parser.parse_args(sys.argv[2:])

        raw_input = args.payload_opt if args.payload_opt is not None else args.payload
        if raw_input is None:
            try:
                raw_input = sys.stdin.read()
            except (OSError, UnicodeDecodeError) as exc:
                sys.stderr.write(f"[Along Hook] Failed to read stdin: {exc}\n")
                raw_input = ""

        return _evaluate_and_respond(
            raw_input=raw_input,
            event_name=args.event,
            runtime=args.runtime,
            repo_root=args.repo_root,
            mode=args.mode,
        )

    parser = argparse.ArgumentParser(
        description="Along Protocol runtime hook dispatcher.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--runtime",
        default="antigravity",
        help="Target agent runtime (antigravity, claude, codex, cursor, opencode, generic)",
    )
    parser.add_argument(
        "--event",
        default="PreToolUse",
        choices=["PreToolUse", "PostToolUse", "PreInvocation", "PostInvocation", "Stop"],
        help="Lifecycle event trigger name",
    )
    parser.add_argument(
        "--mode",
        choices=["enforce", "shadow"],
        default=None,
        help="Override execution governance mode (enforce vs shadow)",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Path to repository root (auto-detected if omitted)",
    )
    args = parser.parse_args()

    try:
        raw_input = sys.stdin.read()
    except (OSError, UnicodeDecodeError) as exc:
        sys.stderr.write(f"[Along Hook] Failed to read stdin: {exc}\n")
        raw_input = ""

    return _evaluate_and_respond(
        raw_input=raw_input,
        event_name=args.event,
        runtime=args.runtime,
        repo_root=args.repo_root,
        mode=args.mode,
    )


def _evaluate_and_respond(
    raw_input: str,
    event_name: str,
    runtime: str = "antigravity",
    repo_root: str | None = None,
    mode: str | None = None,
) -> int:
    raw_input = raw_input.lstrip("\ufeff")
    adapter = get_adapter(runtime)

    try:
        event_type = HookEventType(event_name)
    except (ValueError, KeyError):
        event_type = HookEventType.PRE_TOOL_USE

    event = adapter.parse(raw_input, event_type=event_type)

    effective_root = repo_root
    if not effective_root and event.workspace_root:
        effective_root = repo.find_repo_root(event.workspace_root) or event.workspace_root
    if not effective_root:
        effective_root = repo.find_repo_root()

    # Fail-open check: if workspace does not carry Along protocol, do not block
    is_along_repo = bool(
        effective_root and (
            os.path.isdir(os.path.join(effective_root, ".along"))
            or os.path.isdir(os.path.join(effective_root, ".agents"))
            or os.path.isfile(os.path.join(effective_root, "AGENTS.md"))
        )
    )
    if not is_along_repo:
        from alongkit.hooks import GateDecision, GateResult
        exit_code, response_str = adapter.format_response(
            GateResult(decision=GateDecision.ALLOW, exit_code=0)
        )
        if response_str:
            sys.stdout.write(response_str + "\n")
            sys.stdout.flush()
        return 0

    if not event.workspace_root and effective_root:
        event.workspace_root = effective_root

    # Proof for `along doctor` that this runtime's hooks actually fire here.
    from datetime import datetime, timezone
    from alongkit import runtime as runtime_info
    runtime_info.record_heartbeat(
        effective_root, adapter.runtime_name or runtime,
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    config: HooksConfig = load_config(effective_root)
    if mode:
        config.mode = mode
        for k in config.gates:
            config.gates[k] = mode

    try:
        result = evaluate_event(event, repo_root=effective_root, config=config)
    except (OSError, UnicodeDecodeError, ValueError, KeyError, AttributeError) as exc:
        sys.stderr.write(f"[Along Hook] Evaluation error: {exc}\n")
        from alongkit.hooks import GateDecision, GateResult
        result = GateResult(
            decision=GateDecision.DENY,
            reason=f"Along Runtime Gate Error: {exc}",
            exit_code=2,
        )

    if getattr(result, "decision", None) and result.decision.value != "deny":
        # After evaluate_event succeeds, record telemetry if in a runner session
        run_id = os.environ.get("ALONG_RUN_ID")
        if run_id and effective_root:
            try:
                from alongkit.telemetry.tracer import Tracer
                active_tracer = Tracer.get_active()
                if active_tracer is not None:
                    if event_type == HookEventType.PRE_TOOL_USE and event.tool_name:
                        span = active_tracer.active_span
                        if span:
                            span.add_event(
                                f"hook.pre_tool.{event.tool_name}",
                                attributes={
                                    "tool.name": event.tool_name,
                                    "hook.runtime": runtime,
                                    "hook.decision": result.decision.value if hasattr(result, 'decision') else "allow",
                                },
                            )
                    elif event_type == HookEventType.POST_TOOL_USE and event.tool_name:
                        span = active_tracer.active_span
                        if span:
                            raw = event.raw_payload or {}
                            tool_result = raw.get("toolResult", {})
                            attrs = {
                                "tool.name": event.tool_name,
                                "hook.runtime": runtime,
                            }
                            if isinstance(tool_result, dict):
                                if "exitCode" in tool_result:
                                    attrs["process.exit.code"] = tool_result["exitCode"]
                                if "durationMs" in tool_result:
                                    attrs["tool.duration_ms"] = tool_result["durationMs"]
                            span.add_event(
                                f"hook.post_tool.{event.tool_name}",
                                attributes=attrs,
                            )
            except (ImportError, OSError, RuntimeError, AttributeError, TypeError):
                pass  # Fail-open: telemetry faults must never block the hook

    exit_code, response_str = adapter.format_response(result)
    if response_str:
        target_stream = sys.stderr if exit_code != 0 else sys.stdout
        target_stream.write(response_str + "\n")
        target_stream.flush()

    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError, KeyError, AttributeError, TypeError) as exc:
        sys.stderr.write(f"[Along Hook] Internal error (fail-open): {exc}\n")
        sys.exit(0)
