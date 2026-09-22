#!/usr/bin/env python3
"""
alongkit.hooks.adapters.codex - OpenAI Codex hook protocol adapter.

Translates OpenAI Codex JSON stdin payloads to canonical HookEvent, and GateResult
to process exit codes and stderr feedback.
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
    "write_file": "write_to_file",
    "WriteFile": "write_to_file",
    "Write": "write_to_file",
    "create_file": "write_to_file",
    "edit_file": "replace_file_content",
    "EditFile": "replace_file_content",
    "Edit": "replace_file_content",
    "patch": "replace_file_content",
    "patch_file": "replace_file_content",
    "shell": "run_command",
    "exec": "run_command",
    "execute": "run_command",
    "bash": "run_command",
    "Bash": "run_command",
    "powershell": "run_command",
    "PowerShell": "run_command",
    "cmd": "run_command",
}


class CodexAdapter(BaseAdapter):
    """Adapter for OpenAI Codex CLI and headless hook protocol."""

    runtime_name: str = "codex"

    def parse(self, raw_input: str, event_type: HookEventType = HookEventType.PRE_TOOL_USE) -> HookEvent:
        payload: Dict[str, Any] = {}
        if raw_input and raw_input.strip():
            clean_text = raw_input.lstrip("\ufeff").strip()
            try:
                parsed = json.loads(clean_text)
                if isinstance(parsed, dict):
                    payload = parsed
            except json.JSONDecodeError:
                pass

        # Resolve event type from payload hook_event_name or event_type if present
        raw_event_name = (
            payload.get("hook_event_name")
            or payload.get("event_type")
            or payload.get("event")
            or payload.get("type")
        )
        effective_event_type = event_type
        if raw_event_name:
            raw_event_str = str(raw_event_name)
            if raw_event_str in EVENT_TYPE_MAP:
                effective_event_type = EVENT_TYPE_MAP[raw_event_str]
            else:
                try:
                    effective_event_type = HookEventType(raw_event_str)
                except ValueError:
                    effective_event_type = event_type

        # Map tool name
        raw_tool_name = str(
            payload.get("tool_name")
            or payload.get("tool")
            or payload.get("name")
            or ""
        )
        tool_call = payload.get("tool_call") or payload.get("toolCall")
        if not raw_tool_name and isinstance(tool_call, dict):
            raw_tool_name = str(tool_call.get("name") or tool_call.get("tool") or "")

        tool_name = TOOL_NAME_MAP.get(raw_tool_name, raw_tool_name)

        # Handle payload parameters from tool_input, parameters, arguments, or args
        raw_params = None
        for key in ("tool_input", "parameters", "arguments", "args"):
            if key in payload and payload[key] is not None:
                raw_params = payload[key]
                break

        if raw_params is None and isinstance(tool_call, dict):
            for key in ("tool_input", "parameters", "arguments", "args"):
                if key in tool_call and tool_call[key] is not None:
                    raw_params = tool_call[key]
                    break

        tool_args: Dict[str, Any] = {}
        if isinstance(raw_params, str) and raw_params.strip():
            try:
                parsed_params = json.loads(raw_params)
                if isinstance(parsed_params, dict):
                    tool_args = dict(parsed_params)
            except json.JSONDecodeError:
                pass
        elif isinstance(raw_params, dict):
            tool_args = dict(raw_params)

        # Fallback if arguments were passed directly in root payload
        if not tool_args and isinstance(payload, dict):
            for k in (
                "file_path", "path", "filePath", "content", "text", "code", "file_text",
                "new_string", "replacement", "new_content", "patch", "command", "cmd", "script",
            ):
                if k in payload:
                    tool_args = dict(payload)
                    break

        # Normalize arguments:
        # file_path, path, filePath -> TargetFile
        for key in ("file_path", "path", "filePath"):
            if key in tool_args and tool_args[key] is not None:
                tool_args.setdefault("TargetFile", tool_args[key])
                break

        # content, text, code, file_text -> CodeContent (and content)
        for key in ("content", "text", "code", "file_text"):
            if key in tool_args and tool_args[key] is not None:
                tool_args.setdefault("CodeContent", tool_args[key])
                tool_args.setdefault("content", tool_args[key])
                break

        # new_string, replacement, new_content, patch -> ReplacementContent (and content)
        for key in ("new_string", "replacement", "new_content", "patch"):
            if key in tool_args and tool_args[key] is not None:
                tool_args.setdefault("ReplacementContent", tool_args[key])
                if tool_name == "replace_file_content":
                    tool_args["content"] = tool_args[key]
                else:
                    tool_args.setdefault("content", tool_args[key])
                break

        # command, cmd, script -> CommandLine
        for key in ("command", "cmd", "script"):
            if key in tool_args and tool_args[key] is not None:
                tool_args.setdefault("CommandLine", tool_args[key])
                break

        # cwd, workspace_root, workdir -> workspace_root
        workspace_root = ""
        for key in ("cwd", "workspace_root", "workdir"):
            val = payload.get(key) or tool_args.get(key)
            if val:
                workspace_root = str(val)
                break

        # session_id, conversation_id, id -> conversation_id
        conversation_id: Optional[str] = None
        for key in ("session_id", "conversation_id", "id"):
            val = payload.get(key) or tool_args.get(key)
            if val:
                conversation_id = str(val)
                break

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
        """Format GateResult into Codex exit code and message."""
        if result.is_denied:
            return 2, result.reason or "Operation rejected by Along protocol gate."
        return 0, ""
