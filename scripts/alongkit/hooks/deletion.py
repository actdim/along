#!/usr/bin/env python3
"""
alongkit.hooks.deletion - Narrow check for explicit recursive deletes and history rewrites.

Only these forms are recognised, segment by segment (`shellparse.split_segments`):

- `rm -r` / `rm -rf` / `rm --recursive`, `Remove-Item -Recurse` (`ri`, PowerShell `rm`),
  `del /s` / `erase /s`, `rd /s` / `rmdir /s`;
- `git clean -f`, `git reset --hard`, `git push --force` (`-f`, `--force-with-lease`).

A delete is held when a target is empty, cannot be expanded before the command runs (a
variable, a command substitution), lies outside the repository (the system temp directory
excepted), is the repository itself, or holds work git cannot give back (untracked or
modified files, `git status --porcelain`). `git reset --hard` is held when tracked files are
modified, `git clean` when its dry run would remove something, `git push --force` always.

Everything else passes: scripts and other tools are out of reach by design, the container
covers them (ADR docker-isolation-now-gvisor-later). [debt--gate-simplification]
"""

from __future__ import annotations

import os
import re
import tempfile
from typing import List, Optional, Sequence, Tuple

from .. import proc, repo
from . import shellparse

_VAR_RE = re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?|\$env:[A-Za-z_][A-Za-z0-9_]*|%[A-Za-z_][A-Za-z0-9_]*%",
                     re.IGNORECASE)
_GLOB_RE = re.compile(r"[*?\[]")
_CMD_SWITCH_RE = re.compile(r"^/[a-z](?::\S*)?$", re.IGNORECASE)

#: PowerShell Remove-Item parameters whose value is not a target.
_PS_VALUE_PARAMS = frozenset({"-include", "-exclude", "-filter", "-credential", "-stream"})
_PS_PATH_PARAMS = frozenset({"-path", "-literalpath", "-lp", "-pspath"})
_GIT_GLOBAL_VALUE_OPTS = frozenset({"-c", "-C", "--git-dir", "--work-tree", "--namespace"})


def _strip_git_globals(words: List[str]) -> List[str]:
    """`git -C x -c k=v reset --hard` -> `[reset, --hard]` (words after `git`)."""
    out = list(words[1:])
    while out and out[0].startswith("-"):
        opt = out.pop(0)
        if opt in _GIT_GLOBAL_VALUE_OPTS and out:
            out.pop(0)
    return out


def _git_cwd(words: List[str], cwd: str) -> str:
    """Working directory a `git -C <dir>` command runs in."""
    for i, word in enumerate(words[1:-1], start=1):
        if word == "-C":
            return os.path.normpath(os.path.join(cwd, words[i + 1]))
    return cwd


def _short_flags(args: Sequence[str]) -> str:
    """Letters of every `-abc` cluster (not `--long`)."""
    return "".join(a[1:] for a in args if a.startswith("-") and not a.startswith("--") and len(a) > 1)


def _recursive_delete_targets(words: List[str]) -> Optional[List[str]]:
    """Targets of a recursive delete, or None when `words` is no recursive delete."""
    if not words:
        return None
    cmd = os.path.basename(words[0]).lower()
    if cmd.endswith(".exe"):
        cmd = cmd[:-4]
    args = words[1:]
    lowered = [a.lower() for a in args]

    if cmd in ("del", "erase", "rd", "rmdir") and "/s" in lowered:
        return [a for a in args if not _CMD_SWITCH_RE.match(a)]

    ps_recurse = any(a.startswith("-rec") for a in lowered)
    if cmd in ("remove-item", "ri") or (cmd in ("rm", "rmdir", "rd", "del", "erase") and ps_recurse):
        if not (ps_recurse or "-r" in lowered):
            return None
        targets: List[str] = []
        skip = False
        for arg, low in zip(args, lowered):
            if skip:
                skip = False
                continue
            if low in _PS_PATH_PARAMS:
                continue
            if low in _PS_VALUE_PARAMS:
                skip = True
                continue
            if arg.startswith("-"):
                continue
            targets.extend(p for p in arg.split(",") if p)
        return targets

    if cmd == "rm":
        if "--recursive" not in lowered and not re.search(r"[rR]", _short_flags(args)):
            return None
        targets = []
        options_done = False
        for arg in args:
            if not options_done and arg == "--":
                options_done = True
                continue
            if not options_done and arg.startswith("-"):
                continue
            targets.append(arg)
        return targets
    return None


def _git_porcelain(cwd: str, *args: str) -> Optional[str]:
    """`git status --porcelain` output for `args`, None outside a work tree or on failure."""
    result = proc.run_capture(["git", "status", "--porcelain", *args], cwd=cwd, check=False)
    return result.stdout if result.ok else None


def _target_problem(raw: str, cwd: str, repo_root: str) -> Optional[str]:
    """Why deleting `raw` recursively is held, or None when it may run."""
    if not raw.strip():
        return "the path is empty"
    if shellparse.SUBSTITUTION in raw:
        return f"'{raw}' holds a command substitution whose value is unknown before the command runs"
    if _VAR_RE.search(raw):
        expanded = os.path.expandvars(re.sub(r"\$env:([A-Za-z_][A-Za-z0-9_]*)", r"$\1", raw, flags=re.IGNORECASE))
        if _VAR_RE.search(expanded):
            return f"'{raw}' holds a variable that cannot be expanded here (an empty one deletes from the parent)"
        raw = expanded
    path = os.path.expanduser(raw)
    glob = _GLOB_RE.search(path)
    if glob:
        # A glob deletes inside its base directory: judge that directory.
        path = os.path.dirname(path[:glob.start()]) or "."
    target = os.path.realpath(os.path.join(cwd, path))
    root = os.path.realpath(repo_root)
    temp = os.path.realpath(tempfile.gettempdir())
    if repo._same_path(target, root) or repo.is_within(root, target):
        return f"'{raw}' is the repository itself" if repo._same_path(target, root) \
            else f"'{raw}' is outside the repository (it contains it)"
    if not repo.is_within(target, root):
        if repo.is_within(target, temp) and not repo._same_path(target, temp):
            return None
        return f"'{raw}' is outside the repository"
    if not os.path.exists(target):
        return None
    status = _git_porcelain(root, "--untracked-files=all", "--", target)
    if status is None:
        return f"'{raw}' is not under git, so nothing could restore it"
    if status.strip():
        first = status.strip().splitlines()[0][3:]
        return f"'{raw}' holds uncommitted work git cannot restore ({first}{', ...' if status.count(chr(10)) > 1 else ''})"
    return None


def _git_problem(words: List[str], cwd: str) -> Optional[Tuple[str, str]]:
    """(why, fix) when a git history-rewriting form is held, else None."""
    sub = _strip_git_globals(words)
    if not sub:
        return None
    gcwd = _git_cwd(words, cwd)
    name, args = sub[0], sub[1:]
    if name == "push" and ("--force" in args or "--force-with-lease" in args
                           or any(a.startswith("--force-with-lease=") for a in args) or "f" in _short_flags(args)):
        return "force-push rewrites remote history", "push without --force, or let the user run it"
    if name == "reset" and "--hard" in args:
        status = _git_porcelain(gcwd, "--untracked-files=no")
        if status is None or status.strip():
            return ("git reset --hard discards modified tracked files",
                    "commit or 'git stash' them first")
        return None
    if name == "clean" and ("--force" in args or "f" in _short_flags(args)):
        dry: List[str] = []
        for arg in args:
            if arg in ("--force", "-i", "--interactive"):
                continue
            if arg.startswith("-") and not arg.startswith("--"):
                arg = "-" + arg[1:].replace("f", "").replace("i", "")
                if arg == "-":
                    continue
            dry.append(arg)
        result = proc.run_capture(["git", "clean", "-n", *dry], cwd=gcwd, check=False)
        if not result.ok or result.stdout.strip():
            listed = result.stdout.strip().splitlines()
            first = listed[0].replace("Would remove ", "") if listed else "untracked files"
            return (f"git clean would delete untracked files ({first}{', ...' if len(listed) > 1 else ''})",
                    "review 'git clean -n' and commit or move what you keep")
    return None


def find_problem(command: str, cwd: str, repo_root: str) -> Optional[str]:
    """One-line reason the command is held, or None when no listed form is at risk."""
    segments = shellparse.split_segments(command)
    if segments is None:
        segments = [command]
    for seg in segments:
        words = shellparse.words(seg)
        if not words:
            continue
        if os.path.basename(words[0]).lower() in ("git", "git.exe"):
            found = _git_problem(words, cwd)
            if found:
                why, fix = found
                return f"DESTRUCTIVE [gate: destructive-command]: '{seg[:120]}': {why}. Fix: {fix}."
            continue
        targets = _recursive_delete_targets(words)
        if targets is None:
            continue
        if not targets:
            return (f"DESTRUCTIVE [gate: destructive-command]: '{seg[:120]}' names no path. "
                    "Fix: name the path to delete.")
        for raw in targets:
            why = _target_problem(raw, cwd, repo_root)
            if why:
                return (f"DESTRUCTIVE [gate: destructive-command]: '{seg[:120]}': {why}. "
                        "Fix: delete a committed or ignored path inside the repository, or let the user run it.")
    return None


__all__: Sequence[str] = ("find_problem",)
