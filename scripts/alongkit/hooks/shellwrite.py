"""
alongkit/hooks/shellwrite.py - Does a shell command write a file with echo / printf?

A quote-aware lexer for [gate: cli_safety]'s "inline shell file writer" rule. It flags only
a real write to a file: `echo ... > path`, `>> path`, `1> path`, `&> path`, or `echo ... |
tee path`. It does not flag `2>/dev/null`, `>/dev/null`, `2>&1`, `&>/dev/null`, `>&2`,
echo to stdout or into a pipe, or a `>` inside quotes (`echo "a -> b"`).
[bug--cli-safety-redirect-false-positive]
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

_WRITERS = frozenset({"echo", "printf", "write-output"})
#: Words that open a clause; the command after them decides.
_LEAD = frozenset({"do", "then", "else", "elif", "if", "while", "until", "{", "(", "!", "time", "command",
                   "builtin", "exec"})
_NULL_TARGETS = frozenset({"/dev/null", "$null", "nul", "/dev/stdout", "/dev/stderr"})
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

Token = Tuple[str, bool]  # (text, is_operator)


def _lex(command: str) -> List[Token]:
    """Words and operators outside quotes; quoted text stays inside its word."""
    tokens: List[Token] = []
    buf: List[str] = []
    quote = ""
    i, n = 0, len(command)

    def flush() -> None:
        if buf:
            tokens.append(("".join(buf), False))
            buf.clear()

    while i < n:
        ch = command[i]
        if quote:
            if ch == "\\" and quote == '"' and i + 1 < n:
                buf.append(command[i:i + 2])
                i += 2
                continue
            buf.append(ch)
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if ch == "\\" and i + 1 < n:
            buf.append(command[i:i + 2])
            i += 2
            continue
        if ch in " \t":
            flush()
            i += 1
            continue
        if ch in ";\n|&()":
            # `&>` / `&>>` is a redirect, `>&` is handled below; `2>&1` reads as one redirect.
            if ch == "&" and command.startswith(">", i + 1):
                flush()
                op = "&>>" if command.startswith(">>", i + 1) else "&>"
                tokens.append((op, True))
                i += len(op)
                continue
            flush()
            op = command[i:i + 2] if command[i:i + 2] in ("&&", "||", ";;") else ch
            tokens.append((op, True))
            i += len(op)
            continue
        if ch == ">" or (ch.isdigit() and command.startswith(">", i + 1) and not buf):
            flush()
            j = i
            fd = ""
            if ch.isdigit():
                fd = ch
                j += 1
            op = ">>" if command.startswith(">>", j) else ">"
            j += len(op)
            if command.startswith("&", j):
                # `>&2`, `2>&1`: duplicates a descriptor, never a file.
                j += 1
                while j < n and (command[j].isdigit() or command[j] == "-"):
                    j += 1
                tokens.append((fd + op + "&", True))
            else:
                tokens.append((fd + op, True))
            i = j
            continue
        buf.append(ch)
        i += 1
    flush()
    return tokens


def _unquote(word: str) -> str:
    if len(word) >= 2 and word[0] == word[-1] and word[0] in ("'", '"'):
        return word[1:-1]
    return word


def _command_word(words: List[str]) -> Optional[str]:
    for word in words:
        bare = _unquote(word).lower()
        if bare in _LEAD or _ASSIGNMENT.match(word):
            continue
        return bare.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return None


def _is_file_target(word: Optional[str]) -> bool:
    return bool(word) and _unquote(word).lower() not in _NULL_TARGETS


def writes_file_with_echo(command: str) -> bool:
    """True when an echo / printf / Write-Output simple command writes its output to a file."""
    tokens = _lex(command or "")
    # Simple commands, each with the pipeline it belongs to.
    pipeline_has_writer = False
    words: List[str] = []
    redirects: List[Tuple[str, Optional[str]]] = []
    pending_redirect: Optional[str] = None

    def finish(next_op: Optional[str]) -> bool:
        nonlocal pipeline_has_writer
        cmd = _command_word(words)
        is_writer = cmd in _WRITERS
        if is_writer:
            for op, target in redirects:
                if op.endswith("&") or op.startswith("2"):
                    continue
                if _is_file_target(target):
                    return True
        if cmd == "tee" and pipeline_has_writer:
            args = [w for w in words[1:] if not _unquote(w).startswith("-")]
            if any(_is_file_target(a) for a in args):
                return True
        pipeline_has_writer = (pipeline_has_writer or is_writer) if next_op == "|" else False
        return False

    for text, is_op in tokens:
        if pending_redirect is not None:
            if is_op:
                redirects.append((pending_redirect, None))
                pending_redirect = None
            else:
                redirects.append((pending_redirect, text))
                pending_redirect = None
                continue
        if is_op and (text.endswith(">") or text.endswith(">>") or text.endswith(">&")):
            if text.endswith("&"):
                redirects.append((text, None))
            else:
                pending_redirect = text
            continue
        if is_op:
            if text in ("(", ")") and not words:
                continue
            if finish(text):
                return True
            words, redirects = [], []
            continue
        words.append(text)
    if pending_redirect is not None:
        redirects.append((pending_redirect, None))
    return finish(None)


class InlineEchoWriter:
    """Duck-typed stand-in for a compiled pattern in `DANGEROUS_CLI_PATTERNS` (`.search`)."""

    pattern = "echo/printf/Write-Output > file (quote-aware)"

    def search(self, command: str) -> bool:
        return writes_file_with_echo(command)


def has_heredoc(command: str) -> bool:
    """True when an unquoted <<WORD (outside arithmetic expansions) has a following heredoc body."""
    if not command or "\n" not in command:
        return False

    i, n = 0, len(command)
    stack: List[str] = []

    while i < n:
        ch = command[i]
        top = stack[-1] if stack else None

        if top == "SQ":
            if ch == "'":
                stack.pop()
            i += 1
            continue

        if top == "DQ":
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == '"':
                stack.pop()
                i += 1
                continue
            if command.startswith("$((", i):
                stack.append("ARITH")
                i += 3
                continue
            if command.startswith("$(", i):
                stack.append("CS_PAREN")
                i += 2
                continue
            if ch == "`":
                stack.append("CS_BACKTICK")
                i += 1
                continue
            i += 1
            continue

        if top == "ARITH":
            if command.startswith("))", i):
                stack.pop()
                i += 2
                continue
            i += 1
            continue

        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == "'":
            stack.append("SQ")
            i += 1
            continue
        if ch == '"':
            stack.append("DQ")
            i += 1
            continue
        if command.startswith("$((", i) or command.startswith("((", i):
            stack.append("ARITH")
            i += 3 if command.startswith("$((", i) else 2
            continue
        if command.startswith("$(", i):
            stack.append("CS_PAREN")
            i += 2
            continue
        if top == "CS_PAREN" and ch == ")":
            stack.pop()
            i += 1
            continue
        if ch == "`":
            if top == "CS_BACKTICK":
                stack.pop()
            else:
                stack.append("CS_BACKTICK")
            i += 1
            continue

        if command.startswith("<<<", i):
            i += 3
            continue

        if command.startswith("<<", i):
            if i > 0 and command[i - 1] == "<":
                i += 2
                continue
            j = i + 2
            if j < n and command[j] in ("-", "~"):
                j += 1
            while j < n and command[j] in (" ", "\t"):
                j += 1
            delim_quote = ""
            if j < n and command[j] in ("'", '"'):
                delim_quote = command[j]
                j += 1
            start_w = j
            while j < n and (command[j].isalnum() or command[j] == "_"):
                j += 1
            if j > start_w:
                if delim_quote and j < n and command[j] == delim_quote:
                    j += 1
                rest = command[j:]
                if "\n" in rest:
                    return True
            i += 2
            continue

        i += 1
    return False


class HeredocWriter:
    """Duck-typed stand-in for a compiled pattern in `DANGEROUS_CLI_PATTERNS` (`.search`)."""

    pattern = "Heredoc syntax (<<EOF)"

    def search(self, command: str) -> bool:
        return has_heredoc(command)
