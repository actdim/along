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
import sys

# Ensure repository scripts directory is on sys.path
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from alongkit import bootstrap, repo

bootstrap.ensure_deps()

from alongkit.hooks import (
    HookEventType,
    HooksConfig,
    evaluate_event,
    get_adapter,
    load_config,
)


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "install":
        parser = argparse.ArgumentParser(
            prog="along hook install",
            description="Install or update runtime lifecycle hook configuration.",
        )
        parser.add_argument("--runtime", default="antigravity", help="Target runtime (antigravity)")
        parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
        parser.add_argument("--repo-root", default=None, help="Path to repository root")
        args = parser.parse_args(sys.argv[2:])

        repo_root = args.repo_root or repo.find_repo_root()
        if not repo_root:
            sys.stderr.write("[Along Hook] Error: cannot locate repository root.\n")
            return 1

        from alongkit.hooks.config import install_antigravity_hooks
        status, msg = install_antigravity_hooks(repo_root, dry_run=args.dry_run)
        print(f"-> [Along Hook] {msg}")
        return 0 if status in ("installed", "present", "dry-run") else 1

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


    parser = argparse.ArgumentParser(
        description="Along Protocol runtime hook dispatcher.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--runtime",
        default="antigravity",
        help="Target agent runtime (antigravity, claude, codex, generic)",
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

    repo_root = args.repo_root or repo.find_repo_root()
    config: HooksConfig = load_config(repo_root)
    if args.mode:
        config.mode = args.mode

    adapter = get_adapter(args.runtime)

    try:
        raw_input = sys.stdin.read()
    except (OSError, UnicodeDecodeError) as exc:
        sys.stderr.write(f"[Along Hook] Failed to read stdin: {exc}\n")
        raw_input = ""

    event_type = HookEventType(args.event)
    event = adapter.parse(raw_input, event_type=event_type)
    if not event.workspace_root and repo_root:
        event.workspace_root = repo_root

    try:
        result = evaluate_event(event, repo_root=repo_root, config=config)
    except (OSError, UnicodeDecodeError, ValueError, KeyError, AttributeError) as exc:
        sys.stderr.write(f"[Along Hook] Evaluation error: {exc}\n")
        from alongkit.hooks import GateDecision, GateResult
        result = GateResult(
            decision=GateDecision.DENY,
            reason=f"Along Runtime Gate Error: {exc}",
            exit_code=2,
        )

    exit_code, response_str = adapter.format_response(result)
    if response_str:
        sys.stdout.write(response_str + "\n")
        sys.stdout.flush()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
