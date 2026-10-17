#!/usr/bin/env python3
"""
alongkit.hooks.shellparse - Split a shell command line into segments and words.

Gates do not classify commands as read-only or writing: that is not decidable from the text
(any interpreter can write, delete or call the network). This module only splits a command
on control operators so that a gate can match an explicit form, such as `rm -r <path>`, in
each segment. [debt--gate-simplification]

1. The command is split on `;`, `&&`, `||`, `|`, a single `&` (background in POSIX shells,
   a command separator in cmd.exe) and newlines outside quotes. An `&` that belongs to a
   redirection (`2>&1`, `&>file`) does not split.
2. A command substitution (`$(...)`, backticks) or arithmetic expansion stands in as the
   word `SUBST`; its value is unknown before the command runs.
3. Script blocks inside balanced braces `{ ... }` are not split.
"""

from __future__ import annotations

import shlex
from typing import List, Optional, Tuple

#: Placeholder word for a command substitution or arithmetic expansion.
SUBSTITUTION = "SUBST"


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


def _arithmetic_expansion(command: str, i: int) -> Optional[Tuple[str, int]]:
    """(inner expression, index after closing '))') for bash arithmetic expansion '$((...))';
    None when unterminated."""
    if not command.startswith("$((", i):
        return None
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
                return command[i + 3:j - 1], j + 1
        j += 1
    return None


def split_segments(command: str) -> Optional[List[str]]:
    """Split on control operators outside quotes; substitutions become `SUBST`.

    None when the command cannot be split reliably (unbalanced quotes, braces or
    substitutions)."""
    segments: List[str] = []
    buf: List[str] = []
    quote = ""
    brace_depth = 0
    i = 0
    n = len(command)
    while i < n:
        ch = command[i]
        if quote != "'":
            if command.startswith("$((", i):
                arith = _arithmetic_expansion(command, i)
                if arith is None:
                    return None
                buf.append(SUBSTITUTION)
                i = arith[1]
                continue
            if ch == "`" or command.startswith("$(", i):
                sub = _substitution(command, i)
                if sub is None:
                    return None
                buf.append(SUBSTITUTION)
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

        if ch == "{":
            brace_depth += 1
            buf.append(ch)
            i += 1
            continue
        if ch == "}":
            if brace_depth > 0:
                brace_depth -= 1
            buf.append(ch)
            i += 1
            continue

        if brace_depth == 0:
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
    if quote or brace_depth != 0:
        return None
    segments.append("".join(buf))
    return [s.strip() for s in segments if s.strip()]


def words(segment: str) -> Optional[List[str]]:
    """Words of one segment with surrounding quotes removed; None when quoting is broken.

    Non-POSIX splitting keeps Windows backslashes in paths intact."""
    try:
        raw = shlex.split(segment, posix=False)
    except ValueError:
        return None
    return [t.strip("'\"") for t in raw]
