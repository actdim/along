"""
alongkit/bypass.py - A gate bypass is a human decision, and it is recorded.

Bypass flags (`along commit -n`, `along wrap -n`, `along wrap --force-reason`,
`along bump -n`, `along scratch fallback`, `along scratch purge --force`) can be typed by the
agent itself. `authorize` holds them to three rules:

1. A non-empty reason.
2. Where the runtime records user messages (Claude Code: the UserPromptSubmit hook), the
   gate must have failed in this session and the user must have replied after that failure:
   the agent showed the failure and the human decided. Without recorded user messages the
   bypass is allowed and marked `unverified`.
3. Every bypass is written to the session trace and to `.along/diagnostics/hooks_audit.jsonl`
   (`decision: bypass`); a commit also carries an `Along-Bypass:` trailer.

[feat--gate-friction-and-bypass-accountability] REQ-3
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

if __name__ == "__main__":
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Bypasses are recorded by: along commit -n --reason, along wrap -n --reason, along bump -n --reason"
    )

from . import repo, session, textio

#: Bypass names: one per flag family.
PRE_COMMIT = "pre-commit"
TESTS = "tests"
WRAP_CHECKS = "wrap-checks"
RELEASE_GATES = "release-gates"
TEAM_STEPS = "team-steps"

#: Hook gates whose denial counts as a failure of a bypass name.
_HOOK_GATE_FAILURES = {
    "team_step_active": TEAM_STEPS,
    "team_reviews_before_stop": TEAM_STEPS,
}

VERIFIED = "verified"
UNVERIFIED = "unverified"
FAILURES_DIRNAME = "gate_failures"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _epoch(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _failures_file(repo_root: str, key: Optional[str]) -> str:
    """Machine-local (diagnostics) record of gate failures per agent session."""
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", key or "no-session")
    return os.path.join(repo.diagnostics_dir(session.binding_root(repo_root)), FAILURES_DIRNAME, f"{safe}.json")


def _load_failures(repo_root: str, key: Optional[str]) -> Dict[str, str]:
    path = _failures_file(repo_root, key)
    try:
        data = json.loads(textio.read_text(path, strict=False)) if os.path.isfile(path) else {}
    except (OSError, UnicodeDecodeError, ValueError):
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def record_failure(repo_root: str, name: str, key: Optional[str] = None) -> None:
    """Remember that gate `name` failed now in this session (what a bypass must follow)."""
    if not repo_root or not repo.is_installed(repo_root):
        return
    key = key if key is not None else session.current_session_key()
    failures = _load_failures(repo_root, key)
    failures[name] = _now()
    path = _failures_file(repo_root, key)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        textio.write_text(path, json.dumps(failures, indent=2) + "\n", newline="\n")
    except OSError:
        return


def record_hook_denial(repo_root: str, gate: str, key: Optional[str]) -> None:
    """A hook gate denial that a bypass flag may later override counts as its failure."""
    name = _HOOK_GATE_FAILURES.get(gate)
    if name:
        record_failure(repo_root, name, key)


def authorize(repo_root: str, name: str, reason: Optional[str], key: Optional[str] = None) -> Tuple[Optional[str], str]:
    """(refusal, verification) for bypassing `name`; refusal None means allowed."""
    if not reason or not str(reason).strip():
        return (f"bypassing [{name}] needs a reason (--reason \"...\"): why the user accepts skipping it",
                UNVERIFIED)
    key = key if key is not None else session.current_session_key()
    last_prompt = _epoch(session.last_user_prompt_at(repo_root, key))
    if last_prompt is None:
        return None, UNVERIFIED
    failed = _epoch(_load_failures(repo_root, key).get(name))
    if failed is None:
        return (f"[{name}] has not failed in this session: run without the bypass first; if it fails, "
                "show the failure to the user and wait for their reply", UNVERIFIED)
    if last_prompt <= failed:
        return (f"no user reply since [{name}] failed: show the failure to the user and wait for their "
                "reply before bypassing it", UNVERIFIED)
    return None, VERIFIED


def record(repo_root: str, name: str, reason: str, verification: str, slug: Optional[str] = None,
           key: Optional[str] = None) -> str:
    """Write the bypass to the session trace and the hooks audit log; the trailer line."""
    key = key if key is not None else session.current_session_key()
    line = f"bypass [{name}] ({verification}): {reason.strip()}"
    target = slug or session.get_active_session_slug(repo_root, key)
    if target and session.load_state(repo_root, target) is not None:
        session.append_trace(repo_root, target, line)
    entry = {"timestamp": _now(), "gate": name, "decision": "bypass", "mode": verification,
             "runtime": (key or "").split("--", 1)[0] or "cli", "tool": "cli",
             "reason": reason.strip(), "conversation_id": key or ""}
    try:
        path = os.path.join(repo.ensure_diagnostics_dir(repo_root), "hooks_audit.jsonl")
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry) + "\n")
    except OSError:
        pass
    return f"Along-Bypass: {name}; {verification}; {reason.strip()}"


def guard(repo_root: str, name: str, reason: Optional[str], slug: Optional[str] = None) -> Optional[str]:
    """`authorize` then `record`: the trailer when allowed, None (after printing why) when refused."""
    import sys

    refusal, verification = authorize(repo_root, name, reason)
    if refusal:
        print(f"[Error] Bypass refused: {refusal}.", file=sys.stderr)
        return None
    trailer = record(repo_root, name, str(reason), verification, slug=slug)
    print(f"-> Bypass of [{name}] recorded ({verification}): {str(reason).strip()}")
    return trailer
