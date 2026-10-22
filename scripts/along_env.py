#!/usr/bin/env python3
"""
along_env.py - Isolated Docker Environment Manager for Along Protocol.

Provisions, configures, and controls containerized execution sandboxes for
autonomous agent runs on host machines and VPS deployments.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap

# Ensure runtime dependencies before dispatching commands
bootstrap.ensure_deps()

from alongkit import repo
from alongkit.commands.env import handle_env_command


def main(argv=None) -> int:
    """CLI entry point for along_env standalone engine."""
    args = sys.argv[1:] if argv is None else list(argv)
    repo_root = repo.find_repo_root()
    handle_env_command(repo_root, args)
    return 0


if __name__ == "__main__":
    main()
