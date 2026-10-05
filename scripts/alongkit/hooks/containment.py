#!/usr/bin/env python3
"""
alongkit.hooks.containment - workspace containment policy for `[gate: workspace-containment]`.

Prose telling an agent to stay inside the repository decays over a long transcript; this
module decides deterministically whether a tool call's path is inside the allowed scope.

Scopes (every path is canonicalized with `os.path.realpath`, so `..` and symlinks cannot
escape, and compared case-insensitively where the filesystem is):

- write: the workspace root (or only its `write_scope` subfolders plus `.along/` when a
  write scope is declared), the system temp dir, the runtime's brain artifacts
  (`~/.gemini/antigravity/brain/<conversation-id>/`) and Claude Code project memory
  (`~/.claude/projects/`).
- read: everything writable, plus declared `allowed_roots`, the main checkout of a git
  worktree, and the global skill/config dirs (`~/.gemini`, `~/.claude`, `~/.codex`,
  `~/.along`), which are read-only.
- never: credential stores in the home directory (`~/.ssh`, `~/.aws`, ...), for reads too.

Configuration sources, merged: the gate entry in `.along/rules/gates.yaml`
(`allowed_roots`, `write_scope`, `on_violation`), the in-progress issue frontmatter
(`allowed_roots`, `write_scope`; written by `along start --allow-root/--write-scope`).
Relative entries resolve against the workspace root.

A write outside scope is always denied. A read outside scope asks in interactive mode and is
denied in autonomous mode (Claude Code `bypassPermissions`, `ALONG_AUTONOMOUS=1`, or
`on_violation: deny`).
"""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along hook verify   (or: python scripts/along_exec.py hook verify)"
    )

import os
import re
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .. import frontmatter, repo, session, textio
from .adapters.normalize import SEARCH_TOOLS, SHELL_TOOLS, WRITE_TOOLS
from .models import HookEvent

AUTONOMOUS_ENV = "ALONG_AUTONOMOUS"
#: Claude Code permission modes that run without asking the user.
AUTONOMOUS_PERMISSION_MODES: Tuple[str, ...] = ("bypassPermissions",)
VIOLATION_MODES: Tuple[str, ...] = ("auto", "ask", "deny")

#: Read tools whose path argument is checked (URL/MCP/messaging tools carry no path).
PATH_READ_TOOLS: Tuple[str, ...] = ("view_file", "read_file", "view_image", "list_dir", "list_directory")

#: Keys that name the path a tool touches, across runtimes.
PATH_ARG_KEYS: Tuple[str, ...] = (
    "TargetFile", "target_file", "file_path", "FilePath", "notebook_path", "path",
    "AbsolutePath", "DirectoryPath", "SearchDirectory", "SearchPath", "Directory", "filename",
)
CWD_ARG_KEYS: Tuple[str, ...] = ("Cwd", "cwd", "working_directory", "WorkingDirectory")

#: Home-relative global dirs readable by default (skills, rules, installed engines).
GLOBAL_READ_DIRS: Tuple[str, ...] = (".gemini", ".claude", ".codex", ".along")
#: Home-relative credential stores that are never readable.
SECRET_DIRS: Tuple[str, ...] = (
    ".ssh", ".aws", ".gnupg", ".azure", ".kube", ".docker", ".config/gcloud",
    ".netrc", ".git-credentials", ".npmrc", ".pypirc",
)
BRAIN_DIR = (".gemini", "antigravity", "brain")
CLAUDE_PROJECTS_DIR = (".claude", "projects")

_GLOB_CHARS = re.compile(r"[*?\[{]")


def canonical(path: str, base: Optional[str] = None) -> str:
    """Absolute, symlink-free, `..`-free path; relative paths resolve against `base`."""
    expanded = os.path.expanduser(str(path))
    if not os.path.isabs(expanded) and base:
        expanded = os.path.join(base, expanded)
    return os.path.normcase(os.path.realpath(expanded))


def is_within(path: str, root: str) -> bool:
    """True when canonical `path` equals or lies under canonical `root`."""
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:          # different drives on Windows
        return False


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if str(v).strip()]
    return []


@dataclass
class ContainmentPolicy:
    root: str                                   # canonical workspace root
    write_roots: List[str] = field(default_factory=list)
    read_roots: List[str] = field(default_factory=list)
    denied_roots: List[str] = field(default_factory=list)
    write_scope: List[str] = field(default_factory=list)   # empty: whole workspace
    on_violation: str = "auto"

    def can_write(self, path: str) -> bool:
        if any(is_within(path, d) for d in self.denied_roots):
            return False
        if is_within(path, self.root):
            if not self.write_scope:
                return True
            return any(is_within(path, s) for s in self.write_scope)
        return any(is_within(path, w) for w in self.write_roots)

    def can_read(self, path: str) -> bool:
        if any(is_within(path, d) for d in self.denied_roots):
            return False
        if is_within(path, self.root):
            return True
        return any(is_within(path, r) for r in self.write_roots + self.read_roots)

    def is_secret(self, path: str) -> bool:
        return any(is_within(path, d) for d in self.denied_roots)


def _worktree_main_checkout(root: str) -> Optional[str]:
    """In a git worktree `.git` is a file `gitdir: <main>/.git/worktrees/<name>`."""
    dot_git = os.path.join(root, ".git")
    if not os.path.isfile(dot_git):
        return None
    try:
        line = textio.read_text(dot_git, strict=False).strip()
    except (OSError, UnicodeDecodeError):
        return None
    if not line.startswith("gitdir:"):
        return None
    gitdir = canonical(line[len("gitdir:"):].strip(), root)
    parts = gitdir.split(os.sep)
    if "worktrees" in parts:
        idx = len(parts) - 1 - parts[::-1].index("worktrees")
        common = os.sep.join(parts[:idx])       # <main>/.git
        return os.path.dirname(common)
    return None


def issue_scope(repo_root: str, session_key: Optional[str] = None) -> Tuple[List[str], List[str]]:
    """(allowed_roots, write_scope) declared by the session's issue, else by in-progress issues."""
    issues_dir = os.path.join(repo.state_dir(repo_root), "ISSUES")
    if not os.path.isdir(issues_dir):
        return [], []
    active = session.get_active_session_slug(repo_root, session_key)
    roots: List[str] = []
    scope: List[str] = []
    try:
        entries = sorted(e for e in os.listdir(issues_dir) if e.endswith(".md"))
    except OSError:
        return [], []
    for name in entries:
        stem = name[:-3]
        if active and stem != active and stem.split("--", 1)[-1] != active:
            continue
        try:
            mapping, _body, _err = frontmatter.try_parse(
                textio.read_text(os.path.join(issues_dir, name), strict=False))
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        if not mapping or mapping.get("status") != "in-progress":
            continue
        roots += _as_list(mapping.get("allowed_roots"))
        scope += _as_list(mapping.get("write_scope"))
    return roots, scope


def build_policy(repo_root: str, options: Optional[Dict[str, Any]] = None,
                 conversation_id: Optional[str] = None, home: Optional[str] = None,
                 temp_dir: Optional[str] = None,
                 session_key: Optional[str] = None) -> ContainmentPolicy:
    """Policy from built-in defaults, gate options and the session's in-progress issue."""
    opts = options or {}
    root = canonical(repo_root)
    home_dir = home or os.path.expanduser("~")
    issue_roots, issue_write = issue_scope(repo_root, session_key)

    brain = os.path.join(home_dir, *BRAIN_DIR)
    if conversation_id:
        brain = os.path.join(brain, conversation_id)
    write_roots = [
        canonical(temp_dir or tempfile.gettempdir()),
        canonical(brain),
        canonical(os.path.join(home_dir, *CLAUDE_PROJECTS_DIR)),
    ]
    read_roots = [canonical(os.path.join(home_dir, d)) for d in GLOBAL_READ_DIRS]
    main = _worktree_main_checkout(root)
    if main:
        read_roots.append(canonical(main))
    read_roots += [canonical(p, root) for p in _as_list(opts.get("allowed_roots")) + issue_roots]

    declared_scope = _as_list(opts.get("write_scope")) + issue_write
    write_scope: List[str] = []
    if declared_scope:
        write_scope = [canonical(p, root) for p in declared_scope]
        write_scope.append(canonical(repo.state_dir(root)))

    mode = str(opts.get("on_violation", "auto")).strip().lower()
    return ContainmentPolicy(
        root=root,
        write_roots=write_roots,
        read_roots=read_roots,
        denied_roots=[canonical(os.path.join(home_dir, d)) for d in SECRET_DIRS],
        write_scope=write_scope,
        on_violation=mode if mode in VIOLATION_MODES else "auto",
    )


def is_autonomous(event: HookEvent, policy: ContainmentPolicy) -> bool:
    """Autonomous runs get DENY instead of ASK for out-of-scope reads."""
    if policy.on_violation == "deny":
        return True
    if policy.on_violation == "ask":
        return False
    if os.environ.get(AUTONOMOUS_ENV, "").strip().lower() in ("1", "true", "yes"):
        return True
    payload = event.raw_payload or {}
    return str(payload.get("permission_mode") or "") in AUTONOMOUS_PERMISSION_MODES


def _glob_base(pattern: str) -> Optional[str]:
    """Directory prefix of an absolute glob pattern (`C:/x/**/*.py` -> `C:/x`)."""
    expanded = os.path.expanduser(pattern)
    if not os.path.isabs(expanded):
        return None
    match = _GLOB_CHARS.search(expanded)
    prefix = expanded[:match.start()] if match else expanded
    return os.path.dirname(prefix) if match else prefix


def touched_paths(event: HookEvent) -> List[Tuple[str, str]]:
    """(access, raw path) pairs a tool call touches: access is `write`, `read` or `cwd`."""
    args = event.tool_args or {}
    tool = event.tool_name
    out: List[Tuple[str, str]] = []
    if tool in SHELL_TOOLS:
        for key in CWD_ARG_KEYS:
            if args.get(key):
                out.append(("cwd", str(args[key])))
                break
        return out
    if tool in WRITE_TOOLS:
        access = "write"
    elif tool in SEARCH_TOOLS or tool in PATH_READ_TOOLS:
        access = "read"
    else:
        return out
    seen = set()
    for key in PATH_ARG_KEYS:
        value = args.get(key)
        if isinstance(value, str) and value.strip() and value not in seen:
            seen.add(value)
            out.append((access, value))
    if tool in SEARCH_TOOLS:
        for key in ("pattern", "Pattern"):
            base = _glob_base(str(args.get(key) or ""))
            if base and base not in seen:
                out.append(("read", base))
    return out


def violations(event: HookEvent, policy: ContainmentPolicy, base: Optional[str] = None
               ) -> List[Tuple[str, str]]:
    """(access, canonical path) pairs outside the policy."""
    anchor = base or policy.root
    bad: List[Tuple[str, str]] = []
    for access, raw in touched_paths(event):
        path = canonical(raw, anchor)
        allowed = policy.can_write(path) if access == "write" else policy.can_read(path)
        if not allowed:
            bad.append((access, path))
    return bad


__all__: Sequence[str] = (
    "ContainmentPolicy", "build_policy", "canonical", "is_within", "is_autonomous",
    "issue_scope", "touched_paths", "violations", "AUTONOMOUS_ENV",
)
