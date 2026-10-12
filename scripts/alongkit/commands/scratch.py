#!/usr/bin/env python3
"""
alongkit.commands.scratch - Modular CLI command router for along scratch.
[debt--along-exec-argparse-migration]
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: python .along/scripts/test.py"
    )

import argparse
import json
import os
import sys
from typing import List

from alongkit import lifecycle, repo, session
from .common import check_unknown_args, require_entity_name


def cli_approval_or_exit(repo_root: str, slug: str) -> str:
    """Hold a CLI plan approval of `slug` to the user's last message; its `approved_via`."""
    key = session.current_session_key()
    refusal, via = session.check_cli_approval(
        repo_root, key, os.path.join(session.get_session_dir(repo_root, slug), "plan.md")
    )
    if refusal:
        print(f"[Error] Plan approval refused: {refusal}.", file=sys.stderr)
        sys.exit(2)
    session.append_trace(repo_root, slug, f"plan approved (along scratch; approved_via: {via})")
    return via


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="along scratch",
        description="Session blackboard and step-loop lifecycle management.",
        allow_abbrev=False,
    )
    sub = parser.add_subparsers(dest="subcmd")

    p_init = sub.add_parser("init", help="Initialize session blackboard")
    p_init.add_argument("slug", help="Session slug")
    p_init.add_argument("--title", "-t", default=None, help="Session title")
    p_init.add_argument("--steps", "-s", type=int, default=None, help="Number of steps")
    p_init.add_argument("--restart", "--force", "-f", dest="restart", action="store_true", help="Force restart")
    p_init.add_argument("--mode", default=None, choices=["direct", "role-based"], help="Execution mode")

    p_state = sub.add_parser("state", help="Inspect session blackboard state")
    p_state.add_argument("slug", help="Session slug")
    p_state.add_argument("--json", action="store_true", help="Format as JSON")

    for name in ("approve", "plan-approve"):
        p_app = sub.add_parser(name, help="Approve plan and transition to execution phase")
        p_app.add_argument("slug", help="Session slug")

    p_phase = sub.add_parser("phase", help="Set session phase")
    p_phase.add_argument("slug", help="Session slug")
    p_phase.add_argument("phase", choices=["inquiry", "planning", "execution"], help="Target phase")
    p_phase.add_argument("--approve", action="store_true", help="Also approve plan")

    p_update = sub.add_parser("update", help="Update step loop state")
    p_update.add_argument("slug", help="Session slug")
    p_update.add_argument("--step", type=int, default=None, help="Current step index")
    p_update.add_argument("--step-status", default=None, help="Step status")
    p_update.add_argument("--status", default=None, help="Overall status")
    p_update.add_argument("--phase", default=None, help="Phase")
    p_update.add_argument("--approve", "--plan-approved", dest="approve", action="store_true", help="Mark plan approved")
    p_update.add_argument("--plan-rev", "--revision", dest="plan_rev", type=int, default=None, help="Plan revision")
    p_update.add_argument("--inc-retry", "--retry", dest="inc_retry", action="store_true", help="Increment retry count")

    p_fallback = sub.add_parser("fallback", help="Switch blackboard to single-agent (direct) mode")
    p_fallback.add_argument("slug", help="Session slug")
    p_fallback.add_argument("--reason", required=True, help="Justification for bypassing multi-agent loop")

    p_purge = sub.add_parser("purge", help="Archive and purge session blackboard")
    p_purge.add_argument("slug", help="Session slug")
    p_purge.add_argument("--force", action="store_true", help="Force purge despite open steps")
    p_purge.add_argument("--reason", default=None, help="Reason required when forcing purge")

    return parser


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
    slug = require_entity_name(args[1].lower(), f"along scratch {subcmd} <slug> [options]")
    sub_args = args[1:]

    if subcmd == "init":
        parser = argparse.ArgumentParser(prog="along scratch init", allow_abbrev=False)
        parser.add_argument("slug")
        parser.add_argument("--title", "-t", default=None)
        parser.add_argument("--steps", "-s", default=None)
        parser.add_argument("--restart", "--force", "-f", dest="restart", action="store_true")
        parser.add_argument("--mode", default=None)
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along scratch init")

        total_steps = None
        if parsed.steps is not None:
            try:
                total_steps = int(parsed.steps)
            except ValueError:
                print("[Error] --steps expects an integer", file=sys.stderr)
                sys.exit(1)

        mode = "direct" if parsed.mode == "direct" else "role-based"
        st = session.init_session(
            repo_root, slug,
            title=parsed.title,
            total_steps=total_steps,
            force_restart=parsed.restart,
            execution_mode=mode,
        )
        sdir = session.get_session_dir(repo_root, slug)
        print(f"-> Initialized session blackboard: {sdir}")
        print(session.format_state_summary(st))
        sys.exit(0)

    elif subcmd == "state":
        parser = argparse.ArgumentParser(prog="along scratch state", allow_abbrev=False)
        parser.add_argument("slug")
        parser.add_argument("--json", action="store_true")
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along scratch state")

        st = session.load_state(repo_root, slug)
        if not st:
            print(f"[Error] No session blackboard found for '{slug}'. Run 'along scratch init {slug}' first.", file=sys.stderr)
            sys.exit(1)
        if parsed.json:
            print(json.dumps(st, indent=2))
        else:
            print(session.format_state_summary(st))
        sys.exit(0)

    elif subcmd in ("approve", "plan-approve"):
        parser = argparse.ArgumentParser(prog=f"along scratch {subcmd}", allow_abbrev=False)
        parser.add_argument("slug")
        _parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, f"along scratch {subcmd}")

        if not session.plan_recorded(repo_root, slug):
            print(f"[Error] No plan recorded for '{slug}': plan.md is still the scaffold. "
                  f"Use 'along plan approve {slug} --plan-file <path>' or write the plan into plan.md.",
                  file=sys.stderr)
            sys.exit(2)
        cli_approval_or_exit(repo_root, slug)
        st = session.approve_plan(repo_root, slug)
        print(f"-> Granted plan approval for session: {slug} (phase: execution, plan_approved: true)")
        print(session.format_state_summary(st))
        sys.exit(0)

    elif subcmd == "phase":
        if len(args) < 3:
            print("[Error] Usage: along scratch phase <slug> <inquiry|planning|execution> [--approve]", file=sys.stderr)
            sys.exit(1)
        parser = argparse.ArgumentParser(prog="along scratch phase", allow_abbrev=False)
        parser.add_argument("slug")
        parser.add_argument("phase")
        parser.add_argument("--approve", action="store_true")
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along scratch phase")

        phase_val = parsed.phase.lower()
        if parsed.approve:
            cli_approval_or_exit(repo_root, slug)
        try:
            st = session.set_session_phase(repo_root, phase_val, slug=slug, plan_approved=True if parsed.approve else None)
        except ValueError as exc:
            print(f"[Error] {exc}", file=sys.stderr)
            sys.exit(1)
        print(f"-> Set session phase for {slug} to '{phase_val}' (plan_approved: {st.get('plan_approved', False)})")
        print(session.format_state_summary(st))
        sys.exit(0)

    elif subcmd == "update":
        parser = argparse.ArgumentParser(prog="along scratch update", allow_abbrev=False)
        parser.add_argument("slug")
        parser.add_argument("--step", default=None)
        parser.add_argument("--step-status", default=None)
        parser.add_argument("--status", default=None)
        parser.add_argument("--phase", default=None)
        parser.add_argument("--approve", "--plan-approved", dest="approve", action="store_true")
        parser.add_argument("--plan-rev", "--revision", dest="plan_rev", default=None)
        parser.add_argument("--inc-retry", "--retry", dest="inc_retry", action="store_true")
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along scratch update")

        current_step = None
        if parsed.step is not None:
            try:
                current_step = int(parsed.step)
            except ValueError:
                print("[Error] --step expects an integer", file=sys.stderr)
                sys.exit(1)

        plan_rev = None
        if parsed.plan_rev is not None:
            try:
                plan_rev = int(parsed.plan_rev)
            except ValueError:
                print("[Error] --plan-rev expects an integer", file=sys.stderr)
                sys.exit(1)

        if parsed.approve:
            cli_approval_or_exit(repo_root, slug)
        st, retry_exhausted = session.update_state(
            repo_root, slug,
            current_step=current_step,
            step_status=parsed.step_status.lower() if parsed.step_status else None,
            status=parsed.status.lower() if parsed.status else None,
            phase=parsed.phase.lower() if parsed.phase else None,
            plan_approved=True if parsed.approve else None,
            plan_revision=plan_rev,
            increment_retry=parsed.inc_retry,
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
        parser = argparse.ArgumentParser(prog="along scratch fallback", allow_abbrev=False)
        parser.add_argument("slug")
        parser.add_argument("--reason", default=None)
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along scratch fallback")

        if not parsed.reason:
            print("[Error] Usage: along scratch fallback <slug> --reason \"why one agent does all roles\"", file=sys.stderr)
            sys.exit(2)
        from alongkit import bypass
        if not bypass.guard(repo_root, bypass.TEAM_STEPS, parsed.reason, slug=slug):
            sys.exit(2)
        session.record_fallback(repo_root, slug, parsed.reason)
        print(f"-> '{slug}' now runs single-agent (direct); reason recorded in {session.TRACE_FILENAME}.")
        sys.exit(0)

    elif subcmd == "purge":
        parser = argparse.ArgumentParser(prog="along scratch purge", allow_abbrev=False)
        parser.add_argument("slug")
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--reason", default=None)
        parsed, extra = parser.parse_known_args(sub_args)
        check_unknown_args(extra, "along scratch purge")

        from alongkit import bypass
        problems = session.completion_problems(repo_root, slug)
        if problems and not parsed.force:
            bypass.record_failure(repo_root, bypass.TEAM_STEPS)
            print(f"[Error] Refusing to purge role-based blackboard '{slug}':", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            print("  Finish the steps (with reviews/step-N.md), or 'along scratch purge <slug> --force --reason \"...\"'.",
                  file=sys.stderr)
            sys.exit(2)
        reason = parsed.reason
        if problems:
            if not reason:
                print("[Error] --force needs --reason \"...\"; it is kept in the session log.", file=sys.stderr)
                sys.exit(2)
            if not bypass.guard(repo_root, bypass.TEAM_STEPS, reason, slug=slug):
                sys.exit(2)
            reason = f"open problems ({'; '.join(problems)}): {reason}"
            print(f"-> Forced purge of '{slug}' with {reason}")
        if not session.load_state(repo_root, slug):
            print(f"-> Session blackboard not found (already clean): {session.get_session_dir(repo_root, slug)}")
            sys.exit(0)
        unrecorded = session.unrecorded_files(repo_root, slug)
        if unrecorded:
            print(f"[Error] Refusing to purge blackboard '{slug}': unknown non-scaffold file(s):", file=sys.stderr)
            for f in unrecorded:
                print(f"  - {f}", file=sys.stderr)
            sys.exit(2)
        log_path = lifecycle.archive_and_purge(repo_root, slug, reason=reason, source="scratch purge")
        if log_path:
            print(f"-> Archived blackboard into {repo.safe_relpath(log_path, repo_root)}")
        if not os.path.isdir(session.get_session_dir(repo_root, slug)):
            print(f"-> Purged session blackboard: {session.get_session_dir(repo_root, slug)}")
        sys.exit(0)

    else:
        print(f"[Error] Unknown scratch subcommand: {subcmd}. Use init, state, update, or purge.", file=sys.stderr)
        sys.exit(1)
