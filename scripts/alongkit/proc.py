#!/usr/bin/env python3
"""
alongkit.proc - Subprocess execution with fixed encoding conventions.

Every text-capturing subprocess call in Along goes through `run_capture`.

Why this module exists: `subprocess.run(..., text=True)` without `encoding=`
decodes child output with `locale.getpreferredencoding()`. On a Russian Windows
install that is cp1251, on a Chinese one cp936. A single non-ASCII byte then raises
UnicodeDecodeError inside the reader thread, `run` returns `stdout=None` rather than
failing, and the caller crashes later on a confusing secondary error. The defect was
present at 25+ call sites, which is why the convention is enforced here instead of
being remembered per call.
"""


from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{__name__} is a library module, not a command.\n"
        "Run: along kb-sync   (or: python scripts/along_exec.py kb-sync)"
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )


import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Union

Command = Union[str, Sequence[str]]

#: Child environment overrides that force UTF-8 on both sides of the pipe.
UTF8_CHILD_ENV: Dict[str, str] = {
    "PYTHONIOENCODING": "utf-8",
    # PEP 540: makes a child CPython use UTF-8 for stdio and the filesystem
    # regardless of the host locale.
    "PYTHONUTF8": "1",
}


class ProcessError(RuntimeError):
    """A captured command failed and the caller asked for `check=True`."""

    def __init__(self, result: "Result"):
        self.result = result
        detail = (result.stderr or result.stdout or "").strip()
        suffix = f": {detail.splitlines()[-1]}" if detail else ""
        super().__init__(f"command failed ({result.returncode}): {result.display}{suffix}")


@dataclass(frozen=True)
class Result:
    """Outcome of a captured command. `stdout` and `stderr` are always strings."""

    cmd: Command
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def display(self) -> str:
        if isinstance(self.cmd, str):
            return self.cmd
        return " ".join(str(part) for part in self.cmd)

    @property
    def out(self) -> str:
        """Stdout without surrounding whitespace, the usual form for parsing."""
        return self.stdout.strip()

    def lines(self) -> List[str]:
        """Non-empty stdout lines, stripped."""
        return [ln.strip() for ln in self.stdout.splitlines() if ln.strip()]


def child_env(extra: Optional[Dict[str, str]] = None,
              base: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Environment for a child process, with UTF-8 stdio forced."""
    env = dict(base if base is not None else os.environ)
    env.update(UTF8_CHILD_ENV)
    if extra:
        env.update(extra)
    return env


def run_capture(cmd: Command,
                cwd: Optional[str] = None,
                timeout: Optional[float] = None,
                check: bool = False,
                env: Optional[Dict[str, str]] = None,
                stdin_text: Optional[str] = None,
                shell: bool = False) -> Result:
    """Run `cmd`, capture stdout and stderr as UTF-8 text, never raise on decode.

    Decoding uses `errors="replace"`, so undecodable bytes surface as replacement
    characters instead of destroying the result. A command that cannot be started,
    or that exceeds `timeout`, is reported as a Result with a non-zero returncode
    and the reason in `stderr`; only `check=True` turns a failure into an exception.
    """
    try:
        completed = subprocess.run(
            cmd,
            cwd=cwd,
            shell=shell,
            input=stdin_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=child_env(env),
        )
        result = Result(cmd, completed.returncode,
                       completed.stdout or "", completed.stderr or "")
    except subprocess.TimeoutExpired as exc:
        result = Result(cmd, 124, _as_text(exc.stdout),
                        _as_text(exc.stderr) or f"timed out after {timeout}s")
    except (OSError, ValueError) as exc:
        # Missing executable, bad arguments: a normal outcome for optional tooling.
        result = Result(cmd, 127, "", str(exc))

    if check and not result.ok:
        raise ProcessError(result)
    return result


def run_passthrough(cmd: Command,
                    cwd: Optional[str] = None,
                    env: Optional[Dict[str, str]] = None,
                    shell: bool = False) -> int:
    """Run `cmd` with inherited stdio (no capture) and return its exit code.

    For dispatching to another tool whose output belongs to the user, where
    capturing would hide progress. The UTF-8 child environment still applies.
    """
    try:
        completed = subprocess.run(cmd, cwd=cwd, shell=shell, env=child_env(env))
        return completed.returncode
    except (OSError, ValueError) as exc:
        print(f"[Error] cannot execute {cmd}: {exc}", file=sys.stderr)
        return 127


def run_python(args: Sequence[str], **kwargs) -> Result:
    """`run_capture` with the current interpreter, for invoking sibling engines."""
    return run_capture([sys.executable, *args], **kwargs)


def git(args: Sequence[str], cwd: Optional[str] = None, check: bool = False,
        timeout: Optional[float] = None) -> Result:
    """Run a git command and capture its output."""
    return run_capture(["git", *args], cwd=cwd, check=check, timeout=timeout)


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)
