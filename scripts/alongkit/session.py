#!/usr/bin/env python3
"""
alongkit.session - Ephemeral multi-agent session blackboard and state management.

Provides persistent state machine tracking for `along-team` workflows:
- Externalizes execution state to `.along/.session/<slug>/`
- Tracks Living Plan (`plan.md`), findings (`research.md`), and step gate audits (`reviews/`)
- Enforces strict retry budgets (maximum 2 retries per step) stored in `state.json`
- Supports resumption across context resets and CLI-driven state transitions
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along scratch --help   (or: python scripts/along_exec.py scratch --help)"
    )

import json
import os
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from . import repo, textio

DEFAULT_RETRY_LIMIT: int = 2
STEP_STATUSES: tuple = ("pending", "in-progress", "passed", "failed")
SESSION_STATUSES: tuple = ("in-progress", "completed", "failed")


def _utc_now_iso() -> str:
    """ISO 8601 formatted UTC timestamp with trailing Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_session_dir(repo_root: str, slug: str) -> str:
    """Absolute path to the ephemeral session blackboard directory."""
    return os.path.join(repo.state_dir(repo_root), ".session", slug)


def load_state(repo_root: str, slug: str) -> Optional[Dict[str, Any]]:
    """Read and parse state.json from session blackboard, or None if absent."""
    state_file = os.path.join(get_session_dir(repo_root, slug), "state.json")
    if not os.path.isfile(state_file):
        return None
    try:
        raw = textio.read_text(state_file, strict=True)
        return json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def save_state(repo_root: str, slug: str, state: Dict[str, Any]) -> None:
    """Save state dict atomically to state.json in session blackboard."""
    session_dir = get_session_dir(repo_root, slug)
    os.makedirs(session_dir, exist_ok=True)
    state["updated"] = _utc_now_iso()
    raw = json.dumps(state, indent=2) + "\n"
    textio.write_text(os.path.join(session_dir, "state.json"), raw, newline="\n")


def init_session(
    repo_root: str,
    slug: str,
    title: Optional[str] = None,
    total_steps: Optional[int] = None,
    step_titles: Optional[List[str]] = None,
    retry_limit: int = DEFAULT_RETRY_LIMIT,
    force_restart: bool = False,
) -> Dict[str, Any]:
    """Initialize or load session blackboard with plan.md, research.md, reviews/, and state.json."""
    session_dir = get_session_dir(repo_root, slug)
    reviews_dir = os.path.join(session_dir, "reviews")
    os.makedirs(reviews_dir, exist_ok=True)

    existing_state = load_state(repo_root, slug)
    if existing_state and not force_restart:
        return existing_state

    plan_revision = 1
    if existing_state and force_restart:
        plan_revision = existing_state.get("plan_revision", 1) + 1

    now = _utc_now_iso()
    effective_title = title or slug

    # Initialize step structures
    steps_list: List[Dict[str, Any]] = []
    if step_titles:
        for idx, stitle in enumerate(step_titles, start=1):
            steps_list.append({
                "step": idx,
                "title": stitle,
                "status": "pending",
                "retries": 0,
                "started": None,
                "completed": None,
            })
    else:
        count = total_steps if total_steps and total_steps > 0 else 1
        for idx in range(1, count + 1):
            steps_list.append({
                "step": idx,
                "title": f"Step {idx}",
                "status": "pending",
                "retries": 0,
                "started": None,
                "completed": None,
            })

    state: Dict[str, Any] = {
        "slug": slug,
        "title": effective_title,
        "status": "in-progress",
        "current_step": 1,
        "total_steps": len(steps_list),
        "retry_limit": retry_limit,
        "plan_revision": plan_revision,
        "created": now,
        "updated": now,
        "steps": steps_list,
    }
    save_state(repo_root, slug, state)

    # Initialize plan.md
    plan_file = os.path.join(session_dir, "plan.md")
    if not os.path.exists(plan_file) or force_restart:
        step_lines = "\n".join(f"- [ ] Step {s['step']}: {s['title']}" for s in steps_list)
        plan_content = (
            f"# Living Plan: {slug}\n\n"
            f"Title: {effective_title}\n\n"
            f"## Steps\n{step_lines}\n"
        )
        textio.write_text(plan_file, plan_content, newline="\n")

    # Initialize research.md
    research_file = os.path.join(session_dir, "research.md")
    if not os.path.exists(research_file) or force_restart:
        research_content = (
            f"# Research & Findings: {slug}\n\n"
            f"## Target Symbols and Files\n\n"
            f"## Constraints & Risks\n\n"
            f"## Architectural Patterns\n"
        )
        textio.write_text(research_file, research_content, newline="\n")

    return state


def update_state(
    repo_root: str,
    slug: str,
    current_step: Optional[int] = None,
    step_status: Optional[str] = None,
    status: Optional[str] = None,
    plan_revision: Optional[int] = None,
    increment_retry: bool = False,
    max_retries: Optional[int] = None,
) -> Tuple[Dict[str, Any], bool]:
    """Update session state. Returns tuple (updated_state, retry_exhausted_bool)."""
    state = load_state(repo_root, slug)
    if not state:
        state = init_session(repo_root, slug)

    if status:
        state["status"] = status

    if plan_revision is not None:
        state["plan_revision"] = int(plan_revision)

    target_step = current_step if current_step is not None else state.get("current_step", 1)
    state["current_step"] = target_step

    retry_limit = max_retries if max_retries is not None else state.get("retry_limit", DEFAULT_RETRY_LIMIT)
    retry_exhausted = False

    steps = state.get("steps", [])
    step_entry: Optional[Dict[str, Any]] = None
    for s in steps:
        if s.get("step") == target_step:
            step_entry = s
            break

    if not step_entry:
        step_entry = {
            "step": target_step,
            "title": f"Step {target_step}",
            "status": "pending",
            "retries": 0,
            "started": None,
            "completed": None,
        }
        steps.append(step_entry)
        steps.sort(key=lambda x: x.get("step", 0))
        state["steps"] = steps
        state["total_steps"] = len(steps)

    now = _utc_now_iso()
    if step_status:
        step_entry["status"] = step_status
        if step_status == "in-progress" and not step_entry.get("started"):
            step_entry["started"] = now
        elif step_status in ("passed", "done", "completed"):
            step_entry["completed"] = now

    if increment_retry:
        retries = step_entry.get("retries", 0) + 1
        step_entry["retries"] = retries
        if retries > retry_limit:
            retry_exhausted = True
            step_entry["status"] = "failed"

    save_state(repo_root, slug, state)
    return state, retry_exhausted


def purge_session(repo_root: str, slug: str) -> bool:
    """Remove ephemeral session blackboard directory. True if purged, False if did not exist."""
    session_dir = get_session_dir(repo_root, slug)
    if os.path.exists(session_dir):
        shutil.rmtree(session_dir)
        return True
    return False


def format_state_summary(state: Dict[str, Any]) -> str:
    """Format a clean ASCII summary of the session state."""
    slug = state.get("slug", "unknown")
    status = state.get("status", "unknown")
    title = state.get("title", slug)
    curr = state.get("current_step", 1)
    total = state.get("total_steps", 1)
    rev = state.get("plan_revision", 1)
    limit = state.get("retry_limit", DEFAULT_RETRY_LIMIT)

    lines = [
        f"Session: {slug} (status: {status})",
        f"Title:   {title}",
        f"Step:    {curr} of {total} (Plan Rev {rev}, Retry Limit: {limit})",
        "Steps:"
    ]

    for s in state.get("steps", []):
        s_idx = s.get("step", 0)
        s_title = s.get("title", "")
        s_status = s.get("status", "pending")
        s_retries = s.get("retries", 0)
        marker = "->" if s_idx == curr else "  "
        lines.append(f"{marker} [{s_idx}] {s_title} ({s_status}, retries: {s_retries}/{limit})")

    return "\n".join(lines)

