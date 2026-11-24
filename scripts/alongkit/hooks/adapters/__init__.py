#!/usr/bin/env python3
"""
alongkit.hooks.adapters - Runtime adapter registry and factory.
"""

from __future__ import annotations

from typing import Dict, Type

from .antigravity import AntigravityAdapter
from .base import BaseAdapter
from .claude import ClaudeCodeAdapter
from .codex import CodexAdapter
from .dsh import DeepSeekHarnessAdapter
from .generic import GenericCliAdapter
from .opencode import OpenCodeAdapter

ADAPTERS: Dict[str, Type[BaseAdapter]] = {
    "antigravity": AntigravityAdapter,
    "agy": AntigravityAdapter,
    "claude": ClaudeCodeAdapter,
    "claudecode": ClaudeCodeAdapter,
    "claude-code": ClaudeCodeAdapter,
    "codex": CodexAdapter,
    "openaicodex": CodexAdapter,
    "openai-codex": CodexAdapter,
    "openai": CodexAdapter,
    "generic": GenericCliAdapter,
    "cli": GenericCliAdapter,
    "generic-cli": GenericCliAdapter,
    "generic_cli": GenericCliAdapter,
    "cursor": GenericCliAdapter,
    "opencode": OpenCodeAdapter,
    "open-code": OpenCodeAdapter,
    "dsh": DeepSeekHarnessAdapter,
    "deepseek": DeepSeekHarnessAdapter,
    "deepseek-harness": DeepSeekHarnessAdapter,
}


def get_adapter(runtime: str = "antigravity") -> BaseAdapter:
    """Resolve adapter by runtime name, defaulting to Antigravity."""
    key = runtime.strip().lower()
    adapter_cls = ADAPTERS.get(key, AntigravityAdapter)
    return adapter_cls()


def can_ask(runtime: str) -> bool:
    """True when this runtime's adapter can hand an ASK decision to the user.

    The single source of truth for the engine and the predicates: capability is a property of
    the adapter, not a list of runtime names kept somewhere else. See
    [bug--dsh-tool-name-map-and-ask-capability].
    """
    return bool(getattr(get_adapter(runtime), "ask_capable", False))
