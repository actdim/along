#!/usr/bin/env python3
"""
alongkit.textio - Strict text reads and atomic, line-ending-preserving writes.

Rules this module enforces, because engines here perform read-modify-write over
files a user owns:

- Never read with `errors="ignore"` before rewriting. Dropping undecodable bytes
  and then overwriting the file destroys content silently.
- Preserve the line endings a file already uses. `.gitattributes` declares CRLF for
  `.ps1` and `.bat`; a tool that normalizes to LF as a side effect fights the
  repository configuration and produces diff churn.
- Write atomically (temp file plus replace) so an interrupted run cannot truncate
  a file it was only supposed to edit.
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
import tempfile
from dataclasses import dataclass
from typing import Optional, Tuple

BOM = "\ufeff"


class DecodeSkipped(UnicodeDecodeError):
    """A file is not valid UTF-8 and must be skipped rather than rewritten."""


@dataclass(frozen=True)
class TextFile:
    """A decoded text file plus the byte-level facts needed to rewrite it faithfully."""

    path: str
    text: str
    newline: str
    had_bom: bool

    @property
    def text_without_bom(self) -> str:
        return self.text[1:] if self.text.startswith(BOM) else self.text


def detect_newline(text: str) -> str:
    """Dominant line ending of `text`; LF when the text has none."""
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    cr = text.count("\r") - crlf
    if crlf and crlf >= lf and crlf >= cr:
        return "\r\n"
    if cr and cr > lf:
        return "\r"
    return "\n"


def read_text(path: str, *, strict: bool = True) -> str:
    """Read a UTF-8 text file with line endings preserved verbatim.

    Raises UnicodeDecodeError when the file is not valid UTF-8 and `strict` is set.
    Pass `strict=False` only for read-only inspection that must not fail; never
    before a rewrite.
    """
    errors = "strict" if strict else "replace"
    with open(path, "r", encoding="utf-8", errors=errors, newline="") as handle:
        return handle.read()


def read_text_file(path: str) -> TextFile:
    """Read a file and capture its BOM and line-ending facts for a faithful rewrite."""
    raw = read_text(path, strict=True)
    return TextFile(path=path, text=raw, newline=detect_newline(raw),
                    had_bom=raw.startswith(BOM))


def write_text(path: str, text: str, *, newline: Optional[str] = None,
               atomic: bool = True) -> None:
    """Write `text` to `path` as UTF-8 without BOM.

    `newline=None` writes the string byte for byte, which is what a caller that
    already preserved the original line endings wants. Passing an explicit newline
    translates "\n" to it.
    """
    if newline is None:
        body = text
    else:
        body = text.replace("\r\n", "\n")
        if newline != "\n":
            body = body.replace("\n", newline)
    data = body.encode("utf-8")

    if not atomic:
        with open(path, "wb") as handle:
            handle.write(data)
        return

    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".along-tmp-",
                                    suffix=os.path.basename(path))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def update_text_file(path: str, transform) -> Tuple[bool, str]:
    """Read, transform, and rewrite only when the content actually changed.

    Returns `(changed, new_text)`. Line endings and the absence of a BOM are the
    caller's responsibility inside `transform`; nothing is normalized here.
    """
    original = read_text(path, strict=True)
    updated = transform(original)
    if updated == original:
        return False, original
    write_text(path, updated)
    return True, updated
