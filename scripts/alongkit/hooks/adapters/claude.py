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
from ..models import GateDecision, GateResult, HookEvent, HookEventType


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
    "MultiEdit": "replace_file_content",
    "NotebookEdit": "replace_file_content",
    "Bash": "run_command",
    "bash": "run_command",
    "PowerShell": "run_command",
    "powershell": "run_command",
    "Grep": "grep_search",
    "Glob": "find_by_name",
    # Read-only tools, mapped so they are recognized rather than audited as unmapped.
    "Read": "view_file",
    "LS": "list_dir",
    "WebFetch": "read_url_content",
    "WebSearch": "search_web",
    "TodoWrite": "manage_task",
    "Task": "manage_task",
    "Agent": "manage_task",
    "ExitPlanMode": "ask_question",
    "AskUserQuestion": "ask_question",
}

#: Claude Code tools that the gates deliberately do not inspect: they neither write
#: repository files nor run commands. `tests/test_hooks_tool_coverage.py` asserts that
#: every documented Claude Code tool is either in TOOL_NAME_MAP or listed here.
EXEMPT_TOOLS: Tuple[str, ...] = ("BashOutput", "KillShell", "SlashCommand", "Skill", "ToolSearch")


class ClaudeCodeAdapter(BaseAdapter):
    """Adapter for Anthropic Claude Code CLI lifecycle hooks."""

    runtime_name: str = "claude"

    def __init__(self) -> None:
        self._event_type: Optional[HookEventType] = None
        self._stop_hook_active: bool = False

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
        elif "notebook_path" in tool_args:
            tool_args.setdefault("TargetFile", tool_args["notebook_path"])
        elif "path" in tool_args and tool_name not in ("grep_search", "find_by_name"):
            tool_args.setdefault("TargetFile", tool_args["path"])

        # MultiEdit carries a list of edits; the gates inspect the combined new text.
        edits = tool_args.get("edits")
        if raw_tool_name == "MultiEdit" and isinstance(edits, list):
            combined = "\n".join(
                str(e.get("new_string", "")) for e in edits if isinstance(e, dict)
            )
            tool_args.setdefault("ReplacementContent", combined)
            tool_args.setdefault("content", combined)

        # NotebookEdit carries the new cell source.
        if "new_source" in tool_args:
            tool_args.setdefault("ReplacementContent", tool_args["new_source"])
            tool_args.setdefault("content", tool_args["new_source"])

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
        self._event_type = effective_event_type
        self._stop_hook_active = bool(payload.get("stop_hook_active"))

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
        """Format GateResult into Claude Code exit code and message.

        - DENY: exit 2, reason on stderr (Claude sees it and the tool call is blocked).
        - ASK on PreToolUse: exit 0 with `permissionDecision: "ask"`, so the user decides.
        - DENY on Stop while `stop_hook_active`: Claude already continued once for this
          gate; report the reason to the user instead of forcing another continuation.
        See [bug--claude-stop-loop-ask-mapping].
        """
        reason = result.reason or "Operation rejected by Along protocol gate."
        if result.decision in (GateDecision.ASK, GateDecision.FORCE_ASK) \
                and self._event_type == HookEventType.PRE_TOOL_USE:
            return 0, json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": reason,
            }})
        if result.is_denied:
            if self._event_type == HookEventType.STOP and self._stop_hook_active:
                return 0, json.dumps({"systemMessage": f"[Along] Not enforced again this turn: {reason}"})
            return 2, reason
        return 0, ""
