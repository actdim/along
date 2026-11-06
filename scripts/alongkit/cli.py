#!/usr/bin/env python3
"""
alongkit.cli - The `along` console entry point.

Deliberately thin: it locates `along_exec.py`, the existing command router, and runs
it in-process. Duplicating the router's dispatch table here would recreate exactly the
divergence this package exists to remove.

`along_exec.py` is resolved through `repo.resolve_tool_script`, so the same command
works from a source checkout, from a global file install in `~/.along/bin/`, and from
a wheel where the engines ship inside the package as `alongkit/engines/`.

Rewriting the nineteen `SKILL.md` files onto this command is tracked separately as
`[bug--skill-commands-reference-missing-script-paths]`; until then both invocations
work and neither is deprecated.
"""

from __future__ import annotations

import os
import runpy
import sys
from typing import List, Optional, Sequence, Tuple


if __name__ == "__main__" and not __package__:
    _parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from alongkit import repo
    from alongkit.version import CURRENT_PROTOCOL_VERSION
else:
    from . import repo
    from .version import CURRENT_PROTOCOL_VERSION

ROUTER = "along_exec.py"


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


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the Along command router with `argv`, returning its exit code."""
    args: List[str] = list(argv if argv is not None else sys.argv[1:])

    target_dir, remaining = _handle_chdir_options(args)
    if target_dir is not None:
        if not os.path.isdir(target_dir):
            print(f"[Error] Target directory does not exist: {target_dir}", file=sys.stderr)
            return 2
        try:
            os.chdir(target_dir)
        except OSError as exc:
            print(f"[Error] Cannot change directory to '{target_dir}': {exc}", file=sys.stderr)
            return 2
        args = remaining

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
