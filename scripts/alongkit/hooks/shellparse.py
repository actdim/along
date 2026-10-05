#!/usr/bin/env python3
"""
alongkit.hooks.shellparse - Segment-aware classification of shell commands as read-only.

The inquiry/plan-approval gate lets read-only inspection and test commands through in every
session phase. It used to decide that by matching the whole command line against prefix or
substring patterns, so `ls && rm -rf src`, `rm -rf src; pytest` and `echo hi > src/a.py`
were all classified as safe reads. This module classifies a command as read-only only when
every segment of it is read-only:

1. The command is split on `;`, `&&`, `||`, `|`, a single `&` (background in POSIX shells,
   a command separator in cmd.exe) and newlines outside quotes. An `&` that belongs to a
   redirection (`2>&1`, `&>file`) does not split.
2. Command substitution (`$(...)` or backticks outside single quotes) is never read-only.
3. An output redirection (`>`, `>>`) outside quotes is a write unless its target is a null
   device (`/dev/null`, `NUL`, `$null`) or a descriptor duplication such as `2>&1`.
4. Each segment, after stripping runner wrappers (`uv run ...`, `poetry run`, `pipenv run`,
   `pdm run`, `hatch run`, `npx`), must start with a known read-only command or test runner.
5. `git` read subcommands are read-only only without flags that write: `--output` on
   `diff`/`log`/`show`, and anything that creates, deletes, renames or reconfigures a branch.
6. `python -c` is read-only only for a single `print(...)` call with no other call inside.

See [bug--safe-command-prefix-bypass] and [bug--shell-classifier-residual-bypasses].
"""

from __future__ import annotations

import ast
import re
import shlex
from typing import List, Optional, Tuple

_NULL_TARGETS = ("/dev/null", "nul", "$null")

#: First words that only read (POSIX and PowerShell/cmd spellings).
_READ_COMMANDS = frozenset({
    "echo", "printf", "cat", "dir", "ls", "type", "head", "tail", "grep", "rg", "which",
    "where", "pwd", "cd", "wc", "stat", "file", "true",
    "cut", "tr", "nl", "basename", "dirname", "realpath", "du", "df", "test", "[", "diff", "cmp",
    "comm", "false",
    "get-childitem", "get-content", "select-string", "get-location", "set-location",
    "write-output", "write-host",
})

_GIT_READ = frozenset({"status", "diff", "log", "branch", "show", "rev-parse", "describe"})
#: `git branch` flags that only list; any other flag, or a bare name, may write.
_GIT_BRANCH_LIST_FLAGS = frozenset({
    "-a", "-r", "-v", "-vv", "-l", "--list", "--all", "--remotes", "--verbose",
    "--show-current", "--no-color", "--color", "--column", "--no-column",
})
_GIT_BRANCH_LIST_VALUE_PREFIXES = ("--format=", "--sort=", "--color=", "--column=")
_ALONG_READ = (
    "test", "status", "doctor", "budget", "context-budget", "kb-search", "scratch state",
    "worktree list", "worktree status", "hook verify",
)
#: `find` primaries that run commands or write files.
_FIND_WRITE = frozenset({
    "-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprint0", "-fprintf", "-fls",
})
#: Shell keywords that open a clause; the command after them decides.
_SHELL_LEAD_KEYWORDS = frozenset({"do", "then", "else", "elif", "if", "while", "until", "{"})
#: Shell keywords that close a clause and run nothing themselves.
_SHELL_CLOSE_KEYWORDS = frozenset({"done", "fi", "}"})
#: A sed script command that writes a file (`w`, `W`) or executes one (`e`, `s///e`).
_SED_WRITE = re.compile(r"[wWe](\s|$|;|\})")
_WRAPPER_OPTS_WITH_VALUE = frozenset({
    "--with", "--python", "-p", "--project", "--directory", "--extra", "--group", "--env-file",
    "--from", "--package",
})


def _substitution(command: str, i: int) -> Optional[Tuple[str, int]]:
    """(inner command, index after it) for the `$(...)` or backquote starting at `i`; None when
    it is unterminated."""
    if command[i] == "`":
        end = command.find("`", i + 1)
        return (command[i + 1:end], end + 1) if end != -1 else None
    depth = 0
    quote = ""
    j = i + 1
    while j < len(command):
        ch = command[j]
        if quote:
            if ch == quote:
                quote = ""
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return command[i + 2:j], j + 1
        j += 1
    return None


def split_segments(command: str) -> Optional[List[str]]:
    """Split on control operators outside quotes. Command substitutions are classified on their
    own and stand in as a plain word when read-only. None when the command is not simple
    enough to classify (unbalanced quotes, a substitution that may write)."""
    segments: List[str] = []
    buf: List[str] = []
    quote = ""
    i = 0
    n = len(command)
    while i < n:
        ch = command[i]
        if (ch == "`" or command.startswith("$(", i)) and quote != "'":
            sub = _substitution(command, i)
            if sub is None or not is_read_only_command(sub[0]):
                return None
            buf.append("SUBST")
            i = sub[1]
            continue
        if quote:
            if ch == quote:
                quote = ""
            buf.append(ch)
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            i += 1
            continue
        two = command[i:i + 2]
        if two in ("&&", "||"):
            segments.append("".join(buf))
            buf = []
            i += 2
            continue
        if ch in (";", "|", "\n", "\r"):
            segments.append("".join(buf))
            buf = []
            i += 1
            continue
        if ch == "&" and not (buf and buf[-1] == ">") and not command.startswith("&>", i):
            segments.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    if quote:
        return None
    segments.append("".join(buf))
    return [s.strip() for s in segments if s.strip()]


def _has_write_redirect(segment: str) -> bool:
    """True when the segment redirects output to a real file."""
    quote = ""
    i = 0
    n = len(segment)
    while i < n:
        ch = segment[i]
        if quote:
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            i += 1
            continue
        if ch == ">":
            j = i + 1
            if j < n and segment[j] == ">":
                j += 1
            if j < n and segment[j] == "&":
                i = j + 1
                continue
            rest = segment[j:].lstrip()
            target = rest.split()[0] if rest.split() else ""
            if target.strip("'\"").lower() not in _NULL_TARGETS:
                return True
            i = j
            continue
        i += 1
    return False


def _tokens(segment: str) -> Optional[List[str]]:
    try:
        raw = shlex.split(segment, posix=False)
    except ValueError:
        return None
    return [t.strip("'\"") for t in raw]


def _strip_wrappers(tokens: List[str]) -> List[str]:
    """Drop `uv run [opts]`, `poetry run`, `npx`, ... and environment assignments."""
    changed = True
    while changed and tokens:
        changed = False
        while tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
            tokens = tokens[1:]
            changed = True
        if len(tokens) >= 2 and tokens[0].lower() in ("uv", "poetry", "pipenv", "pdm", "hatch") \
                and tokens[1].lower() == "run":
            tokens = tokens[2:]
            while tokens and tokens[0].startswith("-"):
                opt = tokens[0].split("=", 1)[0]
                tokens = tokens[2:] if (opt in _WRAPPER_OPTS_WITH_VALUE and "=" not in tokens[0]) else tokens[1:]
            changed = True
        elif tokens and tokens[0].lower() == "npx":
            tokens = tokens[1:]
            changed = True
    return tokens


def _is_python(word: str) -> bool:
    base = word.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return bool(re.match(r"^(python\d*(\.\d+)?|py)(\.exe)?$", base))


def _git_is_read_only(rest: List[str]) -> bool:
    """`rest` are the lowercased words after `git`."""
    if not rest or rest[0] not in _GIT_READ:
        return False
    sub, args = rest[0], rest[1:]
    if any(a == "--output" or a.startswith("--output=") for a in args):
        return False
    if sub == "branch":
        listing = any(a in ("-l", "--list") for a in args)
        for a in args:
            if a in _GIT_BRANCH_LIST_FLAGS or a.startswith(_GIT_BRANCH_LIST_VALUE_PREFIXES):
                continue
            if not a.startswith("-") and listing:
                continue  # pattern for `--list`
            return False
    return True


def _python_c_is_read_only(code: str) -> bool:
    """A single `print(...)` whose arguments call nothing else."""
    try:
        tree = ast.parse(code.strip(), mode="exec")
    except (SyntaxError, ValueError):
        return False
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Expr):
        return False
    call = tree.body[0].value
    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "print"):
        return False
    return sum(isinstance(node, ast.Call) for node in ast.walk(call)) == 1


def _sed_is_read_only(args: List[str]) -> bool:
    """`sed` without in-place editing, script files, or write/execute script commands."""
    scripts: List[str] = []
    positional: List[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-e", "--expression"):
            if i + 1 >= len(args):
                return False
            scripts.append(args[i + 1])
            i += 2
            continue
        if arg.startswith("--expression="):
            scripts.append(arg.split("=", 1)[1])
        elif arg.startswith("--in-place") or arg in ("-f", "--file") or arg.startswith("--file="):
            return False
        elif arg.startswith("-") and not arg.startswith("--") and len(arg) > 1:
            if "i" in arg or "f" in arg:
                return False
        elif not arg.startswith("-"):
            positional.append(arg)
        i += 1
    if not scripts:
        if not positional:
            return False
        scripts.append(positional[0])
    return not any(_SED_WRITE.search(s) for s in scripts)


def _segment_is_read_only(segment: str) -> bool:
    if _has_write_redirect(segment):
        return False
    tokens = _tokens(segment)
    if not tokens:
        return tokens is not None
    tokens = _strip_wrappers(tokens)
    while tokens and tokens[0].lower() in _SHELL_LEAD_KEYWORDS:
        tokens = _strip_wrappers(tokens[1:])
    if not tokens:
        return True
    first = tokens[0].lower()
    rest = [t.lower() for t in tokens[1:]]

    if first in _SHELL_CLOSE_KEYWORDS:
        return not rest
    if first == "for":
        # `for NAME in WORDS`: substitutions among the words were already classified.
        return len(rest) >= 1 and (len(rest) == 1 or rest[1] == "in")
    if first in _READ_COMMANDS:
        return True
    if first == "sed":
        return _sed_is_read_only(tokens[1:])
    if first == "find":
        return not any(t in _FIND_WRITE for t in rest)
    if first == "sort":
        return not any(t.startswith("--output") or (t.startswith("-") and not t.startswith("--")
                                                    and "o" in t) for t in rest)
    if first == "uniq":
        return len([t for t in rest if not t.startswith("-")]) <= 1
    if first == "git":
        return _git_is_read_only(rest)
    if first == "along" or first.endswith("along_exec.py"):
        joined = " ".join(rest)
        return any(joined == sub or joined.startswith(sub + " ") for sub in _ALONG_READ)
    if first in ("pytest", "along-test", "along_test"):
        return True
    if first in ("npm", "pnpm", "yarn"):
        return rest[:1] == ["test"] or rest[:2] == ["run", "test"] or rest[:2] == ["run", "test:quiet"]
    if first in ("cargo", "dotnet", "go"):
        return rest[:1] == ["test"]
    if _is_python(first):
        if not rest:
            return False
        if rest[0] in ("-v", "--version"):
            return True
        if rest[0] == "-c":
            return len(tokens) == 3 and _python_c_is_read_only(tokens[2])
        if rest[0] == "-m":
            return len(rest) > 1 and rest[1] in ("pytest", "unittest")
        script = rest[0].replace("\\", "/")
        if script.endswith(".along/scripts/test.py"):
            return True
        if script.endswith("along_exec.py"):
            joined = " ".join(rest[1:])
            return any(joined == sub or joined.startswith(sub + " ") for sub in _ALONG_READ)
        return False
    return False


#: Along subcommands that only move Along's own state (entities, blackboards, projections).
#: The plan gate lets them through so an agent can create and start an issue before any plan
#: exists; `commit`, `bump`, `hook install` and `update` are not among them.
_ALONG_STATE = (
    "issue", "start", "scratch", "plan", "decision", "milestone", "session", "wrap",
    "kb-sync", "kb sync", "glossary", "risk", "spike", "checklist",
)


def _along_subcommand(tokens: List[str]) -> Optional[str]:
    """Words after `along` / `along_exec.py` when the segment invokes the Along CLI."""
    tokens = _strip_wrappers(tokens)
    if not tokens:
        return None
    first = tokens[0].lower()
    if first == "along" or first.endswith("along_exec.py") or first.endswith("along.ps1"):
        return " ".join(t.lower() for t in tokens[1:])
    if _is_python(first) and len(tokens) > 1 and tokens[1].replace("\\", "/").lower().endswith("along_exec.py"):
        return " ".join(t.lower() for t in tokens[2:])
    return None


def along_subcommand(segment: str) -> Optional[str]:
    """Lower-cased words after the Along CLI in one command segment, or None if it is not one."""
    tokens = _tokens(segment)
    return _along_subcommand(tokens) if tokens else None


def is_along_state_command(command: str) -> bool:
    """True when every segment runs an Along state subcommand (or is read-only)."""
    segments = split_segments(command or "")
    if not segments:
        return False
    for seg in segments:
        if _has_write_redirect(seg):
            return False
        tokens = _tokens(seg)
        sub = _along_subcommand(tokens) if tokens else None
        if sub is not None and any(sub == s or sub.startswith(s + " ") for s in _ALONG_STATE):
            continue
        if not _segment_is_read_only(seg):
            return False
    return True


def is_read_only_command(command: str) -> bool:
    """True only when every segment of `command` is a read-only inspection or a test run."""
    if not command or not command.strip():
        return True
    segments = split_segments(command)
    if segments is None:
        return False
    return all(_segment_is_read_only(seg) for seg in segments)


def classify(command: str) -> Tuple[bool, List[str]]:
    """(read_only, segments) - for diagnostics and tests."""
    segments = split_segments(command) or []
    return is_read_only_command(command), segments
