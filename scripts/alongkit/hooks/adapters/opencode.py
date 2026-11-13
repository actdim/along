#!/usr/bin/env python3
"""
alongkit.hooks.adapters.opencode - OpenCode runtime hook adapter.

Handles lifecycle events from the Along OpenCode plugin (`tool.execute.before`,
`tool.execute.after`, `shell.env`).
"""

from __future__ import annotations

from .generic import GenericCliAdapter


class OpenCodeAdapter(GenericCliAdapter):
    """Adapter for OpenCode agent harness and Along plugin."""

    runtime_name: str = "opencode"

    def __init__(self) -> None:
        super().__init__(runtime_name="opencode")
