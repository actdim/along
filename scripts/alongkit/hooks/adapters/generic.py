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
    "beforeReadFile": HookEventType.PRE_TOOL_USE,
    "PostToolUse": HookEventType.POST_TOOL_USE,
    "post_tool_use": HookEventType.POST_TOOL_USE,
    "postToolUse": HookEventType.POST_TOOL_USE,
    "afterShellExecution": HookEventType.POST_TOOL_USE,
    "afterFileEdit": HookEventType.POST_TOOL_USE,
    "Stop": HookEventType.STOP,
    "stop": HookEventType.STOP,
    "UserPromptSubmit": HookEventType.USER_PROMPT_SUBMIT,
    "user_prompt_submit": HookEventType.USER_PROMPT_SUBMIT,
    "beforeSubmitPrompt": HookEventType.USER_PROMPT_SUBMIT,
}

#: Explicit read-only OpenCode/generic tool allowlist (intentionally ungated by write/shell gates).
READ_ONLY_TOOLS = frozenset({"read", "glob", "grep", "webfetch", "list"})

TOOL_NAME_MAP: Dict[str, str] = {
    # Explicit read-only allowlist -> canonical read/search tools (no unmapped_tool audit noise)
    "read": "read_file",
    "glob": "find_by_name",
    "grep": "grep_search",
    "webfetch": "read_url_content",
    "list": "list_dir",
    # Cursor and canonical read / list / search tools
    "Read": "view_file",
    "ReadFile": "read_file",
    "read_file": "read_file",
    "view_file": "view_file",
    "ViewFile": "view_file",
    "view_image": "view_image",
    "ViewImage": "view_image",
    "read_image": "view_image",
    "LS": "list_dir",
    "list_dir": "list_dir",
    "ListDir": "list_dir",
    "list_directory": "list_directory",
    "ListDirectory": "list_directory",
    "Grep": "grep_search",
    "grep_search": "grep_search",
    "GrepSearch": "grep_search",
    "ripgrep": "grep_search",
    "codebase_search": "grep_search",
    "Glob": "find_by_name",
    "find_by_name": "find_by_name",
    "find_files": "find_files",
    "FindFiles": "find_files",
    "file_search": "file_search",
    "FileSearch": "file_search",
    "glob_file_search": "file_search",
    "WebFetch": "read_url_content",
    "WebSearch": "search_web",
    # Non-read-only OpenCode/Cursor/generic tools -> canonical gated tools
    "task": "Task",
    "Task": "Task",
    "Agent": "manage_task",
    "Subagent": "invoke_subagent",
    "subagent": "invoke_subagent",
    "invoke_subagent": "invoke_subagent",
    "spawn_subagent": "spawn_subagent",
    "send_message": "send_message",
    "SendMessage": "send_message",
    "manage_task": "manage_task",
    "TodoWrite": "manage_task",
    "skill": "invoke_subagent",
    "todowrite": "write_to_file",
    "write_to_file": "write_to_file",
    "write_file": "write_to_file",
    "WriteFile": "write_to_file",
    "Write": "write_to_file",
    "write": "write_to_file",
    "create_file": "write_to_file",
    "CreateFile": "write_to_file",
    "edit_file": "replace_file_content",
    "EditFile": "replace_file_content",
    "Edit": "replace_file_content",
    "edit": "replace_file_content",
    "StrReplace": "replace_file_content",
    "str_replace": "replace_file_content",
    "MultiEdit": "replace_file_content",
    "NotebookEdit": "replace_file_content",
    "edit_notebook": "replace_file_content",
    "search_replace": "replace_file_content",
    "apply_patch": "replace_file_content",
    "patch": "replace_file_content",
    "patch_file": "replace_file_content",
    "replace_file_content": "replace_file_content",
    "Shell": "run_command",
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
    "run_terminal_cmd": "run_command",
    "RunTerminalCmd": "run_command",
    "execute_command": "execute_command",
    "ExecuteCommand": "execute_command",
    "delete_file": "delete_file",
    "DeleteFile": "delete_file",
    "delete": "delete",
    "Delete": "delete",
    "file_delete": "file_delete",
    "FileDelete": "file_delete",
    "remove_file": "remove_file",
    "RemoveFile": "remove_file",
    "remove": "remove",
    "Remove": "remove",
    "unlink": "unlink",
    "Unlink": "unlink",
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
            clean_text = raw_input.lstrip("\ufeff").strip()
            try:
                parsed = json.loads(clean_text)
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
        for key in ("tool_input", "tool_args", "parameters", "arguments", "args", "input"):
            if key in payload and payload[key] is not None:
                raw_params = payload[key]
                break

        if raw_params is None and isinstance(tool_call, dict):
            for key in ("tool_args", "parameters", "arguments", "args", "input"):
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
            for k in (
                "CommandLine", "command", "cmd", "TargetFile", "target_file", "file_path",
                "FilePath", "AbsolutePath", "DirectoryPath", "SearchPath", "SearchDirectory",
                "Directory", "filename", "path", "file", "CodeContent", "content",
                "ReplacementContent", "new_string", "patch",
            ):
                if k in payload:
                    tool_args[k] = payload[k]

        # Normalize file targets
        for key in (
            "file_path", "filePath", "FilePath", "target_file", "AbsolutePath",
            "DirectoryPath", "path", "file", "target", "filename",
        ):
            if key in tool_args and "TargetFile" not in tool_args:
                tool_args["TargetFile"] = tool_args[key]
                break

        # Normalize write content
        for key in ("content", "code", "text", "file_text", "CodeContent"):
            if key in tool_args and "CodeContent" not in tool_args:
                if tool_name not in ("run_command", "execute", "bash", "shell", "powershell", "cmd"):
                    tool_args["CodeContent"] = tool_args[key]
                    break

        # Normalize edit / replacement content
        for key in ("new_string", "newString", "replacement", "new_content", "patch", "ReplacementContent"):
            if key in tool_args:
                tool_args.setdefault("ReplacementContent", tool_args[key])
                tool_args.setdefault("content", tool_args[key])
                break

        # Normalize edit / target content
        for key in ("old_string", "oldString", "target_string", "target", "Target", "OldString"):
            if key in tool_args and key != "TargetFile":
                tool_args.setdefault("OldString", tool_args[key])
                tool_args.setdefault("Target", tool_args[key])
                break

        # Normalize command line
        for key in ("command", "cmd", "script", "code", "CommandLine"):
            if key in tool_args and "CommandLine" not in tool_args:
                if key != "code" or tool_name in ("run_command", "execute", "bash", "shell", "powershell", "cmd"):
                    tool_args["CommandLine"] = tool_args[key]
                    break

        # Fallback tool name detection based on event or normalized arguments
        if not tool_name:
            raw_ev_lower = str(raw_event_name or "").lower()
            if raw_ev_lower == "beforereadfile":
                tool_name = "view_file"
            elif raw_ev_lower == "beforeshellexecution":
                tool_name = "run_command"
            elif "CommandLine" in tool_args:
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
            ws_paths = payload.get("workspacePaths") or payload.get("workspace_roots") or []
            if isinstance(ws_paths, list) and ws_paths:
                workspace_root = str(ws_paths[0])

        session_id = (
            payload.get("session_id")
            or payload.get("sessionId")
            or payload.get("sessionID")
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
