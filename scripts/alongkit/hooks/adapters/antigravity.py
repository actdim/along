#!/usr/bin/env python3
"""
alongkit.hooks.adapters.antigravity - Google Antigravity hook protocol adapter.

Translates Antigravity JSON stdin payloads to HookEvent, and GateResult to
Antigravity JSON stdout responses.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple

from .base import BaseAdapter
from ..models import GateDecision, GateResult, HookEvent, HookEventType


class AntigravityAdapter(BaseAdapter):
    """Adapter for Google Antigravity lifecycle hooks (.agents/hooks.json)."""

    runtime_name: str = "antigravity"

    def parse_post_tool_use(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract tool execution result data from PostToolUse payloads."""
        tool_result = payload.get("toolResult", {})
        extracted: Dict[str, Any] = {}
        if isinstance(tool_result, dict):
            if "output" in tool_result:
                extracted["output"] = str(tool_result["output"])
            if "exitCode" in tool_result:
                try:
                    extracted["exitCode"] = int(tool_result["exitCode"])
                except (ValueError, TypeError):
                    pass
            if "durationMs" in tool_result:
                try:
                    extracted["durationMs"] = float(tool_result["durationMs"])
                except (ValueError, TypeError):
                    pass
        return extracted

    def parse(self, raw_input: str, event_type: HookEventType = HookEventType.PRE_TOOL_USE) -> HookEvent:
        self._last_event_type = event_type
        payload: Dict[str, Any] = {}
        if raw_input and raw_input.strip():
            clean_text = raw_input.lstrip("\ufeff").strip()
            try:
                payload = json.loads(clean_text)
            except json.JSONDecodeError:
                pass

        if "toolResult" in payload:
            payload["toolResult"] = self.parse_post_tool_use(payload)

        tool_name = ""
        tool_args: Dict[str, Any] = {}
        tool_call = payload.get("toolCall", {})
        if isinstance(tool_call, dict):
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            if not isinstance(tool_args, dict):
                tool_args = {}

        workspace_root = ""
        ws_paths = payload.get("workspacePaths", [])
        if isinstance(ws_paths, list) and ws_paths:
            workspace_root = str(ws_paths[0])

        subagent_id: Optional[str] = None
        subagent_role: Optional[str] = None
        raw_subagent = payload.get("subagent") or payload.get("agent")
        if isinstance(raw_subagent, dict):
            subagent_id = str(raw_subagent.get("id") or raw_subagent.get("conversationId") or "") or None
            subagent_role = str(raw_subagent.get("role") or raw_subagent.get("name") or "") or None
        elif isinstance(raw_subagent, str) and raw_subagent.strip() and raw_subagent.lower() not in ("main", "supervisor"):
            subagent_role = raw_subagent.strip()

        if not subagent_id:
            raw_id = payload.get("subagentId") or payload.get("subagent_id") or payload.get("agentId") or payload.get("agent_id")
            if raw_id:
                subagent_id = str(raw_id)
        if not subagent_role:
            raw_role = payload.get("subagentRole") or payload.get("agentRole") or payload.get("subagent_role") or payload.get("agent_role") or payload.get("role")
            if raw_role:
                subagent_role = str(raw_role)

        return HookEvent(
            event_type=event_type,
            tool_name=tool_name,
            tool_args=tool_args,
            workspace_root=workspace_root,
            runtime=self.runtime_name,
            step_idx=payload.get("stepIdx"),
            conversation_id=payload.get("conversationId"),
            model_name=payload.get("modelName"),
            raw_payload=payload,
            subagent_id=subagent_id,
            subagent_role=subagent_role,
        )

    def format_response(self, result: GateResult) -> Tuple[int, str]:
        """Format GateResult as Antigravity JSON payload on stdout with returncode 0."""
        if getattr(self, "_last_event_type", None) == HookEventType.POST_TOOL_USE:
            return 0, "{}"

        response: Dict[str, Any] = {}

        if result.decision == GateDecision.DENY:
            response["decision"] = "deny"
            response["reason"] = result.reason or "Operation rejected by Along protocol gate."
        elif result.decision == GateDecision.ASK:
            response["decision"] = "ask"
            if result.reason:
                response["reason"] = result.reason
        elif result.decision == GateDecision.FORCE_ASK:
            response["decision"] = "force_ask"
            if result.reason:
                response["reason"] = result.reason
        else:
            response["decision"] = "allow"

        if result.overwrite:
            response["overwrite"] = result.overwrite

        if result.permission_overrides:
            response["permissionOverrides"] = result.permission_overrides

        if result.notice and getattr(self, "_last_event_type", None) == HookEventType.PRE_TOOL_USE:
            response["systemMessage"] = result.notice
            response["additionalContext"] = result.notice

        return 0, json.dumps(response)
