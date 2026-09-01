#!/usr/bin/env python3
"""
alongkit.cli - The `along` console entry point.

Deliberately thin: it locates `along_exec.py`, the existing command router, and runs
it in-process. Duplicating the router's dispatch table here would recreate exactly the
divergence this package exists to remove.

`along_exec.py` is resolved through `repo.resolve_tool_script`, so the same command
works from a source checkout, from a global file install in `~/.along/bin/`, and from
a wheel where the engines ship inside the package as `alongkit/engines/`.

Rewriting the eighteen `SKILL.md` files onto this command is tracked separately as
`[bug--skill-commands-reference-missing-script-paths]`; until then both invocations
work and neither is deprecated.
"""

from __future__ import annotations

import runpy
import sys
from typing import List, Optional, Sequence

from . import repo
from .version import CURRENT_PROTOCOL_VERSION

ROUTER = "along_exec.py"


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the Along command router with `argv`, returning its exit code."""
    args: List[str] = list(argv if argv is not None else sys.argv[1:])

    if args and args[0] in ("--version", "-V"):
        print(f"along {CURRENT_PROTOCOL_VERSION}")
        return 0

    router = repo.resolve_tool_script(ROUTER, repo.find_repo_root())
    if not router:
        searched = "\n".join(f"    {path}" for path in repo.tool_search_path(repo.find_repo_root()))
        print(
            f"[Error] cannot locate {ROUTER}. Searched:\n{searched}\n"
            "Reinstall the toolchain (`uv tool install actdim-along`) or run the engine "
            "directly from a source checkout.",
            file=sys.stderr,
        )
        return 2

    sys.argv = [router, *args]
    try:
        runpy.run_path(router, run_name="__main__")
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
