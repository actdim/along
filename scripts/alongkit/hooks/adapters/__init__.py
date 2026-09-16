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
from .generic import GenericCliAdapter

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
    "opencode": GenericCliAdapter,
    "open-code": GenericCliAdapter,
}


def get_adapter(runtime: str = "antigravity") -> BaseAdapter:
    """Resolve adapter by runtime name, defaulting to Antigravity."""
    key = runtime.strip().lower()
    adapter_cls = ADAPTERS.get(key, AntigravityAdapter)
    return adapter_cls()
