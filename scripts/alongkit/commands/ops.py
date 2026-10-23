#!/usr/bin/env python3
"""
alongkit.commands.ops - Operational CLI commands: rules, budget, patch, devenv, and run runner.
[debt--split-along-exec-and-entities]
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: python .along/scripts/test.py"
    )

import json
import os
import shlex
import shutil
import sys
from typing import List, Optional

from .. import proc, repo


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
            print(json.dumps(report, indent=2))
        else:
            print(budget.format_prompt_budget_text(report))

        if check_mode and not report.get("passed", True):
            sys.exit(1)
        sys.exit(0)

    as_json = "--json" in args
    check_mode = "--check" in args

    report = budget.measure_context(repo_root, limits=budget.config_limits(repo_root))

    if as_json:
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


def handle_run_command(repo_root: Optional[str], args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along run [antigravity|agy|claude|codex|opencode|generic] [options] | along run <command...>")
        print("       python scripts/along_exec.py run [antigravity|agy] [options] | run <command...>")
        print("")
        print("Agent Runtime Runner:")
        print("  along run antigravity [--dry-run] [-i|--issue <slug>] [--run-id <id>] [--endpoint <url>] [--binary <path>]")
        print("  along run [claude|codex|opencode|generic] [--dry-run] [-i|--issue <slug>] [--model <model>] [--timeout <sec>]")
        print("  Supervise agent process, enforce workspace containment, and capture telemetry/handoff records.")
        print("")
        print("Lifecycle Command Proxy:")
        print("  Execute a shell command behind the Along runtime lifecycle hook and gate pipeline.")
        print("  Commands violating active protocol gates (typography, CLI safety, commit guard)")
        print("  are blocked with exit code 2 and an error message on stderr.")
        sys.exit(0)

    target_subcmd = args[0].lower()
    if target_subcmd in ("antigravity", "agy"):
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

    if target_subcmd in ("claude", "claude-code", "codex", "opencode", "generic"):
        sub_args = args[1:]
        dry_run = False
        issue_slug = None
        run_id = None
        model = None
        timeout = None
        binary = None
        brief = "Execute assigned issue tasks."
        role = "implementer"
        base_url = None
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
            elif arg in ("--model", "-m") and i + 1 < len(sub_args):
                model = sub_args[i + 1]
                i += 2
            elif arg in ("--timeout",) and i + 1 < len(sub_args):
                try:
                    timeout = int(sub_args[i + 1])
                except ValueError:
                    timeout = None
                i += 2
            elif arg in ("--binary", "-b") and i + 1 < len(sub_args):
                binary = sub_args[i + 1]
                i += 2
            elif arg in ("--brief", "--prompt", "-p") and i + 1 < len(sub_args):
                brief = sub_args[i + 1]
                i += 2
            elif arg in ("--role", "-r") and i + 1 < len(sub_args):
                role = sub_args[i + 1]
                i += 2
            elif arg in ("--base-url",) and i + 1 < len(sub_args):
                base_url = sub_args[i + 1]
                i += 2
            elif arg in ("-h", "--help", "help"):
                print(f"Usage: along run {target_subcmd} [options] [-- <extra-args...>]")
                print("Options:")
                print("  --dry-run, -n          Preview configured environment and parameters without spawning")
                print("  -i, --issue <slug>     Bind run to specific active issue (defaults to in-progress issue)")
                print("  --run-id <id>          Explicit run ID for handoff run record")
                print("  -m, --model <name>     Model identifier override")
                print("  --timeout <seconds>    Process timeout in seconds")
                print("  -b, --binary <path>    Explicit path to CLI binary")
                print("  -p, --brief <text>     Brief or prompt text for headless execution")
                print("  -r, --role <name>      Role profile (scout, architect, implementer, reviewer)")
                if target_subcmd == "opencode":
                    print("  --base-url <url>       Local Ollama/vLLM base URL endpoint (OPENAI_BASE_URL)")
                sys.exit(0)
            elif arg == "--":
                pass_args.extend(sub_args[i + 1:])
                break
            else:
                pass_args.append(arg)
                i += 1

        from alongkit.runner import get_runner
        runner_kwargs: Dict[str, Any] = {
            "repo_root": repo_root,
            "issue_slug": issue_slug,
            "run_id": run_id,
            "model": model,
            "timeout": timeout,
            "binary_path": binary,
            "dry_run": dry_run,
            "extra_args": pass_args,
        }
        if target_subcmd == "opencode" and base_url:
            runner_kwargs["base_url"] = base_url

        try:
            adapter = get_runner(target_subcmd, **runner_kwargs)
            record = adapter.execute_run(brief=brief, role=role, model=model, timeout=timeout)
        except RuntimeError as exc:
            sys.stderr.write(f"[Along Runner Error] {exc}\n")
            sys.exit(1)
        print(json.dumps(record, indent=2))
        sys.exit(record.get("exit_code") or 0)

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
