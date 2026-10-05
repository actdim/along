#!/usr/bin/env python3
"""
alongkit.runtime - Which agent runtime is executing, and what it can enforce.

Along's mechanical gates run only where a runtime loads Along's PreToolUse/Stop hooks. In
any other runtime the protocol in AGENTS.md is advisory and the agent must apply it itself.
This module names the runtime, reports the resulting enforcement level, and detects the
environment hazards seen in Claude Cowork (a Linux VM with the user's folder mounted from the
host): a folder that forbids deletes, which leaves a stale `.git/index.lock` after any git
write, and a cross-OS mount on which git worktrees and symlinks break.

See [feat--cowork-runtime-support] and `docs/topic--runtime-hooks-and-gates.md`.
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

import json
import os
import sys
from typing import Any, Dict, List, Mapping, Optional, Tuple

#: Runtime capability matrix. `runtime_hooks` means Along's own installer can register
#: PreToolUse/Stop hooks for that runtime today.
RUNTIME_MATRIX: Dict[str, Dict[str, Any]] = {
    "claude-code": {"skills": "auto (~/.claude/skills)", "runtime_hooks": True},
    "antigravity": {"skills": "auto (~/.gemini)", "runtime_hooks": True},
    "codex": {"skills": "auto (~/.codex)", "runtime_hooks": True},
    "cowork": {"skills": "not loaded (account plugins only)", "runtime_hooks": False},
    "opencode": {"skills": "auto (~/.config/opencode)", "runtime_hooks": False},
    "cursor": {"skills": "rules only", "runtime_hooks": False},
    "unknown": {"skills": "unknown", "runtime_hooks": False},
}

MECHANICAL = "mechanical"
ADVISORY = "advisory"

#: Filesystem types that indicate a folder mounted from another OS or a VM host.
_CROSS_OS_FS_TYPES = ("9p", "drvfs", "virtiofs", "fuse", "fuse.sshfs", "vboxsf", "cifs", "smbfs")


def is_cowork_env(env: Optional[Mapping[str, str]] = None) -> bool:
    """Heuristic for the Claude Cowork VM (markers observed 2026-09-27).

    The VM sets `CLAUDE_CODE_HOST_HTTP_PROXY_PORT` and runs every session with a home under
    `/sessions/`. `ALONG_RUNTIME=cowork` forces the answer when the markers change.
    """
    env = os.environ if env is None else env
    if (env.get("ALONG_RUNTIME") or "").strip().lower() == "cowork":
        return True
    home = env.get("HOME") or ""
    return "CLAUDE_CODE_HOST_HTTP_PROXY_PORT" in env and home.startswith("/sessions/")


#: Hook events Along needs registered in Claude Code for mechanical enforcement.
CLAUDE_REQUIRED_EVENTS: Tuple[str, ...] = ("PreToolUse", "Stop")

#: Hook adapter runtime name for each `detect_agent` name, where they differ.
HOOK_RUNTIME_NAMES: Dict[str, str] = {"claude-code": "claude"}


def _claude_settings_files(repo_root: Optional[str]) -> List[str]:
    files = [os.path.join(os.path.expanduser("~"), ".claude", "settings.json")]
    if repo_root:
        files += [os.path.join(repo_root, ".claude", "settings.json"),
                  os.path.join(repo_root, ".claude", "settings.local.json")]
    return files


def claude_hook_status(repo_root: Optional[str] = None) -> Tuple[str, List[str]]:
    """('ok' | 'flat' | 'missing', files) for Along hooks in Claude Code settings.

    'ok' means every required event has an Along command in the nested schema Claude Code
    reads; 'flat' means Along entries exist only in the legacy `{matcher, command}` shape,
    which Claude Code ignores. See [bug--claude-runtime-not-detected].
    """
    from .hooks.config import is_along_hook_entry

    nested: set = set()
    flat_files: List[str] = []
    for path in _claude_settings_files(repo_root):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.loads(handle.read() or "{}")
        except (OSError, ValueError):
            continue
        hooks = data.get("hooks") if isinstance(data, dict) else None
        if not isinstance(hooks, dict):
            continue
        for event in CLAUDE_REQUIRED_EVENTS:
            for item in hooks.get(event) or []:
                if not is_along_hook_entry(item, event):
                    continue
                inner = item.get("hooks") if isinstance(item, dict) else None
                if isinstance(inner, list) and any(
                        isinstance(h, dict) and "along_hook.py" in str(h.get("command", "")) for h in inner):
                    nested.add(event)
                elif path not in flat_files:
                    flat_files.append(path)
    if all(e in nested for e in CLAUDE_REQUIRED_EVENTS):
        return "ok", []
    if flat_files:
        return "flat", flat_files
    return "missing", []


def heartbeat_path(repo_root: str) -> str:
    from . import repo
    return os.path.join(repo.diagnostics_dir(repo_root), "hook_heartbeat.json")


def record_heartbeat(repo_root: Optional[str], runtime: str, now_iso: str) -> None:
    """Remember when a hook of `runtime` last ran in this repository (best effort)."""
    if not repo_root or not runtime:
        return
    path = heartbeat_path(repo_root)
    data: Dict[str, Any] = {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            loaded = json.loads(handle.read() or "{}")
            if isinstance(loaded, dict):
                data = loaded
    except (OSError, ValueError):
        pass
    if data.get(runtime) == now_iso:
        return
    data[runtime] = now_iso
    try:
        from . import repo
        repo.ensure_diagnostics_dir(repo_root)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
    except OSError:
        pass


def last_heartbeat(repo_root: str, agent: str) -> Optional[str]:
    """ISO timestamp of the last hook run for the runtime `agent` names, or None."""
    name = HOOK_RUNTIME_NAMES.get(agent, agent)
    try:
        with open(heartbeat_path(repo_root), "r", encoding="utf-8") as handle:
            data = json.loads(handle.read() or "{}")
    except (OSError, ValueError):
        return None
    value = data.get(name) if isinstance(data, dict) else None
    return str(value) if value else None


def along_hooks_registered(runtime: str, repo_root: Optional[str] = None) -> bool:
    """True when Along's hook entry point is registered for `runtime` (user or project)."""
    if runtime == "claude-code":
        return claude_hook_status(repo_root)[0] == "ok"
    home = os.path.expanduser("~")
    candidates: List[str] = []
    if runtime == "codex":
        candidates = [os.path.join(home, ".codex", "hooks.json")]
    elif runtime == "antigravity":
        candidates = [os.path.join(home, ".gemini", "config", "hooks.json")]
        if repo_root:
            candidates.append(os.path.join(repo_root, ".agents", "hooks.json"))
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                if "along_hook" in handle.read():
                    return True
        except OSError:
            continue
    return False


def enforcement_level(runtime: str, repo_root: Optional[str] = None) -> Tuple[str, str]:
    """(level, explanation) for the runtime executing now."""
    caps = RUNTIME_MATRIX.get(runtime, RUNTIME_MATRIX["unknown"])
    if caps["runtime_hooks"] and along_hooks_registered(runtime, repo_root):
        return MECHANICAL, f"Along hooks are registered for {runtime}; gates block violations."
    if runtime == "claude-code":
        status, files = claude_hook_status(repo_root)
        if status == "flat":
            return ADVISORY, ("Along hooks for claude-code use the legacy flat schema, which Claude Code "
                              f"ignores ({', '.join(files)}). Run 'along hook install --runtime claude --global'.")
    if caps["runtime_hooks"]:
        return ADVISORY, f"{runtime} supports hooks, but Along hooks are not registered (run 'along hook install')."
    return ADVISORY, (f"{runtime} does not load Along hooks; the agent must self-apply the gates and use "
                      "the along CLI for tests, commits and entity changes. Git hooks and CI are the "
                      "portable enforcement baseline.")


def python_supported(version_info: Tuple[int, ...] = tuple(sys.version_info)) -> bool:
    return tuple(version_info[:2]) >= (3, 10)


def stale_index_lock(repo_root: str) -> bool:
    """True when `.git/index.lock` exists.

    Some sandboxes (the Cowork folder mount without delete permission) allow create and
    rename but not unlink, so git leaves this lock behind after any index write and every
    later git write fails. Doctor reports it instead of probing with a file of its own,
    because a probe that cannot be deleted would itself be left behind.
    """
    return os.path.exists(os.path.join(repo_root, ".git", "index.lock"))


def mount_fs_type(path: str, mounts_file: str = "/proc/mounts") -> Optional[str]:
    """Filesystem type of the mount containing `path` (Linux only), else None."""
    try:
        with open(mounts_file, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return None
    real = os.path.realpath(path)
    best: Tuple[int, Optional[str]] = (-1, None)
    for line in lines:
        parts = line.split()
        if len(parts) < 3:
            continue
        mount_point = parts[1].replace("\\040", " ")
        if real == mount_point or real.startswith(mount_point.rstrip("/") + "/"):
            if len(mount_point) > best[0]:
                best = (len(mount_point), parts[2])
    return best[1]


def is_cross_os_mount(repo_root: str, fs_type: Optional[str] = None,
                      core_symlinks: Optional[str] = None,
                      platform: str = sys.platform) -> bool:
    """A POSIX process working on a repository that lives on another OS's filesystem."""
    if platform == "win32":
        return False
    fs = fs_type if fs_type is not None else mount_fs_type(repo_root)
    if fs and any(fs == t or fs.startswith(t + ".") for t in _CROSS_OS_FS_TYPES):
        return True
    return (core_symlinks or "").strip().lower() == "false"


def runtime_report(repo_root: str, agent: str) -> Dict[str, Any]:
    """Facts `along doctor` prints for the current runtime."""
    level, why = enforcement_level(agent, repo_root)
    return {
        "runtime": agent,
        "enforcement": level,
        "explanation": why,
        "python": ".".join(str(p) for p in sys.version_info[:3]),
        "python_supported": python_supported(),
        "stale_index_lock": stale_index_lock(repo_root),
        "fs_type": mount_fs_type(repo_root),
    }


def format_matrix() -> str:
    """The capability matrix as JSON, for tooling."""
    return json.dumps(RUNTIME_MATRIX, indent=2, sort_keys=True)
