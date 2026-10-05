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
re-executes the current script under an interpreter that has the declared dependencies,
which is one shared implementation instead of a PEP 723 block copy-pasted into twelve
files that would then drift apart. It prefers a cached environment (`~/.along/venv`,
built once with uv and stamped with the dependency specs) and falls back to
`uv run --with` only when that environment cannot be built. Runtime hooks fire on
every tool use, so re-resolving dependencies per call is too slow to be the default.

The re-exec happens at most once, guarded by an environment marker, so a failure to
import after bootstrapping surfaces as a real error rather than an execution loop. The
marker is cleared as soon as the dependencies are present: it guards one re-exec, not the
whole process tree, so an engine started from a bootstrapped process (an installer running
`install_manifest.py` under a bare interpreter) still bootstraps itself.
See [bug--bootstrap-guard-leaks-to-children].

`ensure_project_env()` serves the repository's own test hook: the suite needs the `dev`
dependency group, which the shared runtime environment deliberately does not carry, so it
re-executes through `uv run --project <root>` instead.
See [bug--test-hook-lacks-dashboard-deps].
"""


from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )


import os
import shutil
import subprocess
import sys
from typing import Iterable, List, Optional, Sequence

#: Runtime dependencies of the engines. `pyproject.toml` is the source of truth;
#: this list mirrors it for the direct-invocation bootstrap and is asserted equal
#: to it by the test suite.
RUNTIME_DEPENDENCIES: tuple = ("ruamel.yaml>=0.18",)

#: Set in the child environment before re-executing, to make the bootstrap idempotent.
GUARD_ENV = "ALONGKIT_BOOTSTRAPPED"

#: The same guard for the `uv run --project` re-exec of `ensure_project_env()`.
PROJECT_GUARD_ENV = "ALONGKIT_PROJECT_ENV"

#: Overrides the location of the cached runtime environment (default `~/.along/venv`).
VENV_ENV = "ALONG_VENV"

#: File inside the cached environment recording the dependency specs it was built with.
_VENV_STAMP = ".along-deps"

#: Upper bound for building the cached environment, in seconds.
_VENV_BUILD_TIMEOUT = 120

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


def runtime_venv_dir() -> str:
    """Location of the cached runtime environment shared by every engine and hook."""
    return os.environ.get(VENV_ENV) or os.path.join(os.path.expanduser("~"), ".along", "venv")


def venv_python(venv_dir: str) -> str:
    """Interpreter path inside a virtual environment."""
    if sys.platform == "win32":
        return os.path.join(venv_dir, "Scripts", "python.exe")
    return os.path.join(venv_dir, "bin", "python")


def _venv_is_current(venv_dir: str, dependencies: Sequence[str]) -> bool:
    """True when `venv_dir` has an interpreter and was built for exactly `dependencies`."""
    stamp = os.path.join(venv_dir, _VENV_STAMP)
    if not os.path.isfile(venv_python(venv_dir)) or not os.path.isfile(stamp):
        return False
    try:
        with open(stamp, "r", encoding="utf-8") as handle:
            return handle.read().strip() == "\n".join(dependencies)
    except OSError:
        return False


def _build_venv(uv: str, venv_dir: str, dependencies: Sequence[str]) -> bool:
    """Build the cached environment with uv; True when a current one exists afterwards.

    The environment is built in a sibling temp directory and renamed into place, so an
    interrupted build (a hook timeout) or a concurrent one never leaves a half-built
    environment at `venv_dir`.
    """
    tmp_dir = f"{venv_dir}.tmp-{os.getpid()}"
    quiet = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
             "timeout": _VENV_BUILD_TIMEOUT, "check": True}
    try:
        os.makedirs(os.path.dirname(venv_dir), exist_ok=True)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        subprocess.run([uv, "venv", "--quiet", "--python", sys.executable, tmp_dir], **quiet)
        subprocess.run([uv, "pip", "install", "--quiet", "--python", venv_python(tmp_dir),
                        *dependencies], **quiet)
        with open(os.path.join(tmp_dir, _VENV_STAMP), "w", encoding="utf-8") as handle:
            handle.write("\n".join(dependencies) + "\n")
        if os.path.isdir(venv_dir):
            # Built for other dependency specs; replace it.
            shutil.rmtree(venv_dir, ignore_errors=True)
        os.replace(tmp_dir, venv_dir)
    except (OSError, subprocess.SubprocessError):
        shutil.rmtree(tmp_dir, ignore_errors=True)
    # A concurrent build may have won the rename; either way, check what is in place.
    return _venv_is_current(venv_dir, dependencies)


def _reexec(command: List[str], missing_exit_code: int, guard: str = GUARD_ENV,
            stdin_data: Optional[bytes] = None) -> None:
    """Run `command` with the `guard` marker set and exit with its return code.

    `stdin_data` replays input this process already consumed (a hook payload).
    """
    env = dict(os.environ)
    env[guard] = "1"
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    try:
        if stdin_data is None:
            completed = subprocess.run(command, env=env)
        else:
            completed = subprocess.run(command, env=env, input=stdin_data)
    except OSError as exc:
        print(f"[Error] could not start {command[0]}: {exc}\n{_INSTALL_HINT}", file=sys.stderr)
        sys.exit(missing_exit_code)
    sys.exit(completed.returncode)


def ensure_deps(dependencies: Sequence[str] = RUNTIME_DEPENDENCIES,
                modules: Sequence[str] = ("ruamel.yaml",),
                missing_exit_code: int = 2, quiet: bool = False,
                stdin_data: Optional[bytes] = None) -> None:
    """Guarantee `modules` are importable, re-executing under `uv run` if they are not.

    Returns normally when the dependencies are already present. Otherwise the current
    process is replaced by an equivalent `uv run` invocation and never returns. When
    `uv` is unavailable, exits with `missing_exit_code` (2 by default) and an actionable
    message: a missing dependency is a setup error, not a crash to be reported as an
    Along defect. Runtime hooks pass 0, because hosts such as Claude Code read exit 2
    as "block the tool", and a setup fault must never block the agent. They also pass
    `quiet` (hook stderr lands in every tool result, so progress notes are noise) and the
    stdin payload they already read, which the re-executed process needs again.
    """
    if have_deps(modules):
        # The marker guarded the re-exec that got us here; descendants start clean.
        os.environ.pop(GUARD_ENV, None)
        return

    if os.environ.get(GUARD_ENV) == "1":
        print(f"[Error] {MissingDependency(modules[0])}", file=sys.stderr)
        sys.exit(missing_exit_code)

    script = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ""
    if not script or not os.path.isfile(script):
        print(f"[Error] {MissingDependency(modules[0])}", file=sys.stderr)
        sys.exit(missing_exit_code)

    # Fast path: a cached environment costs one process spawn, while `uv run --with`
    # re-resolves the dependencies on every call (every hook, every tool use).
    venv_dir = runtime_venv_dir()
    if _venv_is_current(venv_dir, dependencies):
        _reexec([venv_python(venv_dir), script, *sys.argv[1:]], missing_exit_code,
                stdin_data=stdin_data)

    uv = shutil.which("uv")
    if not uv:
        print(f"[Error] {MissingDependency(modules[0])}", file=sys.stderr)
        sys.exit(missing_exit_code)

    if not quiet:
        print(f"-> [Along] building cached runtime {venv_dir} (one-time): {' '.join(dependencies)}",
              file=sys.stderr)
    if _build_venv(uv, venv_dir, dependencies):
        _reexec([venv_python(venv_dir), script, *sys.argv[1:]], missing_exit_code,
                stdin_data=stdin_data)

    command: List[str] = [uv, "run", "--quiet"]
    for spec in dependencies:
        command += ["--with", spec]
    command += [script, *sys.argv[1:]]
    if not quiet:
        print(f"-> [Along] resolving dependencies via uv: {' '.join(dependencies)}",
              file=sys.stderr)
    _reexec(command, missing_exit_code, stdin_data=stdin_data)


def ensure_project_env(project_root: str, modules: Sequence[str]) -> None:
    """Re-execute the current script inside the uv project at `project_root` when `modules` are missing.

    `uv run --project` syncs the project's default dependency groups (`dev`), which is
    where a repository keeps what only its own tooling needs. Returns normally when the
    modules are present, when `uv` or the script cannot be found, or when this process is
    already that re-exec (the caller then degrades, e.g. tests skip). Never exits on its
    own: the runtime bootstrap that usually follows reports what is truly missing.
    """
    if have_deps(modules):
        os.environ.pop(PROJECT_GUARD_ENV, None)
        return
    if os.environ.get(PROJECT_GUARD_ENV) == "1":
        return
    if not os.path.isfile(os.path.join(project_root, "pyproject.toml")):
        return
    script = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ""
    uv = shutil.which("uv")
    if not script or not os.path.isfile(script) or not uv:
        return
    print(f"-> [Along] running in the project environment via uv: {project_root}", file=sys.stderr)
    _reexec([uv, "run", "--quiet", "--project", project_root, "python", script, *sys.argv[1:]],
            missing_exit_code=2, guard=PROJECT_GUARD_ENV)


def require(module: str):
    """Import `module`, raising MissingDependency with install instructions instead of ImportError."""
    import importlib

    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise MissingDependency(module) from exc
