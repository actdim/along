#!/usr/bin/env python3
"""
alongkit.hooks.adapters - Runtime adapter registry and factory.
"""

from __future__ import annotations

from typing import Dict, Type

from .antigravity import AntigravityAdapter
from .base import BaseAdapter

ADAPTERS: Dict[str, Type[BaseAdapter]] = {
    "antigravity": AntigravityAdapter,
    "agy": AntigravityAdapter,
}


def get_adapter(runtime: str = "antigravity") -> BaseAdapter:
    """Resolve adapter by runtime name, defaulting to Antigravity."""
    key = runtime.strip().lower()
    adapter_cls = ADAPTERS.get(key, AntigravityAdapter)
    return adapter_cls()
