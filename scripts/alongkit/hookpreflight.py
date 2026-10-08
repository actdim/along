#!/usr/bin/env python3
"""
alongkit.hookpreflight - Decisions a runtime hook makes before loading its dependencies.

A runtime hook fires on every matched tool use. Two answers need nothing beyond the standard
library, so `along_hook.py` takes them before `bootstrap.ensure_deps()` (which may re-execute
the process under the cached runtime environment):

1. No Along context applies (no real `.along/`, no declared root): allow. A bare `AGENTS.md`
   is a tool-agnostic convention and does not make a repository Along-managed.
2. A read or search tool targets a path inside the Along root, outside `docs/` and the state
   directory (which fast-retrieval governs): allow. Reads outside the root still go through
   the full pipeline, where workspace containment decides.

Everything else returns None and the full gate pipeline runs.
See [bug--hook-activation-and-gate-deadlock].
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
from typing import Any, Dict, Optional, Tuple

from . import repo

#: Read and search tools, by the names the runtimes send (before adapter mapping).
READ_TOOLS: frozenset = frozenset({
    "Read", "Grep", "Glob", "LS",
    "view_file", "read_file", "grep_search", "find_by_name", "list_dir", "list_directory",
})

#: Payload keys naming the session's current directory, across runtimes.
_CWD_KEYS = ("cwd", "workspace_root", "workspaceRoot", "workdir")

#: Tool argument keys naming the path a read or search targets.
_PATH_KEYS = ("file_path", "path", "notebook_path", "TargetFile", "SearchPath", "SearchDirectory",
              "AbsolutePath", "DirectoryPath")


def _parse(raw_input: str) -> Optional[Dict[str, Any]]:
    try:
        payload = json.loads((raw_input or "").lstrip(chr(0xFEFF)) or "{}")
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def payload_cwd(payload: Dict[str, Any]) -> str:
    for key in _CWD_KEYS:
        if payload.get(key):
            return str(payload[key])
    paths = payload.get("workspacePaths")
    if isinstance(paths, list) and paths:
        return str(paths[0])
    return ""


def _tool(payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    name = payload.get("tool_name")
    args = payload.get("tool_input")
    call = payload.get("toolCall")
    if not name and isinstance(call, dict):
        name, args = call.get("name"), call.get("args")
    return str(name or ""), args if isinstance(args, dict) else {}


#: Runtimes whose adapter allows with exit 0 and no output (`hooks.adapters.ADAPTERS`); any
#: other name falls back to the Antigravity adapter, which answers with JSON.
_SILENT_ALLOW_RUNTIMES = frozenset({
    "claude", "claudecode", "claude-code", "codex", "openaicodex", "openai-codex", "openai",
    "generic", "cli", "generic-cli", "generic_cli", "cursor", "opencode", "open-code",
})


def allow_response(runtime: str, event_name: str) -> Tuple[int, str]:
    """(exit code, stdout) that allows the tool for `runtime`, as its adapter would format it."""
    if (runtime or "antigravity").strip().lower() in _SILENT_ALLOW_RUNTIMES:
        return 0, ""
    return 0, "{}" if event_name == "PostToolUse" else json.dumps({"decision": "allow"})


def _inside(path: str, root: str) -> bool:
    return repo.is_within(path, root)


def _is_or_above_home(path: str) -> bool:
    return _inside(os.path.expanduser("~"), path)


def is_workspace_read(payload: Dict[str, Any], root: str, cwd: str) -> bool:
    """True for a read/search tool whose target lies inside `root`, outside docs/ and the state dir."""
    name, args = _tool(payload)
    if name not in READ_TOOLS or _is_or_above_home(root):
        return False
    target = next((str(args[k]) for k in _PATH_KEYS if args.get(k)), "") or cwd or root
    if not os.path.isabs(target):
        target = os.path.join(cwd or root, target)
    if not _inside(target, root):
        return False
    governed = (os.path.join(root, "docs"), repo.state_dir(root))
    return not any(_inside(target, g) for g in governed)


def preflight(raw_input: str, runtime: str, event_name: str,
              repo_root: Optional[str] = None,
              project_dir: Optional[str] = None) -> Optional[Tuple[int, str]]:
    """(exit code, response) when the hook can answer without the gate pipeline, else None."""
    payload = _parse(raw_input)
    if payload is None:
        return None
    cwd = payload_cwd(payload)
    if repo_root:
        root: Optional[str] = repo_root if repo.context_state_dir(repo_root) else None
    else:
        root = repo.find_hook_root(cwd or os.getcwd(), project_dir)
    if not root:
        return allow_response(runtime, event_name)
    if event_name == "PreToolUse" and is_workspace_read(payload, root, cwd):
        return allow_response(runtime, event_name)
    return None
