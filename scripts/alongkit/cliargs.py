#!/usr/bin/env python3
"""
alongkit.cliargs - Dependency-free CLI argument parsing and normalization helpers.

Extracts global CLI options (such as -C / --chdir) before toolchain command dispatch.
Imports only standard library modules to ensure early CLI launcher stability.
"""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

import os
import sys
from typing import List, Optional, Tuple


def _handle_chdir_options(args: List[str]) -> Tuple[Optional[str], List[str]]:
    """Scan and extract leading -C <dir> and --chdir <dir> options, returning (target_dir, remaining_args)."""
    target: Optional[str] = None
    idx = 0
    while idx < len(args):
        arg = args[idx]
        if arg in ("-C", "--chdir"):
            if idx + 1 >= len(args):
                print(f"[Error] Option '{arg}' requires a directory argument.", file=sys.stderr)
                sys.exit(2)
            dir_val = args[idx + 1]
            target = os.path.normpath(dir_val) if target is None else os.path.normpath(os.path.join(target, dir_val))
            idx += 2
            continue
        elif arg.startswith("-C") and len(arg) > 2:
            dir_val = arg[2:]
            target = os.path.normpath(dir_val) if target is None else os.path.normpath(os.path.join(target, dir_val))
            idx += 1
            continue
        elif arg.startswith("--chdir="):
            dir_val = arg.split("=", 1)[1]
            target = os.path.normpath(dir_val) if target is None else os.path.normpath(os.path.join(target, dir_val))
            idx += 1
            continue
        else:
            break
    return target, args[idx:]

