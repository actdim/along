#!/usr/bin/env python3
"""
alongkit.commands.common - Common utilities and helpers for CLI command modules.
[debt--along-exec-argparse-migration]
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: python .along/scripts/test.py"
    )

import sys
from typing import List, Optional


def require_entity_name(name: str, usage: str) -> str:
    """Exit 2 when an entity name looks like a flag."""
    if not name or name.startswith("-"):
        print(f"[Error] Invalid name '{name}': entity names cannot start with '-'.", file=sys.stderr)
        print(f"Usage: {usage}", file=sys.stderr)
        sys.exit(2)
    return name


def check_unknown_args(extra: List[str], prog: str) -> None:
    """Exit 2 with an error message when unknown flags or arguments are encountered."""
    if extra:
        print(f"{prog}: error: unrecognized arguments: {' '.join(extra)}", file=sys.stderr)
        sys.exit(2)


def flag_value(args: List[str], flag: str) -> Optional[str]:
    """Extract value of a flag if present."""
    for i, a in enumerate(args):
        if a == flag and i + 1 < len(args):
            return args[i + 1]
    return None
