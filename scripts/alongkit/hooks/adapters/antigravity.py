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

    def parse(self, raw_input: str, event_type: HookEventType = HookEventType.PRE_TOOL_USE) -> HookEvent:
        payload: Dict[str, Any] = {}
        if raw_input and raw_input.strip():
            try:
                payload = json.loads(raw_input)
            except json.JSONDecodeError:
                pass

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
        )

    def format_response(self, result: GateResult) -> Tuple[int, str]:
        """Format GateResult as Antigravity JSON payload on stdout with returncode 0."""
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

        return 0, json.dumps(response)
