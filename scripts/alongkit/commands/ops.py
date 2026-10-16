#!/usr/bin/env python3
"""
alongkit.commands.ops - Operational CLI commands: rules, tool nature, budget, circuit breaker, patch, devenv, and run runner.
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
from datetime import datetime, timezone
from typing import List, Optional

from .. import circuit, proc, repo


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
