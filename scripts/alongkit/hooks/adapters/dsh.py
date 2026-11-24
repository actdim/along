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
    # Model-facing names: what a DeepSeek Harness payload actually carries. The shipped
    # @deepseek-ai/dsh-tool-fs package publishes `read`/`write`/`edit`, dsh-tool-fs-search
    # publishes `glob`/`grep`, dsh-tool-pwsh publishes `pwsh`, dsh-tool-bash publishes `bash`
    # and dsh-tool-todo publishes `todo_write`.
    "read": "view_file",
    "write": "write_to_file",
    "edit": "replace_file_content",
    "glob": "find_by_name",
    "grep": "grep_search",
    "pwsh": "run_command",
    "PowerShell": "run_command",
    "powershell": "run_command",
    "bash": "run_command",
    "Bash": "run_command",
    "run_command": "run_command",
    "read_image": "view_image",
    "web_fetch": "read_url_content",
    "web_search": "search_web",
    "todo_write": "manage_task",
    "skill": "manage_task",
    "workflow": "manage_task",
    "list_agents": "manage_task",
    "interrupt_agent": "manage_task",
    "job_output": "manage_task",
    "job_list": "manage_task",
    "job_kill": "manage_task",
    "create_goal": "manage_task",
    "get_goal": "manage_task",
    "update_goal": "manage_task",
    "load_workspace_dependencies": "manage_task",
    "present": "manage_task",
    "send_message": "send_message",
    "ask_user_question": "ask_question",
    "exit_plan_mode": "ask_question",
    "subagent": "invoke_subagent",
    "subagent_fork": "invoke_subagent",

    # Composition entry ids: a cordis.patch.yml row (`- id: tool-fs`). Kept as aliases so an
    # unusual mount still resolves, and because these are what a misconfigured bridge sends.
    "tool-pwsh": "run_command",
    "tool_pwsh": "run_command",
    "tool-bash": "run_command",
    "tool_bash": "run_command",
    "tool-fs": "replace_file_content",
    "tool_fs": "replace_file_content",
    "tool-fs/write": "write_to_file",
    "tool-fs/edit": "replace_file_content",
    "tool-fs/create": "write_to_file",
    "fs": "replace_file_content",
    "fs_write": "write_to_file",
    "fs_edit": "replace_file_content",
    "tool-fs-search": "find_by_name",
    "tool_fs_search": "find_by_name",
    "fs_search": "find_by_name",
    "tool-web": "read_url_content",
    "tool_web": "read_url_content",
    "tool-subagent": "invoke_subagent",
    "tool_subagent": "invoke_subagent",

    # Claude Code names: the bridge speaks that dialect, so a payload may arrive with them.
    "Write": "write_to_file",
    "WriteFile": "write_to_file",
    "write_file": "write_to_file",
    "Edit": "replace_file_content",
    "EditFile": "replace_file_content",
    "edit_file": "replace_file_content",
    "MultiEdit": "replace_file_content",
    "NotebookEdit": "replace_file_content",
    "Read": "view_file",
    "view_file": "view_file",
    "LS": "list_dir",
    "list_dir": "list_dir",
    "Grep": "grep_search",
    "grep_search": "grep_search",
    "Glob": "find_by_name",
    "find_by_name": "find_by_name",
    "WebFetch": "read_url_content",
    "WebSearch": "search_web",
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

        # Normalize file path and content for filesystem mutations. The gates read
        # TargetFile/CodeContent/ReplacementContent/content; a payload that carried only
        # `new_string` would otherwise reach no content gate at all.
        if tool_name in ("write_to_file", "replace_file_content"):
            path = (
                tool_args.get("Path")
                or tool_args.get("file_path")
                or tool_args.get("path")
                or ""
            )
            tool_args.setdefault("Path", path)
            tool_args.setdefault("file_path", path)
            if path:
                tool_args.setdefault("TargetFile", path)

        if tool_name == "write_to_file" and tool_args.get("content"):
            tool_args.setdefault("CodeContent", tool_args["content"])

        if tool_name == "replace_file_content":
            for key in ("new_string", "new_content", "new_source", "content"):
                if tool_args.get(key):
                    tool_args.setdefault("ReplacementContent", tool_args[key])
                    tool_args.setdefault("content", tool_args[key])
                    break

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
