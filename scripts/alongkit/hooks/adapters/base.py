#!/usr/bin/env python3
"""
alongkit.hooks.adapters.base - Abstract base adapter for runtime hook protocols.
"""

from __future__ import annotations

from typing import Tuple

from ..models import GateResult, HookEvent, HookEventType


class BaseAdapter:
    """Abstract interface for mapping runtime-specific I/O to canonical hook entities."""

    runtime_name: str = "generic"

    def parse(self, raw_input: str, event_type: HookEventType = HookEventType.PRE_TOOL_USE) -> HookEvent:
        """Parse raw input from runtime (stdin) into a canonical HookEvent."""
        raise NotImplementedError

    def format_response(self, result: GateResult) -> Tuple[int, str]:
        """Format GateResult into (exit_code, output_payload_for_stdout_or_stderr)."""
        raise NotImplementedError
