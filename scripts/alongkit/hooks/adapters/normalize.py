#!/usr/bin/env python3
"""
alongkit.hooks.adapters.normalize - Fail-closed tool-name normalization shared by all adapters.

Every gate in `default_gates.yaml` lists the canonical tool names it applies to. A runtime
tool name that an adapter does not map would otherwise fall through unchanged, match no
gate, and be allowed: Claude Code `MultiEdit` bypassed every write gate that way. The engine
therefore passes each event through `fail_closed()` before evaluating gates:

- a known canonical name is kept as is;
- an unknown name that looks like a mutation (by name, or because its arguments carry a
  file path together with new content) is treated as `replace_file_content`, so write gates
  apply;
- anything else stays unknown and is reported as `unmapped_tool` in
  `.along/diagnostics/hooks_audit.jsonl`, so coverage gaps are visible instead of silent.

See [bug--claude-adapter-unmapped-tools].
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any, Dict, FrozenSet, Tuple

from ..models import HookEvent

WRITE_TOOLS: Tuple[str, ...] = (
    "write_to_file", "write_file", "replace_file_content", "edit_file", "patch_file", "create_file",
)
SHELL_TOOLS: Tuple[str, ...] = ("run_command", "execute_command", "bash", "shell")
SEARCH_TOOLS: Tuple[str, ...] = ("grep_search", "grep", "find_by_name", "find_files", "file_search")
READ_TOOLS: Tuple[str, ...] = (
    "view_file", "read_file", "view_image", "list_dir", "list_directory", "read_url_content",
    "search_web", "manage_task", "schedule", "send_message", "ask_question", "call_mcp_tool",
    "list_resources", "read_resource",
)

#: Every canonical name some gate or safe-list refers to.
CANONICAL_TOOLS: FrozenSet[str] = frozenset(WRITE_TOOLS + SHELL_TOOLS + SEARCH_TOOLS + READ_TOOLS)

#: Marker the engine reads to audit a tool no adapter maps.
UNMAPPED_MARKER = "_along_unmapped_tool"
#: Marker recording the original runtime name of a tool inferred to be a write.
INFERRED_MARKER = "_along_inferred_from"

_MUTATION_NAME = re.compile(
    r"(?i)(write|edit|patch|create|replace|insert|append|delete|remove|move|rename|notebook)"
)
_PATH_KEYS: Tuple[str, ...] = (
    "file_path", "path", "notebook_path", "TargetFile", "target_file", "FilePath", "filename",
)
_CONTENT_KEYS: Tuple[str, ...] = (
    "content", "new_string", "new_source", "edits", "CodeContent", "ReplacementContent",
    "text", "patch", "diff",
)


def is_canonical(tool_name: str) -> bool:
    return tool_name in CANONICAL_TOOLS


def looks_like_mutation(tool_name: str, tool_args: Dict[str, Any]) -> bool:
    """A name that says it writes, or arguments that carry a path plus new content."""
    if _MUTATION_NAME.search(tool_name or ""):
        return True
    has_path = any(tool_args.get(k) for k in _PATH_KEYS)
    has_content = any(k in tool_args for k in _CONTENT_KEYS)
    return has_path and has_content


def fail_closed(event: HookEvent) -> HookEvent:
    """Return an event whose tool name every applicable gate recognizes."""
    name = event.tool_name or ""
    if not name or is_canonical(name):
        return event
    args = dict(event.tool_args or {})
    if looks_like_mutation(name, args):
        args[INFERRED_MARKER] = name
        return replace(event, tool_name="replace_file_content", tool_args=args)
    args[UNMAPPED_MARKER] = name
    return replace(event, tool_args=args)
