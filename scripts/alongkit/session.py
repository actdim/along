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
SESSION_PHASES: tuple = ("inquiry", "planning", "execution")
DEFAULT_PHASE: str = "inquiry"



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


def get_global_session_file(repo_root: str) -> str:
    """Path to the repository-level session phase lock (.along/.session/state.json)."""
    return os.path.join(repo.state_dir(repo_root), ".session", "state.json")


def load_global_session_state(repo_root: str) -> Optional[Dict[str, Any]]:
    """Read and parse global session state from .along/.session/state.json, or None."""
    gfile = get_global_session_file(repo_root)
    if not os.path.isfile(gfile):
        return None
    try:
        raw = textio.read_text(gfile, strict=False)
        return json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def save_global_session_state(repo_root: str, state: Dict[str, Any]) -> None:
    """Save global session state dict to .along/.session/state.json."""
    gfile = get_global_session_file(repo_root)
    os.makedirs(os.path.dirname(gfile), exist_ok=True)
    state["updated"] = _utc_now_iso()
    raw = json.dumps(state, indent=2) + "\n"
    textio.write_text(gfile, raw, newline="\n")


# ---------------------------------------------------------------------------
# Agent-session bindings
#
# Several agent sessions may work in one repository at once. Each one is bound to its own
# issue slug through `.along/.session/bindings/<runtime>--<session_id>.json`; gates resolve
# the slug from the binding of the session that triggered the hook, never from a
# repository-wide pointer. See [bug--session-state-cross-session-leak].
# ---------------------------------------------------------------------------

BINDINGS_DIRNAME: str = "bindings"
#: Bindings untouched for this long are removed by `gc_bindings`.
BINDING_MAX_AGE_HOURS: int = 72

#: Environment variables that name the agent session a CLI call runs in, per runtime.
#: `ALONG_SESSION_ID` (with optional `ALONG_SESSION_RUNTIME`) is the runtime-neutral override.
SESSION_ENV_MARKERS: Tuple[Tuple[str, str], ...] = (
    ("CLAUDE_CODE_SESSION_ID", "claude"),
    ("ANTIGRAVITY_CONVERSATION_ID", "antigravity"),
    ("CODEX_SESSION_ID", "codex"),
)

#: Every environment variable that ties a process to an agent session or issue; the test
#: runner clears them so the suite stays hermetic.
SESSION_ENV_VARS: Tuple[str, ...] = tuple(v for v, _ in SESSION_ENV_MARKERS) + (
    "ALONG_SESSION_ID", "ALONG_SESSION_RUNTIME", "ALONG_ISSUE_SLUG",
)


def _safe_key_part(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in value)[:128]


def session_key(runtime: Optional[str], session_id: Optional[str]) -> Optional[str]:
    """`<runtime>--<session_id>` or None when the session id is unknown."""
    if not session_id:
        return None
    return f"{_safe_key_part(runtime or 'generic')}--{_safe_key_part(str(session_id))}"


def current_session_key(env: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Session key of the agent session this process runs in, from its environment."""
    env = dict(os.environ) if env is None else env
    explicit = (env.get("ALONG_SESSION_ID") or "").strip()
    if explicit:
        return session_key((env.get("ALONG_SESSION_RUNTIME") or "generic").strip(), explicit)
    for var, runtime_name in SESSION_ENV_MARKERS:
        value = (env.get(var) or "").strip()
        if value:
            return session_key(runtime_name, value)
    return None


def binding_root(repo_root: str) -> str:
    """Workspace directory that holds the bindings: the outermost `.along/` owner.

    One binding per agent session for the whole workspace, so a session bound to a
    subproject issue is visible to gates evaluated at the workspace root. The walk stops
    at the git repository top (a `.git` directory; submodules have a `.git` file) and
    never climbs to or above the home directory, whose `~/.along` is the global install.
    """
    cur = os.path.abspath(repo_root)
    home = os.path.normcase(os.path.abspath(os.path.expanduser("~")))
    best = cur
    while True:
        if os.path.normcase(cur) == home:
            break
        if os.path.isdir(os.path.join(cur, repo.STATE_DIR)) or os.path.isdir(os.path.join(cur, repo.LEGACY_STATE_DIR)):
            best = cur
        if os.path.isdir(os.path.join(cur, ".git")):
            break
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return best


def bindings_dir(repo_root: str) -> str:
    return os.path.join(repo.state_dir(binding_root(repo_root)), ".session", BINDINGS_DIRNAME)


def _same_dir(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def binding_context(repo_root: str, binding: Optional[Dict[str, Any]]) -> Optional[str]:
    """Absolute directory of the `.along/` the bound issue lives in."""
    if not binding:
        return None
    rel = binding.get("context") or "."
    return os.path.normpath(os.path.join(binding_root(repo_root), rel))


def _binding_file(repo_root: str, key: str) -> str:
    return os.path.join(bindings_dir(repo_root), f"{key}.json")


def load_binding(repo_root: str, key: Optional[str]) -> Optional[Dict[str, Any]]:
    if not key:
        return None
    path = _binding_file(repo_root, key)
    if not os.path.isfile(path):
        return None
    try:
        data = json.loads(textio.read_text(path, strict=False))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def save_binding(repo_root: str, key: str, data: Dict[str, Any]) -> Dict[str, Any]:
    data["key"] = key
    data["updated"] = _utc_now_iso()
    os.makedirs(bindings_dir(repo_root), exist_ok=True)
    textio.write_text(_binding_file(repo_root, key), json.dumps(data, indent=2) + "\n", newline="\n")
    return data


def bind_session(repo_root: str, slug: str, key: Optional[str] = None,
                 approved: Optional[bool] = None) -> Optional[Dict[str, Any]]:
    """Bind the agent session `key` (default: this process's session) to `slug`.

    A plan approval recorded before any slug was bound (ExitPlanMode at the start of a
    session) carries over to the first slug; binding a different slug later drops it.
    Returns the binding, or None when the session id is unknown.
    """
    key = key or current_session_key()
    if not key:
        return None
    binding = load_binding(repo_root, key) or {"created": _utc_now_iso()}
    pending = binding.get("plan_approved") and not binding.get("approved_slug")
    if approved is not None:
        binding["plan_approved"] = bool(approved)
        binding["approved_slug"] = slug if approved else None
    elif pending:
        binding["approved_slug"] = slug
    elif binding.get("approved_slug") != slug:
        binding["plan_approved"] = False
        binding["approved_slug"] = None
    binding["slug"] = slug
    rel_ctx = os.path.relpath(os.path.abspath(repo_root), binding_root(repo_root))
    binding["context"] = repo.normalize_posix(rel_ctx)
    return save_binding(repo_root, key, binding)


def record_plan_approval(repo_root: str, key: Optional[str]) -> Optional[Dict[str, Any]]:
    """The user approved a plan in session `key`: approve its bound slug, or the next one."""
    if not key:
        return None
    binding = load_binding(repo_root, key) or {"created": _utc_now_iso()}
    slug = binding.get("slug")
    binding["plan_approved"] = True
    binding["approved_slug"] = slug
    binding["approved_at"] = _utc_now_iso()
    saved = save_binding(repo_root, key, binding)
    ctx = binding_context(repo_root, binding) if slug else None
    if slug and ctx and load_state(ctx, slug):
        update_state(ctx, slug, phase="execution", plan_approved=True)
    return saved


def unbind_slug(repo_root: str, slug: str) -> int:
    """Remove every binding that points at `slug`. Returns how many were removed."""
    removed = 0
    bdir = bindings_dir(repo_root)
    if not os.path.isdir(bdir):
        return 0
    for entry in os.scandir(bdir):
        if not entry.name.endswith(".json"):
            continue
        data = load_binding(repo_root, entry.name[:-5])
        ctx = binding_context(repo_root, data)
        if data and data.get("slug") == slug and (not ctx or _same_dir(ctx, repo_root)):
            try:
                os.remove(entry.path)
                removed += 1
            except OSError:
                pass
    return removed


def list_bindings(repo_root: str) -> List[Dict[str, Any]]:
    bdir = bindings_dir(repo_root)
    out: List[Dict[str, Any]] = []
    if not os.path.isdir(bdir):
        return out
    for entry in sorted(os.scandir(bdir), key=lambda e: e.name):
        if entry.name.endswith(".json"):
            data = load_binding(repo_root, entry.name[:-5])
            if data:
                out.append(data)
    return out


def gc_bindings(repo_root: str, max_age_hours: int = BINDING_MAX_AGE_HOURS,
                now: Optional[datetime] = None, dry_run: bool = False) -> List[str]:
    """Remove bindings older than `max_age_hours` or bound to a slug with no blackboard."""
    now = now or datetime.now(timezone.utc)
    stale: List[str] = []
    for data in list_bindings(repo_root):
        key = str(data.get("key", ""))
        updated = str(data.get("updated", ""))
        try:
            age_h = (now - datetime.strptime(updated, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc)).total_seconds() / 3600
        except ValueError:
            age_h = max_age_hours + 1
        slug = data.get("slug")
        ctx = binding_context(repo_root, data) or repo_root
        orphan = bool(slug) and not os.path.isdir(get_session_dir(ctx, str(slug)))
        if age_h > max_age_hours or orphan:
            stale.append(key)
            if not dry_run:
                try:
                    os.remove(_binding_file(repo_root, key))
                except OSError:
                    pass
    return stale


def in_progress_slugs(repo_root: str) -> List[str]:
    """Slugs of blackboards with status in-progress, sorted."""
    s_root = os.path.join(repo.state_dir(repo_root), ".session")
    found: List[str] = []
    if os.path.isdir(s_root):
        try:
            for entry in os.scandir(s_root):
                if entry.is_dir() and not entry.name.startswith(".") and entry.name != BINDINGS_DIRNAME:
                    st = load_state(repo_root, entry.name)
                    if st and st.get("status") == "in-progress":
                        found.append(entry.name)
        except (OSError, UnicodeDecodeError):
            pass
    return sorted(found)


def resolve_active_session(repo_root: str, key: Optional[str] = None) -> Tuple[Optional[str], str]:
    """(slug, how) for the agent session `key` (default: this process's session).

    how is 'env' (ALONG_ISSUE_SLUG from a runner), 'binding', 'elsewhere' (the session is
    bound to an issue of another `.along/` context; slug is None here), 'single' (no binding,
    exactly one in-progress blackboard), 'ambiguous' (no binding, several) or 'none'.
    """
    env_slug = (os.environ.get("ALONG_ISSUE_SLUG") or "").strip()
    if env_slug:
        return env_slug, "env"
    key = key or current_session_key()
    binding = load_binding(repo_root, key)
    if binding and binding.get("slug"):
        ctx = binding_context(repo_root, binding)
        if ctx and not _same_dir(ctx, repo_root):
            return None, "elsewhere"
        return str(binding["slug"]), "binding"
    candidates = in_progress_slugs(repo_root)
    if key:
        # A slug another session is bound to is that session's work, not ours.
        taken = {str(b.get("slug")) for b in list_bindings(repo_root) if b.get("key") != key}
        candidates = [c for c in candidates if c not in taken]
    if len(candidates) == 1:
        return candidates[0], "single"
    if len(candidates) > 1:
        return None, "ambiguous"
    return None, "none"


def resolve_bound(repo_root: str, key: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """(context_root, slug) of the session's issue, following a binding into another context."""
    key = key or current_session_key()
    slug, how = resolve_active_session(repo_root, key)
    if how == "elsewhere":
        binding = load_binding(repo_root, key) or {}
        return binding_context(repo_root, binding) or repo_root, binding.get("slug")
    return repo_root, slug


def get_active_session_slug(repo_root: str, key: Optional[str] = None) -> Optional[str]:
    """Slug the agent session `key` works on, or None when unbound and not unique."""
    return resolve_active_session(repo_root, key)[0]


def get_session_phase(repo_root: str, slug: Optional[str] = None, key: Optional[str] = None) -> str:
    """Current phase ('inquiry', 'planning', 'execution') of the session's slug."""
    key = key or current_session_key()
    effective_slug = slug or get_active_session_slug(repo_root, key)
    state_root = repo_root
    if not effective_slug:
        # Bound to an issue of another .along/ context: its blackboard holds the phase.
        binding = load_binding(repo_root, key)
        if binding and binding.get("slug"):
            effective_slug = str(binding["slug"])
            state_root = binding_context(repo_root, binding) or repo_root
    if effective_slug:
        st = load_state(state_root, effective_slug)
        if st and "phase" in st:
            return str(st["phase"])
    elif not key:
        # Runtimes that pass no session id keep the repository-level state.
        gst = load_global_session_state(repo_root)
        if gst and "phase" in gst:
            return str(gst["phase"])
    return DEFAULT_PHASE


def is_plan_approved(repo_root: str, slug: Optional[str] = None, key: Optional[str] = None) -> bool:
    """True when the plan for the session's slug was approved.

    The binding of session `key` counts (an approval recorded for this slug, e.g. from
    ExitPlanMode), as does `plan_approved` in the slug's own blackboard.
    """
    key = key or current_session_key()
    effective_slug = slug or get_active_session_slug(repo_root, key)
    binding = load_binding(repo_root, key)
    if binding and binding.get("plan_approved"):
        # Approval belongs to the session and the slug it is bound to, in any context.
        approved_slug = binding.get("approved_slug")
        if approved_slug is None or approved_slug == (binding.get("slug") or effective_slug):
            return True
    if effective_slug:
        st = load_state(repo_root, effective_slug)
        if st:
            return bool(st.get("plan_approved", False))
    elif not key:
        gst = load_global_session_state(repo_root)
        if gst:
            return bool(gst.get("plan_approved", False))
    return False


def set_session_phase(
    repo_root: str,
    phase: str,
    slug: Optional[str] = None,
    plan_approved: Optional[bool] = None,
) -> Dict[str, Any]:
    """Set session phase ('inquiry', 'planning', 'execution') and optional approval."""
    if phase not in SESSION_PHASES:
        raise ValueError(f"Invalid session phase '{phase}'. Allowed: {', '.join(SESSION_PHASES)}")

    key = current_session_key()
    effective_slug = slug or get_active_session_slug(repo_root, key)
    now = _utc_now_iso()

    if effective_slug:
        st = load_state(repo_root, effective_slug) or init_session(repo_root, effective_slug)
        st["phase"] = phase
        if plan_approved is not None:
            st["plan_approved"] = plan_approved
        save_state(repo_root, effective_slug, st)
        # Only this session's binding learns about the approval, never a repo-wide pointer.
        if key and plan_approved is not None:
            bind_session(repo_root, effective_slug, key=key, approved=plan_approved)
        return st
    elif key:
        if plan_approved:
            return record_plan_approval(repo_root, key) or {}
        binding = load_binding(repo_root, key) or {"created": now}
        if plan_approved is False:
            binding["plan_approved"] = False
            binding["approved_slug"] = None
        return save_binding(repo_root, key, binding)
    else:
        gst = load_global_session_state(repo_root) or {
            "phase": DEFAULT_PHASE,
            "plan_approved": False,
            "created": now,
        }
        gst["phase"] = phase
        if plan_approved is not None:
            gst["plan_approved"] = plan_approved
        save_global_session_state(repo_root, gst)
        return gst


def approve_plan(repo_root: str, slug: Optional[str] = None) -> Dict[str, Any]:
    """Grant plan approval and transition phase to 'execution'."""
    return set_session_phase(repo_root, phase="execution", slug=slug, plan_approved=True)



# ---------------------------------------------------------------------------
# along-team step discipline [feat--along-team-step-enforcement]
# ---------------------------------------------------------------------------

#: 'role-based' blackboards (along-team, `along scratch init`) are held to the step loop;
#: 'direct' ones (`along start`, or a recorded single-agent fallback) are not.
EXECUTION_MODES: Tuple[str, ...] = ("direct", "role-based")
TRACE_FILENAME: str = "execution_trace.md"


def is_role_based(state: Optional[Dict[str, Any]]) -> bool:
    return bool(state) and state.get("execution_mode") == "role-based"


def review_file(repo_root: str, slug: str, step: int) -> str:
    return os.path.join(get_session_dir(repo_root, slug), "reviews", f"step-{step}.md")


def append_trace(repo_root: str, slug: str, line: str) -> str:
    """Append a timestamped line to the blackboard's execution_trace.md."""
    path = os.path.join(get_session_dir(repo_root, slug), TRACE_FILENAME)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    existing = textio.read_text(path, strict=False) if os.path.isfile(path) else f"# Execution Trace: {slug}\n\n"
    textio.write_text(path, existing.rstrip("\n") + f"\n- {_utc_now_iso()} {line}\n", newline="\n")
    return path


def missing_reviews(repo_root: str, slug: str) -> List[int]:
    """Passed steps of a role-based blackboard that lack reviews/step-N.md."""
    st = load_state(repo_root, slug)
    if not is_role_based(st):
        return []
    return [int(s.get("step", 0)) for s in st.get("steps", [])
            if s.get("status") == "passed" and not os.path.isfile(review_file(repo_root, slug, int(s.get("step", 0))))]


def completion_problems(repo_root: str, slug: str) -> List[str]:
    """Why a role-based blackboard may not be purged yet (empty when it may)."""
    st = load_state(repo_root, slug)
    if not is_role_based(st):
        return []
    problems = [f"step {s.get('step')} '{s.get('title')}' is {s.get('status')}"
                for s in st.get("steps", []) if s.get("status") != "passed"]
    problems += [f"step {n} passed without reviews/step-{n}.md" for n in missing_reviews(repo_root, slug)]
    return problems


def render_blackboard_markdown(repo_root: str, slug: str) -> str:
    """The blackboard as a session-log section (plan, steps, reviews, trace), or ''.

    `along wrap` writes it into the session log before the purge deletes the blackboard.
    See [feat--wrap-session-log-from-blackboard].
    """
    sdir = get_session_dir(repo_root, slug)
    st = load_state(repo_root, slug)
    if not st or not os.path.isdir(sdir):
        return ""

    def _read(name: str) -> str:
        path = os.path.join(sdir, name)
        return textio.read_text(path, strict=False).strip() if os.path.isfile(path) else ""

    def _demote(text: str) -> str:
        # Nest the file's own headings under the section's level-3 headings (not inside fences).
        lines, in_fence = [], False
        for line in text.splitlines():
            if line.lstrip().startswith(("```", "~~~")):
                in_fence = not in_fence
            lines.append("###" + line if line.startswith("#") and not in_fence else line)
        return "\n".join(lines)

    out = [f"## Blackboard Record\n",
           f"Execution mode: {st.get('execution_mode', 'direct')}; plan revision "
           f"{st.get('plan_revision', 1)}; approved: {str(bool(st.get('plan_approved'))).lower()}.\n"]
    steps = st.get("steps", [])
    if steps:
        out.append("| Step | Title | Status | Retries | Review |")
        out.append("| --- | --- | --- | --- | --- |")
        for s in steps:
            n = int(s.get("step", 0))
            has_review = "yes" if os.path.isfile(review_file(repo_root, slug, n)) else "no"
            out.append(f"| {n} | {s.get('title', '')} | {s.get('status', '')} | {s.get('retries', 0)} | {has_review} |")
        out.append("")
    for title, name in (("Plan", "plan.md"), ("Research", "research.md"), ("Execution Trace", TRACE_FILENAME)):
        text = _read(name)
        if text:
            out.append(f"### {title}\n\n{_demote(text)}\n")
    rdir = os.path.join(sdir, "reviews")
    if os.path.isdir(rdir):
        for name in sorted(os.listdir(rdir)):
            text = _read(os.path.join("reviews", name))
            if name.endswith(".md") and text:
                out.append(f"### Review {name[:-3]}\n\n{_demote(text)}\n")
    return "\n".join(out).rstrip() + "\n"


def record_fallback(repo_root: str, slug: str, reason: str) -> Dict[str, Any]:
    """Switch a blackboard to single-agent execution, keeping the reason in the trace."""
    st = load_state(repo_root, slug) or init_session(repo_root, slug)
    st["execution_mode"] = "direct"
    save_state(repo_root, slug, st)
    append_trace(repo_root, slug, f"Single-agent fallback: {reason}")
    return st


def init_session(
    repo_root: str,
    slug: str,
    title: Optional[str] = None,
    total_steps: Optional[int] = None,
    step_titles: Optional[List[str]] = None,
    retry_limit: int = DEFAULT_RETRY_LIMIT,
    force_restart: bool = False,
    execution_mode: str = "direct",
) -> Dict[str, Any]:
    """Initialize or load session blackboard with plan.md, research.md, reviews/, and state.json."""
    session_dir = get_session_dir(repo_root, slug)
    reviews_dir = os.path.join(session_dir, "reviews")
    os.makedirs(reviews_dir, exist_ok=True)

    if execution_mode not in EXECUTION_MODES:
        raise ValueError(f"Invalid execution mode '{execution_mode}'. Allowed: {', '.join(EXECUTION_MODES)}")
    existing_state = load_state(repo_root, slug)
    if existing_state and not force_restart:
        if execution_mode == "role-based" and existing_state.get("execution_mode") != "role-based":
            existing_state["execution_mode"] = "role-based"
            save_state(repo_root, slug, existing_state)
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
        "execution_mode": execution_mode,
        "phase": DEFAULT_PHASE,
        "plan_approved": False,
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
    phase: Optional[str] = None,
    plan_approved: Optional[bool] = None,
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

    if phase:
        if phase not in SESSION_PHASES:
            raise ValueError(f"Invalid session phase '{phase}'. Allowed: {', '.join(SESSION_PHASES)}")
        state["phase"] = phase

    if plan_approved is not None:
        state["plan_approved"] = bool(plan_approved)

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
    # No repository-wide pointer: parallel sessions read their own bindings
    # [bug--session-state-cross-session-leak].
    return state, retry_exhausted


def purge_session(repo_root: str, slug: str) -> bool:
    """Remove ephemeral session blackboard directory and every binding to `slug`.

    True if the blackboard was purged, False if it did not exist.
    """
    unbind_slug(repo_root, slug)
    gst = load_global_session_state(repo_root)
    if gst and gst.get("active_slug") == slug:
        try:
            os.remove(get_global_session_file(repo_root))
        except OSError:
            pass
    session_dir = get_session_dir(repo_root, slug)
    if os.path.exists(session_dir):
        shutil.rmtree(session_dir)
        return True
    return False


def format_state_summary(state: Dict[str, Any]) -> str:
    """Format a clean ASCII summary of the session state."""
    slug = state.get("slug", "unknown")
    status = state.get("status", "unknown")
    phase = state.get("phase", DEFAULT_PHASE)
    approved = state.get("plan_approved", False)
    title = state.get("title", slug)
    curr = state.get("current_step", 1)
    total = state.get("total_steps", 1)
    rev = state.get("plan_revision", 1)
    limit = state.get("retry_limit", DEFAULT_RETRY_LIMIT)

    lines = [
        f"Session:  {slug} (status: {status})",
        f"Title:    {title}",
        f"Phase:    {phase} (plan_approved: {approved})",
        f"Step:     {curr} of {total} (Plan Rev {rev}, Retry Limit: {limit})",
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


