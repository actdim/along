#!/usr/bin/env python3
"""alongkit.exceptions - Central Domain Exception Hierarchy for Along Protocol."""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

from typing import Optional


class AlongError(Exception):
    """Base class for all Along domain errors."""
    pass


class CommandError(AlongError):
    """Raised when a CLI command or lifecycle handler fails.

    Attributes:
        message: Human-readable error message (without '[Error]' prefix).
        exit_code: Process exit code (default: 1).
        usage: Optional single-line usage string displayed after the error.
    """

    def __init__(self, message: str, exit_code: int = 1, usage: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code
        self.usage = usage


class ValidationError(CommandError):
    """Raised on invalid CLI arguments, options, or entity names (exit code 2)."""

    def __init__(self, message: str, usage: Optional[str] = None, exit_code: int = 2):
        super().__init__(message, exit_code=exit_code, usage=usage)

