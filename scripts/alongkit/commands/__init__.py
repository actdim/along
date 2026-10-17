#!/usr/bin/env python3
"""
alongkit.commands - Modular CLI command routers and argparse subparsers.
[debt--along-exec-argparse-migration]
[debt--split-along-exec-and-entities]
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: python .along/scripts/test.py"
    )

from .decision import handle_decision_command
from .doctor import handle_doctor_command
from .gates import handle_gates_command, handle_git_command, handle_lint_command
from .issue import handle_issue_command
from .lifecycle import (
    handle_history_command,
    handle_plan_command,
    handle_start_command,
    handle_status_command,
)
from .milestone import handle_milestone_command
from .ops import (
    handle_budget_command,
    handle_devenv_command,
    handle_patch_command,
    handle_rules_command,
    handle_run_command,
)
from .scratch import handle_scratch_command
from .session import handle_session_command
from .telemetry import handle_telemetry_command
from .worktree import handle_worktree_command

__all__ = [
    "handle_budget_command",
    "handle_decision_command",
    "handle_devenv_command",
    "handle_doctor_command",
    "handle_gates_command",
    "handle_git_command",
    "handle_history_command",
    "handle_issue_command",
    "handle_lint_command",
    "handle_milestone_command",
    "handle_patch_command",
    "handle_plan_command",
    "handle_rules_command",
    "handle_run_command",
    "handle_scratch_command",
    "handle_session_command",
    "handle_start_command",
    "handle_status_command",
    "handle_telemetry_command",
    "handle_worktree_command",
]
