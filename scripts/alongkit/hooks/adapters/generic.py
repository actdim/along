#!/usr/bin/env python3
"""
alongkit.hooks.adapters.generic - Generic CLI and terminal proxy hook adapter.

Supports Cursor, OpenCode, and generic CLI harnesses transmitting event context
via stdin JSON or plaintext shell commands. Follows the standard exit-code-2
gate denial protocol with stderr diagnostics.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

from .base import BaseAdapter
from ..models import GateResult, HookEvent, HookEventType


EVENT_TYPE_MAP: Dict[str, HookEventType] = {
    "PreToolUse": HookEventType.PRE_TOOL_USE,
    "pre_tool_use": HookEventType.PRE_TOOL_USE,
    "preToolUse": HookEventType.PRE_TOOL_USE,
    "beforeShellExecution": HookEventType.PRE_TOOL_USE,
    "beforeFileEdit": HookEventType.PRE_TOOL_USE,
    "PostToolUse": HookEventType.POST_TOOL_USE,
    "post_tool_use": HookEventType.POST_TOOL_USE,
    "postToolUse": HookEventType.POST_TOOL_USE,
    "afterShellExecution": HookEventType.POST_TOOL_USE,
    "afterFileEdit": HookEventType.POST_TOOL_USE,
    "Stop": HookEventType.STOP,
    "stop": HookEventType.STOP,
}

TOOL_NAME_MAP: Dict[str, str] = {
    "write_file": "write_to_file",
    "WriteFile": "write_to_file",
    "Write": "write_to_file",
    "write": "write_to_file",
    "create_file": "write_to_file",
    "edit_file": "replace_file_content",
    "EditFile": "replace_file_content",
    "Edit": "replace_file_content",
    "edit": "replace_file_content",
    "patch": "replace_file_content",
    "patch_file": "replace_file_content",
    "replace_file_content": "replace_file_content",
    "shell": "run_command",
    "exec": "run_command",
    "execute": "run_command",
    "bash": "run_command",
    "Bash": "run_command",
    "powershell": "run_command",
    "PowerShell": "run_command",
    "cmd": "run_command",
    "run": "run_command",
    "run_command": "run_command",
}


class GenericCliAdapter(BaseAdapter):
    """Adapter for generic CLI tools, terminal proxy wrappers, Cursor, and OpenCode."""

    runtime_name: str = "generic"

    def __init__(self, runtime_name: str = "generic") -> None:
        self.runtime_name = runtime_name

    def parse(self, raw_input: str, event_type: HookEventType = HookEventType.PRE_TOOL_USE) -> HookEvent:
        payload: Dict[str, Any] = {}
        is_json = False

        if raw_input and raw_input.strip():
            try:
                parsed = json.loads(raw_input)
                if isinstance(parsed, dict):
                    payload = parsed
                    is_json = True
            except json.JSONDecodeError:
                pass

        if not is_json:
            # Fallback for plain shell string or piped command
            raw_text = raw_input.strip() if raw_input else ""
            tool_args: Dict[str, Any] = {}
            tool_name = ""
            if raw_text:
                tool_name = "run_command"
                tool_args = {"CommandLine": raw_text}

            return HookEvent(
                event_type=event_type,
                tool_name=tool_name,
                tool_args=tool_args,
                workspace_root="",
                runtime=self.runtime_name,
                raw_payload={"raw_text": raw_text},
            )

        # 1. Resolve event type from payload
        effective_event_type = event_type
        raw_event_name = (
            payload.get("hook_event_name")
            or payload.get("event_type")
            or payload.get("event")
            or payload.get("type")
            or payload.get("hook")
        )
        if raw_event_name:
            raw_event_str = str(raw_event_name)
            if raw_event_str in EVENT_TYPE_MAP:
                effective_event_type = EVENT_TYPE_MAP[raw_event_str]
            else:
                for k, v in EVENT_TYPE_MAP.items():
                    if k.lower() == raw_event_str.lower():
                        effective_event_type = v
                        break

        # 2. Extract tool name
        raw_tool_name = str(
            payload.get("tool_name")
            or payload.get("tool")
            or payload.get("name")
            or payload.get("action")
            or ""
        )
        tool_call = payload.get("tool_call") or payload.get("toolCall")
        if not raw_tool_name and isinstance(tool_call, dict):
            raw_tool_name = str(tool_call.get("name") or tool_call.get("tool") or "")

        tool_name = TOOL_NAME_MAP.get(raw_tool_name, raw_tool_name)

        # 3. Extract and normalize tool arguments
        raw_params = None
        for key in ("tool_input", "parameters", "arguments", "args", "input"):
            if key in payload and payload[key] is not None:
                raw_params = payload[key]
                break

        if raw_params is None and isinstance(tool_call, dict):
            for key in ("parameters", "arguments", "args", "input"):
                if key in tool_call and tool_call[key] is not None:
                    raw_params = tool_call[key]
                    break

        if isinstance(raw_params, str) and raw_params.strip().startswith("{"):
            try:
                raw_params = json.loads(raw_params)
            except json.JSONDecodeError:
                pass

        tool_args: Dict[str, Any] = {}
        if isinstance(raw_params, dict):
            tool_args = dict(raw_params)
        elif isinstance(raw_params, str):
            tool_args = {"raw_input": raw_params}
        else:
            # Check if arguments are in root payload
            for k in ("CommandLine", "command", "cmd", "TargetFile", "file_path", "path", "file", "CodeContent", "content", "ReplacementContent", "new_string", "patch"):
                if k in payload:
                    tool_args[k] = payload[k]

        # Normalize file targets
        for key in ("file_path", "filePath", "path", "file", "target", "target_file"):
            if key in tool_args and "TargetFile" not in tool_args:
                tool_args["TargetFile"] = tool_args[key]
                break

        # Normalize write content
        for key in ("content", "code", "text", "file_text", "CodeContent"):
            if key in tool_args and "CodeContent" not in tool_args:
                tool_args["CodeContent"] = tool_args[key]
                break

        # Normalize edit / replacement content
        for key in ("new_string", "replacement", "new_content", "patch", "ReplacementContent"):
            if key in tool_args:
                tool_args.setdefault("ReplacementContent", tool_args[key])
                tool_args.setdefault("content", tool_args[key])
                break

        # Normalize command line
        for key in ("command", "cmd", "script", "CommandLine"):
            if key in tool_args and "CommandLine" not in tool_args:
                tool_args["CommandLine"] = tool_args[key]
                break

        # Fallback tool name detection based on normalized arguments
        if not tool_name:
            if "CommandLine" in tool_args:
                tool_name = "run_command"
            elif "ReplacementContent" in tool_args:
                tool_name = "replace_file_content"
            elif "TargetFile" in tool_args and "CodeContent" in tool_args:
                tool_name = "write_to_file"

        # Extract workspace root
        workspace_root = str(
            payload.get("cwd")
            or payload.get("workspace_root")
            or payload.get("workspaceRoot")
            or payload.get("workdir")
            or ""
        )
        if not workspace_root:
            ws_paths = payload.get("workspacePaths", [])
            if isinstance(ws_paths, list) and ws_paths:
                workspace_root = str(ws_paths[0])

        session_id = (
            payload.get("session_id")
            or payload.get("sessionId")
            or payload.get("conversation_id")
            or payload.get("conversationId")
        )
        conversation_id = str(session_id) if session_id else None

        return HookEvent(
            event_type=effective_event_type,
            tool_name=tool_name,
            tool_args=tool_args,
            workspace_root=workspace_root,
            runtime=self.runtime_name,
            step_idx=payload.get("step_idx") or payload.get("stepIdx"),
            conversation_id=conversation_id,
            model_name=payload.get("model_name") or payload.get("modelName"),
            raw_payload=payload,
        )

    def format_response(self, result: GateResult) -> Tuple[int, str]:
        """Format GateResult into exit code 0 (allow) or 2 (deny) with stderr reason."""
        if result.is_denied:
            return 2, result.reason or "Operation rejected by Along protocol gate."
        return 0, ""
