#!/usr/bin/env python3
"""
alongkit.commands - Modular CLI command routers and argparse subparsers.
[debt--along-exec-argparse-migration]
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: python .along/scripts/test.py"
    )

from .decision import handle_decision_command
from .issue import handle_issue_command
from .milestone import handle_milestone_command
from .scratch import handle_scratch_command
from .session import handle_session_command
from .worktree import handle_worktree_command

__all__ = [
    "handle_decision_command",
    "handle_issue_command",
    "handle_milestone_command",
    "handle_scratch_command",
    "handle_session_command",
    "handle_worktree_command",
]
