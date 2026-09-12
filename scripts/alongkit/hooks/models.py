#!/usr/bin/env python3
"""
alongkit.hooks.models - Canonical event and result data models for lifecycle hooks.

Abstracts runtime-specific payload schemas (Antigravity camelCase JSON, Claude Code,
Codex) into canonical HookEvent and GateResult data classes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class HookEventType(str, Enum):
    """Supported agent lifecycle events."""
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    PRE_INVOCATION = "PreInvocation"
    POST_INVOCATION = "PostInvocation"
    STOP = "Stop"


class GateDecision(str, Enum):
    """Outcome decision of a hook gate evaluation."""
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"
    FORCE_ASK = "force_ask"


@dataclass
class HookEvent:
    """Canonical representation of an agent lifecycle hook trigger."""
    event_type: HookEventType
    tool_name: str = ""
    tool_args: Dict[str, Any] = field(default_factory=dict)
    workspace_root: str = ""
    runtime: str = "generic"
    step_idx: Optional[int] = None
    invocation_num: Optional[int] = None
    conversation_id: Optional[str] = None
    model_name: Optional[str] = None
    raw_payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GateResult:
    """Decision and remediation information produced by a gate."""
    decision: GateDecision = GateDecision.ALLOW
    reason: Optional[str] = None
    gate_name: str = ""
    permission_overrides: List[str] = field(default_factory=list)
    overwrite: Optional[Dict[str, Any]] = None
    exit_code: int = 0

    @property
    def is_allowed(self) -> bool:
        return self.decision == GateDecision.ALLOW

    @property
    def is_denied(self) -> bool:
        return self.decision == GateDecision.DENY
