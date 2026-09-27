#!/usr/bin/env python3
"""alongkit.runner - Process supervisor and stream chunking for agent runtime sessions."""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

from .antigravity import AntigravityRunner
from .stream import ChunkedStreamSupervisor

__all__ = ["AntigravityRunner", "ChunkedStreamSupervisor"]
