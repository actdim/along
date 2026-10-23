#!/usr/bin/env python3
"""alongkit.runner - Process supervisor and runtime adapters for agent execution."""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

from typing import Any, Dict, Type

from .antigravity import AntigravityRunner
from .base import BaseRunner, RunResult
from .claude import ClaudeCodeRunner
from .codex import CodexRunner
from .generic import GenericCliRunner
from .opencode import OpenCodeRunner
from .stream import ChunkedStreamSupervisor

RUNNER_MAP: Dict[str, Type[BaseRunner]] = {
    "claude": ClaudeCodeRunner,
    "claude-code": ClaudeCodeRunner,
    "codex": CodexRunner,
    "opencode": OpenCodeRunner,
    "generic": GenericCliRunner,
    "antigravity": AntigravityRunner,
    "agy": AntigravityRunner,
}


def get_runner(runtime: str, **kwargs: Any) -> BaseRunner:
    """Instantiate and configure a runtime runner adapter by identifier."""
    key = str(runtime).lower().strip()
    runner_cls = RUNNER_MAP.get(key)
    if not runner_cls:
        valid_runtimes = sorted(set(RUNNER_MAP.keys()))
        raise ValueError(f"Unknown runtime '{runtime}'. Expected one of: {valid_runtimes}")
    return runner_cls(**kwargs)


__all__ = [
    "AntigravityRunner",
    "BaseRunner",
    "ChunkedStreamSupervisor",
    "ClaudeCodeRunner",
    "CodexRunner",
    "GenericCliRunner",
    "OpenCodeRunner",
    "RunResult",
    "get_runner",
]
