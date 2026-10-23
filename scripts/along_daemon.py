#!/usr/bin/env python3
"""
along_daemon.py - Host runner daemon and Telegram ingress dispatcher.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap

# Ensure runtime dependencies before dispatching commands
bootstrap.ensure_deps()

from alongkit import repo
from alongkit.commands.daemon import handle_daemon_command


def main(argv=None) -> int:
    """CLI entry point for along_daemon standalone engine."""
    args = sys.argv[1:] if argv is None else list(argv)
    repo_root = repo.find_repo_root()
    return handle_daemon_command(repo_root, args)


if __name__ == "__main__":
    sys.exit(main())
