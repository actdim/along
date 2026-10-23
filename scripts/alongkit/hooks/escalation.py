#!/usr/bin/env python3
"""
alongkit.hooks.escalation - Escalation routing and classification for autonomous execution.

Under the autonomous profile, interactive confirmation is disabled. Operations requiring human
or remote operator approval are routed through the escalation pipeline:
- Push to default branch ('main', 'master')
- Tag or release commands
- Package publication
- Deployment commands
- Dangerous filesystem deletions or history rewrites

Escalations are dispatched to an escalation handler (e.g. Telegram Live Status Card). If no handler
is configured or if escalation times out, the operation is denied deterministically and recorded
in the session run record.
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along doctor   (or: python scripts/along_exec.py doctor)"
    )

from dataclasses import dataclass, field
import json
import os
import re
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .. import proc, repo, session, textio
from . import deletion, shellparse
from .adapters.normalize import SHELL_TOOLS
from .models import GateDecision, GateResult, HookEvent

OP_PUSH_DEFAULT = "push_to_default_branch"
OP_TAG_RELEASE = "tag_or_release"
OP_PACKAGE_PUBLISH = "package_publish"
OP_DEPLOY = "deploy"
OP_DANGEROUS_DELETION = "dangerous_deletion"

DEFAULT_BRANCHES: Tuple[str, ...] = ("main", "master")

ALL_ESCALATION_OPERATIONS: Tuple[str, ...] = (
    OP_PUSH_DEFAULT,
    OP_TAG_RELEASE,
    OP_PACKAGE_PUBLISH,
    OP_DEPLOY,
    OP_DANGEROUS_DELETION,
)

EscalationHandler = Callable[[HookEvent, str, str, str], Optional[GateResult]]

_GLOBAL_ESCALATION_HANDLER: Optional[EscalationHandler] = None


def set_escalation_handler(handler: Optional[EscalationHandler]) -> None:
    """Register a custom escalation handler (for Telegram approval, daemon runner, or tests)."""
    global _GLOBAL_ESCALATION_HANDLER
    _GLOBAL_ESCALATION_HANDLER = handler


def get_escalation_handler() -> Optional[EscalationHandler]:
    """Retrieve the currently registered escalation handler."""
    return _GLOBAL_ESCALATION_HANDLER


def reset_escalation_handler() -> None:
    """Reset escalation handler to default None."""
    global _GLOBAL_ESCALATION_HANDLER
    _GLOBAL_ESCALATION_HANDLER = None


def _is_git_push_default_branch(words: List[str], cwd: str, repo_root: str) -> Optional[str]:
    """Detect if git push targets main or master."""
    if not words:
        return None
    cmd = os.path.basename(words[0]).lower()
    if cmd in ("git", "git.exe"):
        sub = deletion._strip_git_globals(words)
        if sub and sub[0] == "push":
            args = sub[1:]
            # Look for explicit branch target
            for arg in args:
                if arg.startswith("-"):
                    continue
                # Could be remote or refspec
                for b in DEFAULT_BRANCHES:
                    if arg == b or arg.endswith(f":{b}") or arg.endswith(f"/{b}"):
                        return f"git push to default branch '{b}'"
            # If no refspec specified, check current branch in cwd/repo_root
            check_dir = cwd if os.path.isdir(cwd) else repo_root
            res = proc.run_capture(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=check_dir, check=False)
            if res.ok and res.stdout.strip() in DEFAULT_BRANCHES:
                branch = res.stdout.strip()
                return f"git push on current default branch '{branch}'"
    return None


def _is_tag_or_release(words: List[str]) -> Optional[str]:
    """Detect git tag or release commands."""
    if not words:
        return None
    cmd = os.path.basename(words[0]).lower()
    args = words[1:]
    if cmd in ("git", "git.exe"):
        sub = deletion._strip_git_globals(words)
        if sub and sub[0] == "tag":
            # Creating or deleting a tag
            return "git tag operation"
    if cmd == "along" or (cmd in ("python", "python.exe", "py") and args and "along" in args[0].lower()):
        sub_words = args if cmd != "along" else words[1:]
        if sub_words and sub_words[0] in ("bump", "version-bump", "release"):
            return f"along {sub_words[0]} release operation"
    if cmd in ("npm", "pnpm", "yarn") and args and args[0] == "version":
        return f"{cmd} version release operation"
    if cmd == "cargo" and args and args[0] == "release":
        return "cargo release operation"
    return None


def _is_package_publish(words: List[str]) -> Optional[str]:
    """Detect package publishing commands."""
    if not words:
        return None
    cmd = os.path.basename(words[0]).lower()
    args = words[1:]
    if cmd in ("npm", "pnpm", "yarn") and args and args[0] == "publish":
        return f"{cmd} publish operation"
    if cmd == "twine" and args and args[0] == "upload":
        return "twine upload package publication"
    if cmd in ("flit", "poetry") and args and args[0] == "publish":
        return f"{cmd} publish operation"
    if cmd == "cargo" and args and args[0] == "publish":
        return "cargo publish operation"
    if cmd == "dotnet" and len(args) >= 2 and args[0] == "nuget" and args[1] == "push":
        return "dotnet nuget push package publication"
    return None


def _is_deploy(words: List[str]) -> Optional[str]:
    """Detect infrastructure deployment commands."""
    if not words:
        return None
    cmd = os.path.basename(words[0]).lower()
    args = words[1:]
    if cmd == "kubectl" and args and args[0] in ("apply", "delete", "replace", "patch", "rollout"):
        return f"kubectl {args[0]} deployment"
    if cmd == "helm" and args and args[0] in ("install", "upgrade", "rollback", "uninstall"):
        return f"helm {args[0]} deployment"
    if cmd == "terraform" and args and args[0] in ("apply", "destroy"):
        return f"terraform {args[0]} deployment"
    if cmd == "docker" and len(args) >= 2 and args[0] == "compose" and args[1] in ("up", "down"):
        return f"docker compose {args[1]} deployment"
    if cmd == "docker" and len(args) >= 2 and args[0] == "stack" and args[1] in ("deploy", "rm"):
        return f"docker stack {args[1]} deployment"
    if cmd in ("aws", "gcloud", "flyctl") and args and "deploy" in args:
        return f"{cmd} deploy deployment"
    if cmd == "deploy":
        return "direct deploy invocation"
    return None


def classify_escalation(
    event: HookEvent,
    repo_root: Optional[str] = None,
) -> Optional[Tuple[str, str]]:
    """Determine whether an event is on the escalation list.

    Returns:
        (operation_type, detail_string) if in escalation list, else None.
    """
    effective_root = repo_root or event.workspace_root
    cmd = event.tool_args.get("CommandLine") or event.tool_args.get("command") or ""
    if not cmd:
        return None

    args = event.tool_args or {}
    from . import containment
    cwd = next((str(args[k]) for k in containment.CWD_ARG_KEYS if args.get(k)), "") \
        or event.workspace_root or effective_root or "."
    if not os.path.isabs(cwd) and effective_root:
        cwd = os.path.join(effective_root, cwd)

    segments = shellparse.split_segments(cmd)
    if segments is None:
        segments = [cmd]

    for seg in segments:
        words = shellparse.words(seg)
        if not words:
            continue

        # 1. Dangerous deletion / destructive command
        if effective_root:
            prob = deletion.find_problem(seg, cwd, effective_root)
            if prob:
                return OP_DANGEROUS_DELETION, f"destructive deletion/reset: {prob}"

        # 2. Push to default branch
        push_detail = _is_git_push_default_branch(words, cwd, effective_root or ".")
        if push_detail:
            return OP_PUSH_DEFAULT, push_detail

        # 3. Tag or release
        rel_detail = _is_tag_or_release(words)
        if rel_detail:
            return OP_TAG_RELEASE, rel_detail

        # 4. Package publish
        pub_detail = _is_package_publish(words)
        if pub_detail:
            return OP_PACKAGE_PUBLISH, pub_detail

        # 5. Deployment
        dep_detail = _is_deploy(words)
        if dep_detail:
            return OP_DEPLOY, dep_detail

    return None


def record_escalation_outcome(
    repo_root: str,
    operation: str,
    outcome: str,
    detail: str,
    slug: Optional[str] = None,
) -> None:
    """Record escalation decision / timeout in session run record and activity trace."""
    effective_slug = slug
    if not effective_slug:
        effective_slug, _ = session.resolve_active_session(repo_root)
    if not effective_slug:
        candidates = session.in_progress_slugs(repo_root)
        if len(candidates) == 1:
            effective_slug = candidates[0]

    timestamp = session._utc_now_iso()
    entry = {
        "operation": operation,
        "outcome": outcome,
        "detail": detail,
        "timestamp": timestamp,
    }

    # 1. Update latest run record if available
    if effective_slug:
        try:
            from .. import handoff
            records = handoff.list_run_records(repo_root, effective_slug)
            if records:
                latest = records[-1]
                latest_id = str(latest.get("run_id", ""))
                rec = handoff.load_run_record(repo_root, effective_slug, latest_id)
                if rec:
                    rec.setdefault("escalations", []).append(entry)
                    if outcome == "timeout":
                        rec["outcome"] = "timeout"
                    handoff.save_run_record(repo_root, effective_slug, rec)
        except (OSError, UnicodeDecodeError, ValueError, KeyError, AttributeError):
            pass

    # 2. Append to activity trace
    try:
        from .predicates import load_activity_trace, save_activity_trace
        trace = load_activity_trace(repo_root)
        trace.setdefault("escalations", []).append(entry)
        save_activity_trace(repo_root, trace)
    except (OSError, UnicodeDecodeError, ValueError, KeyError, AttributeError):
        pass


def route_escalation(
    event: HookEvent,
    op_type: str,
    detail: str,
    repo_root: str,
    original_reason: Optional[str] = None,
) -> GateResult:
    """Route an escalation operation to registered handler, or deny deterministically."""
    from .predicates import event_session_key
    key = event_session_key(event)
    slug, _ = session.resolve_active_session(repo_root, key=key)
    if not slug:
        candidates = session.in_progress_slugs(repo_root)
        if len(candidates) == 1:
            slug = candidates[0]

    handler = get_escalation_handler()
    if handler is not None:
        try:
            res = handler(event, op_type, detail, repo_root)
            if isinstance(res, GateResult):
                outcome = "allow" if res.is_allowed else "denied"
                record_escalation_outcome(repo_root, op_type, outcome, detail, slug=slug)
                return res
        except TimeoutError:
            record_escalation_outcome(repo_root, op_type, "timeout", detail, slug=slug)
            return GateResult(
                decision=GateDecision.DENY,
                reason=f"Escalation timed out: {detail} was not approved within timeout window.",
                gate_name="escalation",
                exit_code=2,
            )
        except (OSError, ValueError, RuntimeError, TypeError, TimeoutError) as exc:
            record_escalation_outcome(repo_root, op_type, "error", f"{detail} error: {exc}", slug=slug)
            return GateResult(
                decision=GateDecision.DENY,
                reason=f"Escalation handler error: {exc}",
                gate_name="escalation",
                exit_code=2,
            )

    # Default autonomous behavior: no handler configured -> deterministic deny
    reason = f"Autonomous escalation denied: {detail} requires operator approval (escalation handler not configured)."
    if original_reason:
        reason = f"{reason} Details: {original_reason}"
    record_escalation_outcome(repo_root, op_type, "unhandled", detail, slug=slug)
    return GateResult(
        decision=GateDecision.DENY,
        reason=reason,
        gate_name="escalation",
        exit_code=2,
    )
