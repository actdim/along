#!/usr/bin/env python3
"""
alongkit.hooks.predicates - Stateful predicate handlers for declarative gates.

Implements complex condition checks requiring filesystem inspection, Git queries,
or session-level activity tracking.
"""

from __future__ import annotations

from datetime import datetime, timezone
import fnmatch
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .. import frontmatter, repo, sanitizer, textio, typography
from .models import HookEvent, HookEventType


GOVERNED_TYPOGRAPHY_SUFFIXES: Tuple[str, ...] = (
    ".md", ".py", ".ts", ".js", ".tsx", ".jsx",
    ".sh", ".ps1", ".bat", ".rs", ".go", ".txt",
)

PROTECTED_PROJECTIONS: Tuple[str, ...] = (
    ".along/issues.md",
    "docs/index.md",
)

DANGEROUS_CLI_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"<<\s*['\"]?EOF['\"]?", re.IGNORECASE), "Heredoc syntax (<<EOF)"),
    (re.compile(r"python\d*\s+-c\s+.*open\(.*['\"][wa]['\"].*\)", re.DOTALL), "Inline Python file writer"),
    (re.compile(r"git\s+reset\s+--hard", re.IGNORECASE), "Destructive unstaged Git wipe (git reset --hard)"),
    (re.compile(r"git\s+clean\s+-[a-zA-Z]*f", re.IGNORECASE), "Destructive Git clean (git clean -f)"),
    (re.compile(r"npm\s+install\s+(-g|--global)", re.IGNORECASE), "Global package manager mutation (npm -g)"),
    (re.compile(r"(choco|winget)\s+install", re.IGNORECASE), "Global system package installation"),
]

TEST_COMMAND_PATTERNS: List[re.Pattern] = [
    re.compile(r"along[-_]test", re.IGNORECASE),
    re.compile(r"\.along[/\\]scripts[/\\]test\.py", re.IGNORECASE),
    re.compile(r"\bpytest\b", re.IGNORECASE),
    re.compile(r"\bnpm\s+test\b", re.IGNORECASE),
    re.compile(r"\bcargo\s+test\b", re.IGNORECASE),
    re.compile(r"\bdotnet\s+test\b", re.IGNORECASE),
    re.compile(r"unittest\s+discover", re.IGNORECASE),
]


def _extract_target_file(event: HookEvent) -> str:
    args = event.tool_args
    return (
        args.get("TargetFile")
        or args.get("target_file")
        or args.get("path")
        or args.get("FilePath")
        or args.get("file_path")
        or ""
    )


def _extract_content(event: HookEvent) -> str:
    tool = event.tool_name
    args = event.tool_args
    if tool in ("write_to_file", "write_file", "create_file"):
        return args.get("CodeContent") or args.get("content") or ""
    elif tool in ("replace_file_content", "edit_file", "patch_file"):
        return args.get("ReplacementContent") or args.get("replacement_content") or args.get("content") or ""
    return ""


def _extract_command(event: HookEvent) -> str:
    args = event.tool_args
    return args.get("CommandLine") or args.get("command") or args.get("cmd") or ""


def _matches_pattern(path: str, patterns: List[str]) -> bool:
    norm = repo.normalize_posix(path).lstrip("/")
    for pat in patterns:
        pat_norm = repo.normalize_posix(pat).lstrip("/")
        if fnmatch.fnmatch(norm, pat_norm):
            return True
        if pat_norm.endswith("/**") and (norm.startswith(pat_norm[:-3]) or norm == pat_norm[:-3]):
            return True
    return False


# ---------------------------------------------------------------------------
# Activity Trace Tracker (Session-level state)
# ---------------------------------------------------------------------------

def _issues_dir(repo_root: str) -> str:
    return os.path.join(repo.state_dir(repo_root), "ISSUES")


def get_activity_trace_path(repo_root: str) -> str:
    return os.path.join(repo.state_dir(repo_root), "diagnostics", "activity_trace.json")


def load_activity_trace(repo_root: str) -> Dict[str, Any]:
    trace_path = get_activity_trace_path(repo_root)
    if not os.path.isfile(trace_path):
        return {"last_edit_time": None, "last_test_time": None, "edited_files": []}
    try:
        raw = textio.read_text(trace_path, strict=False)
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    return {"last_edit_time": None, "last_test_time": None, "edited_files": []}


def save_activity_trace(repo_root: str, data: Dict[str, Any]) -> None:
    trace_path = get_activity_trace_path(repo_root)
    os.makedirs(os.path.dirname(trace_path), exist_ok=True)
    try:
        textio.write_text(trace_path, json.dumps(data, indent=2) + "\n")
    except (OSError, UnicodeDecodeError):
        pass


def record_tool_activity(event: HookEvent, repo_root: str) -> None:
    """Record file modifications and test runs to track lifecycle state."""
    if not repo_root:
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    trace = load_activity_trace(repo_root)

    # Track file edits
    if event.tool_name in ("write_to_file", "write_file", "replace_file_content", "edit_file", "patch_file", "create_file"):
        target = _extract_target_file(event)
        norm_target = repo.normalize_posix(target).lower() if target else ""
        # Only consider project source files (skip session blackboard and diagnostics)
        if norm_target and not norm_target.startswith(".along/.session") and not norm_target.startswith(".along/diagnostics"):
            trace["last_edit_time"] = now_iso
            edited = trace.get("edited_files", [])
            if target not in edited:
                edited.append(target)
            trace["edited_files"] = edited
            save_activity_trace(repo_root, trace)

    # Track test executions
    elif event.tool_name in ("run_command", "execute_command", "bash", "shell"):
        cmd = _extract_command(event)
        if cmd and any(p.search(cmd) for p in TEST_COMMAND_PATTERNS):
            trace["last_test_time"] = now_iso
            save_activity_trace(repo_root, trace)


# ---------------------------------------------------------------------------
# Predicate Handlers
# ---------------------------------------------------------------------------

def check_typography(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Validate content against forbidden non-ASCII typography."""
    content = _extract_content(event)
    if not content:
        return None

    target_file = _extract_target_file(event)
    if target_file:
        norm_path = repo.normalize_posix(target_file)
        segments = norm_path.split("/")
        if any(seg in sanitizer.LOCALIZED_DIRS for seg in segments):
            return None

        _, ext = os.path.splitext(norm_path)
        if ext and ext.lower() not in GOVERNED_TYPOGRAPHY_SUFFIXES:
            return None

    hits = typography.findings(content)
    if not hits:
        return None

    counts: Dict[str, int] = {}
    lines: List[int] = []
    for line_num, _col, char in hits:
        cname = typography.name_of(char)
        counts[cname] = counts.get(cname, 0) + 1
        if line_num not in lines:
            lines.append(line_num)

    detail = ", ".join(f"{c} {name}" for name, c in sorted(counts.items()))
    line_str = ", ".join(str(n) for n in lines[:6])
    if len(lines) > 6:
        line_str += ", ..."

    target_label = f" in '{target_file}'" if target_file else ""
    return (
        f"Typography Gate Violation: Detected forbidden non-ASCII typography{target_label}: "
        f"{detail} (lines: {line_str}). "
        f"Replace with standard ASCII equivalents ('-', '\"', ''', '...') before writing."
    )


def check_projection_protection(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Disallow manual edits to compiled views (.along/ISSUES.md, docs/INDEX.md)."""
    target = _extract_target_file(event)
    if not target:
        return None

    norm_path = repo.normalize_posix(target).lower()
    is_protected = any(
        norm_path == p or norm_path.endswith("/" + p)
        for p in PROTECTED_PROJECTIONS
    )

    if is_protected:
        return (
            f"Projection Protection Violation: Direct manual edits to '{target}' are forbidden. "
            "The Single Source of Truth (SSOT) is atomic files in '.along/ISSUES/' or 'docs/'. "
            "Modify atomic files and run 'along issue sync' or 'along kb sync' to recompile."
        )
    return None


def check_cli_safety(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Check command line for dangerous shell patterns and destructive commands."""
    cmd = _extract_command(event)
    if not cmd:
        return None

    for pattern, label in DANGEROUS_CLI_PATTERNS:
        if pattern.search(cmd):
            return (
                f"CLI Safety Gate Violation: {label} detected in command: {cmd.strip()[:100]}. "
                "Use native file editing tools and Along lifecycle scripts instead."
            )
    return None


def check_active_issue(event: HookEvent, repo_root: str, exclude_paths: Optional[List[str]] = None, **kwargs: Any) -> Optional[str]:
    """Enforce that code modifications occur under an in-progress issue."""
    target = _extract_target_file(event)
    if not target or not repo_root:
        return None

    excludes = exclude_paths or [
        ".along/ISSUES/**",
        ".along/.session/**",
        ".along/diagnostics/**",
        ".along/SESSIONS/**",
        ".along/DECISIONS/**",
        ".along/HISTORY.md",
        "docs/**",
        "CHANGELOG.md",
    ]

    if os.path.isabs(target):
        try:
            rel_target = os.path.relpath(target, repo_root)
            if rel_target.startswith("..") or os.path.isabs(rel_target):
                # Outside repository root (e.g. brain artifacts, temp files)
                return None
        except ValueError:
            # Different drive on Windows: target is outside repository root
            return None
    else:
        rel_target = target

    if _matches_pattern(rel_target, excludes):
        return None

    issues_dir = _issues_dir(repo_root)
    if not os.path.isdir(issues_dir):
        return None

    # Check if any issue directly in ISSUES/ has status: in-progress
    has_active = False
    try:
        for entry in os.scandir(issues_dir):
            if entry.is_file() and entry.name.endswith(".md"):
                content = textio.read_text(entry.path, strict=False)
                mapping, _body, _err = frontmatter.try_parse(content)
                if mapping and mapping.get("status") == "in-progress":
                    has_active = True
                    break
    except (OSError, UnicodeDecodeError, ValueError):
        pass

    if not has_active:
        return (
            f"Mandatory Issue Anchoring Violation [gate: require-active-issue]: "
            f"Cannot modify repository file '{rel_target}' without an active in-progress issue. "
            f"Identify or create an issue in .along/ISSUES/ with 'status: in-progress' before writing code."
        )
    return None


def check_test_before_stop(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Ensure automated tests were run after code modifications before stopping turn."""
    if not repo_root:
        return None

    trace = load_activity_trace(repo_root)
    edit_time = trace.get("last_edit_time")
    test_time = trace.get("last_test_time")

    if edit_time is not None:
        if test_time is None or test_time < edit_time:
            return (
                "Turn Completion Rejected [gate: test-before-stop]: Source files were modified during this turn, "
                "but automated tests have not been executed afterward. "
                "Run tests via '/along-test' or 'python .along/scripts/test.py' before completing."
            )
    return None


def check_wrap_before_stop(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Ensure session log is recorded if an issue was marked done."""
    if not repo_root:
        return None

    done_dir = os.path.join(_issues_dir(repo_root), "done")
    if not os.path.isdir(done_dir):
        return None

    today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    recent_done = False
    try:
        for entry in os.scandir(done_dir):
            if entry.is_file() and entry.name.endswith(".md"):
                content = textio.read_text(entry.path, strict=False)
                parsed, _body, _err = frontmatter.try_parse(content)
                if parsed:
                    completed = str(parsed.get("completed", ""))
                    if completed.startswith(today_prefix):
                        recent_done = True
                        break
    except (OSError, UnicodeDecodeError, ValueError):
        pass

    if recent_done:
        # Verify a session log exists for today
        sessions_dir = os.path.join(repo.state_dir(repo_root), "SESSIONS")
        has_session_today = False
        if os.path.isdir(sessions_dir):
            for root, _dirs, files in os.walk(sessions_dir):
                for f in files:
                    if f.startswith(today_prefix) and f.endswith(".md"):
                        has_session_today = True
                        break
                if has_session_today:
                    break

        if not has_session_today:
            return (
                f"Turn Completion Rejected [gate: wrap-before-stop]: Issue completed today ({today_prefix}), "
                "but no matching session log was found in .along/SESSIONS/. "
                "Execute '/along-wrap' or write the session log before ending."
            )
    return None


def check_projection_sync_before_stop(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Ensure projections (ISSUES.md, docs/INDEX.md) are updated when atomic sources change."""
    if not repo_root:
        return None

    issues_proj = os.path.join(repo.state_dir(repo_root), "ISSUES.md")
    issues_dir = _issues_dir(repo_root)

    if os.path.isfile(issues_proj) and os.path.isdir(issues_dir):
        proj_mtime = os.path.getmtime(issues_proj)
        for root, _dirs, files in os.walk(issues_dir):
            for f in files:
                if f.endswith(".md"):
                    p = os.path.join(root, f)
                    if os.path.getmtime(p) > proj_mtime + 2.0:  # Allow 2s tolerance
                        return (
                            "Turn Completion Rejected [gate: projection-sync-before-stop]: "
                            "Atomic issues were modified after the latest .along/ISSUES.md projection. "
                            "Run 'along issue sync' to recompile before ending."
                        )

    return None


def check_subproject_boundary(event: HookEvent, repo_root: str, **kwargs: Any) -> Optional[str]:
    """Enforce subproject localization: entities must be in nearest .along/."""
    target = _extract_target_file(event)
    if not target or not repo_root:
        return None

    if os.path.isabs(target):
        try:
            rel = os.path.relpath(target, repo_root)
            if rel.startswith(".."):
                return None
            rel_path = repo.normalize_posix(rel)
        except ValueError:
            return None
    else:
        rel_path = repo.normalize_posix(target)

    # If writing directly to root .along/ but the path indicates working inside a subproject
    if rel_path.startswith(".along/"):
        cwd = repo.normalize_posix(os.getcwd())
        root_norm = repo.normalize_posix(repo_root)
        if cwd != root_norm and cwd.startswith(root_norm + "/"):
            subpath = cwd[len(root_norm) + 1:]
            # Check if subproject has manifest
            sub_along = os.path.join(cwd, ".along")
            sub_pkg = os.path.join(cwd, "package.json")
            if os.path.isdir(sub_along) or os.path.isfile(sub_pkg):
                return (
                    f"Subproject Boundary Violation [gate: subproject-boundary]: "
                    f"Cannot write to root '{rel_path}' while working inside subproject '{subpath}'. "
                    f"Entities must be created in nearest '{subpath}/.along/'."
                )
    return None
