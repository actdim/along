#!/usr/bin/env python3
"""
alongkit.hooks.adapters.claude - Anthropic Claude Code hook protocol adapter.

Translates Claude Code JSON stdin payloads to canonical HookEvent, and GateResult
to Claude Code process exit codes and stderr feedback.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

from .base import BaseAdapter
from ..models import GateResult, HookEvent, HookEventType


EVENT_TYPE_MAP: Dict[str, HookEventType] = {
    "PreToolUse": HookEventType.PRE_TOOL_USE,
    "pre_tool_use": HookEventType.PRE_TOOL_USE,
    "PostToolUse": HookEventType.POST_TOOL_USE,
    "post_tool_use": HookEventType.POST_TOOL_USE,
    "Stop": HookEventType.STOP,
    "stop": HookEventType.STOP,
}

TOOL_NAME_MAP: Dict[str, str] = {
    "Write": "write_to_file",
    "WriteFile": "write_to_file",
    "write_file": "write_to_file",
    "Edit": "replace_file_content",
    "EditFile": "replace_file_content",
    "edit_file": "replace_file_content",
    "Bash": "run_command",
    "bash": "run_command",
    "PowerShell": "run_command",
    "powershell": "run_command",
}


class ClaudeCodeAdapter(BaseAdapter):
    """Adapter for Anthropic Claude Code CLI lifecycle hooks."""

    runtime_name: str = "claude"

    def parse(self, raw_input: str, event_type: HookEventType = HookEventType.PRE_TOOL_USE) -> HookEvent:
        payload: Dict[str, Any] = {}
        if raw_input and raw_input.strip():
            try:
                parsed = json.loads(raw_input)
                if isinstance(parsed, dict):
                    payload = parsed
            except json.JSONDecodeError:
                pass

        # Resolve event type from payload hook_event_name if present
        raw_event_name = payload.get("hook_event_name")
        effective_event_type = event_type
        if raw_event_name:
            if raw_event_name in EVENT_TYPE_MAP:
                effective_event_type = EVENT_TYPE_MAP[raw_event_name]
            else:
                try:
                    effective_event_type = HookEventType(raw_event_name)
                except ValueError:
                    effective_event_type = event_type

        # Map tool name
        raw_tool_name = str(payload.get("tool_name") or "")
        tool_name = TOOL_NAME_MAP.get(raw_tool_name, raw_tool_name)

        # Extract and normalize tool arguments
        tool_input = payload.get("tool_input", {})
        if not isinstance(tool_input, dict):
            tool_input = {}
        tool_args: Dict[str, Any] = dict(tool_input)

        if "file_path" in tool_args:
            tool_args.setdefault("TargetFile", tool_args["file_path"])
        elif "path" in tool_args:
            tool_args.setdefault("TargetFile", tool_args["path"])

        if "content" in tool_args and tool_name == "write_to_file":
            tool_args.setdefault("CodeContent", tool_args["content"])

        if "new_string" in tool_args:
            tool_args.setdefault("ReplacementContent", tool_args["new_string"])
            tool_args.setdefault("content", tool_args["new_string"])

        if "command" in tool_args:
            tool_args.setdefault("CommandLine", tool_args["command"])

        workspace_root = str(payload.get("cwd") or "")
        session_id = payload.get("session_id")
        conversation_id = str(session_id) if session_id else None

        return HookEvent(
            event_type=effective_event_type,
            tool_name=tool_name,
            tool_args=tool_args,
            workspace_root=workspace_root,
            runtime=self.runtime_name,
            conversation_id=conversation_id,
            raw_payload=payload,
        )

    def format_response(self, result: GateResult) -> Tuple[int, str]:
        """Format GateResult into Claude Code exit code and message."""
        if result.is_denied:
            return 2, result.reason or "Operation rejected by Along protocol gate."
        return 0, ""
