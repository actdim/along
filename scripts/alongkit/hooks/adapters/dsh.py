#!/usr/bin/env python3
"""
alongkit.hooks.adapters.dsh - DeepSeek Harness (DSH) hook protocol adapter.

Translates DSH Claude Code bridge payloads (@deepseek-ai/dsh-hooks-claude-code)
and native DSH tool invocations to canonical HookEvent, ensuring proper gate
enforcement across Windows (tool-pwsh) and Linux/macOS (tool-bash).
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

from .claude import ClaudeCodeAdapter, EVENT_TYPE_MAP as CLAUDE_EVENT_MAP
from .base import BaseAdapter
from ..models import GateDecision, GateResult, HookEvent, HookEventType


DSH_TOOL_NAME_MAP: Dict[str, str] = {
    # Shell execution tools
    "tool-pwsh": "run_command",
    "tool_pwsh": "run_command",
    "pwsh": "run_command",
    "PowerShell": "run_command",
    "powershell": "run_command",
    "tool-bash": "run_command",
    "tool_bash": "run_command",
    "bash": "run_command",
    "Bash": "run_command",
    "run_command": "run_command",

    # File mutation and access tools
    "tool-fs": "replace_file_content",
    "tool_fs": "replace_file_content",
    "tool-fs/write": "write_to_file",
    "tool-fs/edit": "replace_file_content",
    "tool-fs/create": "write_to_file",
    "fs": "replace_file_content",
    "fs_write": "write_to_file",
    "fs_edit": "replace_file_content",
    "Write": "write_to_file",
    "WriteFile": "write_to_file",
    "write_file": "write_to_file",
    "Edit": "replace_file_content",
    "EditFile": "replace_file_content",
    "edit_file": "replace_file_content",
    "MultiEdit": "replace_file_content",
    "NotebookEdit": "replace_file_content",

    # Search and discovery
    "tool-fs-search": "find_by_name",
    "tool_fs_search": "find_by_name",
    "fs_search": "find_by_name",
    "Grep": "grep_search",
    "grep_search": "grep_search",
    "Glob": "find_by_name",
    "find_by_name": "find_by_name",

    # Read-only and navigation
    "Read": "view_file",
    "view_file": "view_file",
    "LS": "list_dir",
    "list_dir": "list_dir",
    "WebFetch": "read_url_content",
    "WebSearch": "search_web",
    "tool-web": "read_url_content",
    "tool_web": "read_url_content",

    # Agent tasks and subagents
    "tool-subagent": "invoke_subagent",
    "tool_subagent": "invoke_subagent",
    "subagent": "invoke_subagent",
    "subagent_fork": "invoke_subagent",
    "TodoWrite": "manage_task",
    "Task": "manage_task",
    "Agent": "manage_task",
    "ExitPlanMode": "ask_question",
    "AskUserQuestion": "ask_question",
}

DSH_EXEMPT_TOOLS: Tuple[str, ...] = (
    "tool-todo",
    "tool-goal",
    "tool-ralph",
    "tool-result-pruner",
    "tool-plugin-manager",
    "tool-jobs",
    "tool-subagent-list-agents",
    "tool-subagent-control",
    "tool-workflow",
    "command-compact",
    "BashOutput",
    "KillShell",
    "SlashCommand",
    "Skill",
    "ToolSearch",
)


class DeepSeekHarnessAdapter(ClaudeCodeAdapter):
    """Adapter for DeepSeek Harness (DSH) lifecycle hooks and gate enforcement."""

    runtime_name: str = "dsh"

    def parse(self, raw_input: str, event_type: HookEventType = HookEventType.PRE_TOOL_USE) -> HookEvent:
        """Parse DSH hook payload, normalizing DSH-specific tool names and arguments."""
        clean_input = raw_input.strip()
        payload: Dict[str, Any] = {}
        if clean_input:
            try:
                data = json.loads(clean_input)
                if isinstance(data, dict):
                    payload = data
            except (json.JSONDecodeError, ValueError):
                pass

        # Detect event type from payload or fallback
        raw_event_name = (
            payload.get("hook_event_name")
            or payload.get("event")
            or payload.get("event_type")
            or payload.get("hook")
        )
        effective_event_type = CLAUDE_EVENT_MAP.get(str(raw_event_name), event_type)

        raw_tool_name = str(
            payload.get("tool_name")
            or payload.get("tool")
            or payload.get("name")
            or ""
        )
        tool_args = (
            payload.get("tool_input")
            or payload.get("tool_args")
            or payload.get("args")
            or payload.get("parameters")
            or {}
        )
        if not isinstance(tool_args, dict):
            tool_args = {"raw_value": tool_args}

        # Normalize DSH tool arguments
        fs_action = str(tool_args.get("action") or "").lower().strip()
        if raw_tool_name in ("tool-fs", "tool_fs", "fs") and fs_action:
            if fs_action in ("write", "create"):
                tool_name = "write_to_file"
            elif fs_action in ("edit", "patch", "replace"):
                tool_name = "replace_file_content"
            else:
                tool_name = DSH_TOOL_NAME_MAP.get(raw_tool_name, "replace_file_content")
        else:
            tool_name = DSH_TOOL_NAME_MAP.get(raw_tool_name, raw_tool_name)

        # Normalize command line for shell executions
        if tool_name == "run_command":
            cmd = (
                tool_args.get("CommandLine")
                or tool_args.get("command")
                or tool_args.get("script")
                or tool_args.get("code")
                or ""
            )
            tool_args.setdefault("CommandLine", cmd)
            tool_args.setdefault("command", cmd)

        # Normalize file path for filesystem mutations
        if tool_name in ("write_to_file", "replace_file_content"):
            path = (
                tool_args.get("Path")
                or tool_args.get("file_path")
                or tool_args.get("path")
                or ""
            )
            tool_args.setdefault("Path", path)
            tool_args.setdefault("file_path", path)

        workspace_root = str(payload.get("cwd") or payload.get("workspace_root") or "")
        session_id = payload.get("session_id") or payload.get("sessionId")
        conversation_id = str(session_id) if session_id else None
        self._event_type = effective_event_type
        self._stop_hook_active = bool(payload.get("stop_hook_active"))

        subagent_id: Optional[str] = None
        subagent_role: Optional[str] = None
        raw_subagent = payload.get("subagent") or payload.get("agent")
        if isinstance(raw_subagent, dict):
            subagent_id = str(raw_subagent.get("id") or raw_subagent.get("session_id") or "") or None
            subagent_role = str(raw_subagent.get("role") or raw_subagent.get("name") or "") or None
        elif isinstance(raw_subagent, str) and raw_subagent.strip() and raw_subagent.lower() not in ("main", "supervisor"):
            subagent_role = raw_subagent.strip()

        return HookEvent(
            event_type=effective_event_type,
            tool_name=tool_name,
            tool_args=tool_args,
            workspace_root=workspace_root,
            runtime=self.runtime_name,
            conversation_id=conversation_id,
            raw_payload=payload,
            subagent_id=subagent_id,
            subagent_role=subagent_role,
        )
