#!/usr/bin/env python3
"""
alongkit.bootstrap - Make third-party dependencies available to a directly invoked engine.

Along engines are invoked three ways:

1. `python scripts/along_exec.py ...` inside the source repository;
2. `python ~/.along/bin/along_exec.py ...` after a global install, which is a flat
   file copy with no virtual environment attached;
3. `along <subcommand>` through the console entry point, where the dependencies were
   resolved at install time and nothing here is needed.

Cases 1 and 2 can start under an interpreter that has no `ruamel.yaml`. `ensure_deps()`
re-executes the current script under `uv run` with the declared dependencies, which is
one shared implementation instead of a PEP 723 block copy-pasted into twelve files that
would then drift apart.

The re-exec happens at most once, guarded by an environment marker, so a failure to
import after bootstrapping surfaces as a real error rather than an execution loop.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Iterable, List, Sequence

#: Runtime dependencies of the engines. `pyproject.toml` is the source of truth;
#: this list mirrors it for the direct-invocation bootstrap and is asserted equal
#: to it by the test suite.
RUNTIME_DEPENDENCIES: tuple = ("ruamel.yaml>=0.18",)

#: Set in the child environment before re-executing, to make the bootstrap idempotent.
GUARD_ENV = "ALONGKIT_BOOTSTRAPPED"

_INSTALL_HINT = (
    "Along needs the `ruamel.yaml` package to read entity front-matter.\n"
    "Install the toolchain (recommended):\n"
    "    uv tool install actdim-along\n"
    "Or add the dependency to the current interpreter:\n"
    "    python -m pip install \"ruamel.yaml>=0.18\""
)


class MissingDependency(RuntimeError):
    """A required third-party package is absent and could not be bootstrapped."""

    def __init__(self, module: str):
        super().__init__(f"missing required package `{module}`.\n{_INSTALL_HINT}")
        self.module = module


def have_deps(modules: Iterable[str] = ("ruamel.yaml",)) -> bool:
    """True when every named module can be imported."""
    import importlib.util

    for module in modules:
        try:
            if importlib.util.find_spec(module) is None:
                return False
        except (ImportError, ValueError):
            return False
    return True


def ensure_deps(dependencies: Sequence[str] = RUNTIME_DEPENDENCIES,
                modules: Sequence[str] = ("ruamel.yaml",)) -> None:
    """Guarantee `modules` are importable, re-executing under `uv run` if they are not.

    Returns normally when the dependencies are already present. Otherwise the current
    process is replaced by an equivalent `uv run` invocation and never returns. When
    `uv` is unavailable, exits with code 2 and an actionable message: a missing
    dependency is a setup error, not a crash to be reported as an Along defect.
    """
    if have_deps(modules):
        return

    if os.environ.get(GUARD_ENV) == "1":
        print(f"[Error] {MissingDependency(modules[0])}", file=sys.stderr)
        sys.exit(2)

    uv = shutil.which("uv")
    script = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ""
    if not uv or not script or not os.path.isfile(script):
        print(f"[Error] {MissingDependency(modules[0])}", file=sys.stderr)
        sys.exit(2)

    command: List[str] = [uv, "run", "--quiet"]
    for spec in dependencies:
        command += ["--with", spec]
    command += [script, *sys.argv[1:]]

    env = dict(os.environ)
    env[GUARD_ENV] = "1"
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")

    print(f"-> [Along] resolving dependencies via uv: {' '.join(dependencies)}",
          file=sys.stderr)
    try:
        completed = subprocess.run(command, env=env)
    except OSError as exc:
        print(f"[Error] uv could not start: {exc}\n{_INSTALL_HINT}", file=sys.stderr)
        sys.exit(2)
    sys.exit(completed.returncode)


def require(module: str):
    """Import `module`, raising MissingDependency with install instructions instead of ImportError."""
    import importlib

    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise MissingDependency(module) from exc
