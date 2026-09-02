#!/usr/bin/env python3
"""
alongkit.frontmatter - The single YAML front-matter reader and writer.

Backed by `ruamel.yaml` in round-trip mode. Nothing here parses YAML by hand.

Before this module the repository carried four hand-rolled parsers
(`along_kb_sync.py`, `along_kb_search.py`, `migrate_protocol.py`,
`dashboard/core/collector.py`). They shared two defects that lost user data:

1. A line without a colon was skipped, so a block sequence

       tags:
         - protocol
         - retrieval

   parsed to `{"tags": ""}`, and the following `dump_frontmatter` wrote the key back
   with its items gone.
2. The writer emitted `f"{key}: {value}"` with no quoting, so an ordinary title
   containing a colon produced a block that is not valid YAML. Six such files existed
   in this repository when this module was written; strict readers, including the
   dashboard's own PyYAML path, could not parse any of them.

Why a real library rather than a subset parser: YAML is a widely implemented format,
front-matter is read by tools that are not Along (GitHub, static site generators,
`gray-matter`), and a bespoke parser has to be kept correct by tests forever for no
gain. `ruamel.yaml` is chosen over `pyyaml` because round-trip mode preserves
comments, key order, and quoting style, which is what makes a read-modify-write over
a file the user owns safe. See ADR-2026-09-01--frontmatter-on-ruamel-yaml.

Contract:

- `parse()` returns plain Python and raises on invalid YAML. Callers that rewrite a
  file must let that propagate: refusing to write is the correct response to metadata
  that cannot be understood.
- `try_parse()` is the tolerant form, for read-only scanners that must not abort a
  repository-wide search because one file is malformed.
- `update()` edits named keys and preserves everything else, including comments, key
  order, block sequences, and the file's line endings.
- `render()` builds a new document and re-parses its own output before returning it.
"""


from __future__ import annotations
if __name__ == "__main__":
    raise SystemExit(
        f"{__name__} is a library module, not a command.\n"
        "Run: along kb-sync   (or: python scripts/along_exec.py kb-sync)"
    )


import datetime
import io
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from . import bootstrap

BOM = "\ufeff"

#: Leading front-matter block. A UTF-8 BOM is tolerated because Windows PowerShell 5.1
#: emits one from `Set-Content -Encoding utf8`, `Out-File -Encoding utf8`, and `>`.
BLOCK_RE = re.compile(
    r"^(" + BOM + r")?"
    r"(---[ \t]*(?:\r\n|\n))"
    r"(.*?)"
    r"((?:\r\n|\n)?---[ \t]*(?:\r\n|\n|\Z))",
    re.DOTALL,
)

#: An ISO calendar date, the only date form the protocol uses.
ISO_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


class FrontmatterError(ValueError):
    """Front-matter exists but cannot be parsed or emitted.

    Never raised for a document that simply has no front-matter block.
    """

    def __init__(self, message: str, line: Optional[int] = None, path: Optional[str] = None):
        self.line = line
        self.path = path
        if path and line:
            location = f"{path}:{line}: "
        elif path:
            location = f"{path}: "
        elif line:
            location = f"line {line}: "
        else:
            location = ""
        super().__init__(f"{location}{message}")


@dataclass(frozen=True)
class Block:
    """The lexical parts of a front-matter block, enough to rebuild a file verbatim."""

    bom: str
    open_delim: str
    raw: str
    close_delim: str
    body: str
    newline: str

    @property
    def had_bom(self) -> bool:
        return bool(self.bom)


def split(content: str) -> Optional[Block]:
    """Split `content` into its front-matter parts, or None when it has no block."""
    match = BLOCK_RE.match(content)
    if not match:
        return None
    bom = match.group(1) or ""
    open_delim, raw, close_delim = match.group(2), match.group(3), match.group(4)
    newline = "\r\n" if "\r\n" in open_delim or "\r\n" in close_delim else "\n"
    return Block(bom=bom, open_delim=open_delim, raw=raw, close_delim=close_delim,
                 body=content[match.end():], newline=newline)


def has_frontmatter(content: str) -> bool:
    """True when `content` opens with a front-matter block, parseable or not."""
    return BLOCK_RE.match(content) is not None


# ---------------------------------------------------------------------------
# ruamel.yaml plumbing
# ---------------------------------------------------------------------------

def _yaml():
    """A round-trip YAML instance configured for Along front-matter.

    `width` is effectively unlimited: front-matter is one key per line, and wrapping
    would turn a long `target_issues` list into a multi-line fold that diffs badly.
    Sequence indentation matches the style already used in the repository.
    """
    module = bootstrap.require("ruamel.yaml")
    yaml = module.YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.width = 1 << 20
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def _error_line(exc: Exception) -> Optional[int]:
    """File line number for a ruamel error, accounting for the opening delimiter."""
    mark = getattr(exc, "problem_mark", None) or getattr(exc, "context_mark", None)
    if mark is None or getattr(mark, "line", None) is None:
        return None
    return mark.line + 2


def _message(exc: Exception) -> str:
    problem = getattr(exc, "problem", None)
    return str(problem) if problem else str(exc).splitlines()[0]


def _load_block(block: Block, path: Optional[str]):
    """Load a block's mapping in round-trip form, raising FrontmatterError on failure."""
    module = bootstrap.require("ruamel.yaml")
    text = block.raw.replace("\r\n", "\n").replace("\r", "\n") + "\n"
    try:
        data = _yaml().load(text)
    except module.error.YAMLError as exc:
        raise FrontmatterError(_message(exc), _error_line(exc), path) from exc
    if data is None:
        return module.comments.CommentedMap()
    if not isinstance(data, Mapping):
        raise FrontmatterError(
            f"front-matter must be a mapping, got {type(data).__name__}", 2, path)
    return data


def _dump(data) -> str:
    stream = io.StringIO()
    _yaml().dump(data, stream)
    return stream.getvalue()


def plain(value: Any) -> Any:
    """Convert a ruamel round-trip value into ordinary Python.

    Dates become `YYYY-MM-DD` strings, because every consumer here formats them as
    text, and an unset key becomes the empty string, because front-matter is text
    metadata and callers do `fm.get("milestone", "")`.
    """
    if value is None:
        return ""
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Mapping):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value)
    return str(value)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def parse(content: str, path: Optional[str] = None) -> Tuple[Dict[str, Any], str]:
    """Parse leading front-matter, returning `(mapping, body)` as plain Python.

    A document with no block yields `({}, content)`. A block that is not valid YAML
    raises FrontmatterError.
    """
    block = split(content)
    if block is None:
        return {}, content
    data = _load_block(block, path)
    return {str(key): plain(value) for key, value in data.items()}, block.body


def try_parse(content: str, path: Optional[str] = None
              ) -> Tuple[Dict[str, Any], str, Optional[FrontmatterError]]:
    """Tolerant `parse` for read-only scanners.

    Returns `(mapping, body, error)`. On failure the mapping is empty and the error is
    returned rather than raised. Never use this before writing a file back.
    """
    try:
        mapping, body = parse(content, path=path)
        return mapping, body, None
    except FrontmatterError as exc:
        block = split(content)
        return {}, (block.body if block else content), exc


def parse_tolerant(content: str, path: Optional[str] = None,
                   prefix: str = "[Warning]") -> Tuple[Dict[str, Any], str]:
    """`try_parse` that reports the problem on stderr and returns what it could read.

    For engines that scan or inspect many files: one malformed entity must not abort a
    repository-wide operation, but the operator has to hear about it. An engine that
    then WRITES the file must use strict `parse` or `update`, both of which refuse.
    """
    fields, body, error = try_parse(content, path=path)
    if error:
        print(f"{prefix} {error}", file=sys.stderr)
    return fields, body


def parse_file(path: str) -> Tuple[Dict[str, Any], str]:
    """Read `path` strictly as UTF-8 and parse its front-matter."""
    from . import textio

    return parse(textio.read_text(path), path=path)


def lint(content: str, path: Optional[str] = None) -> List[str]:
    """Report front-matter that a strict YAML reader would reject.

    Earlier Along versions emitted unquoted values, so a title containing a colon
    produced a block that PyYAML, `gray-matter`, and GitHub all refuse. Such files are
    readable by nothing but the old hand-rolled parser, so a gate needs to surface them.
    """
    block = split(content)
    if block is None:
        return []
    try:
        _load_block(block, path)
    except FrontmatterError as exc:
        return [str(exc)]
    return []


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def quoted(value: Any) -> Any:
    """Mark a scalar to be emitted in quotes even when YAML would not require them.

    Used for `protocol_version`, which the protocol writes as `"2.2.8"`: unquoted it
    is still a string today, but a two-component version such as `3.0` would become a
    float, and the repository convention is to quote it everywhere.
    """
    module = bootstrap.require("ruamel.yaml")
    return module.scalarstring.DoubleQuotedScalarString(str(value))


def _flow(value: Any) -> Any:
    """Prepare a Python value for emission, using flow style for collections.

    The repository writes `tags: [a, b]` and `items: [{id: 1}]` on one line, which is
    what the documented schema in AGENTS.md shows, so new values follow that style.
    Existing values keep whatever style the file already used.
    """
    module = bootstrap.require("ruamel.yaml")
    if isinstance(value, Mapping):
        mapping = module.comments.CommentedMap(
            (key, _flow(item)) for key, item in value.items())
        mapping.fa.set_flow_style()
        return mapping
    if isinstance(value, (list, tuple, set)):
        sequence = module.comments.CommentedSeq(_flow(item) for item in value)
        sequence.fa.set_flow_style()
        return sequence
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value
    if isinstance(value, str) and ISO_DATE_RE.match(value):
        # Emitted unquoted, as `created: 2026-09-01`, matching the convention every
        # existing entity file uses. Passing the string through would make ruamel quote
        # it to preserve its type, producing gratuitous diff churn against those files.
        try:
            return datetime.date.fromisoformat(value)
        except ValueError:
            return value
    return value


def _verify(document: str, expected: Mapping[str, Any], path: Optional[str]) -> str:
    """Re-parse an emitted document and refuse to return it if it does not match."""
    verified, _ = parse(document, path=path)
    wanted = {str(key): plain(value) for key, value in expected.items()}
    if verified != wanted:
        raise FrontmatterError(
            "emitted front-matter does not round-trip; refusing to write. "
            f"expected={wanted!r} got={verified!r}", path=path)
    return document


def update(content: str, updates: Mapping[str, Any],
           place_after: Optional[Mapping[str, str]] = None,
           remove: Iterable[str] = (),
           path: Optional[str] = None) -> str:
    """Set, insert, or delete keys in the LEADING front-matter block only.

    Comments, key order, quoting style, block sequences, and the file's line endings
    are preserved. The markdown body is never touched, so prose or code samples
    mentioning `status:` cannot be corrupted.

    Keys absent from the block are inserted after their `place_after` anchor when one
    is given, otherwise appended.

    A leading UTF-8 BOM is dropped, because the protocol requires BOM-free UTF-8 while
    PowerShell 5.1 adds one. That is a byte-level change the caller did not ask for, so
    callers MUST report it: check `content.startswith(frontmatter.BOM)` before calling.
    Detecting and rejecting BOMs in committed text is the quality gate's job, not this
    function's.

    Content with no front-matter block is returned unchanged; check `has_frontmatter`
    first when that would be a silent no-op for the caller.
    """
    block = split(content)
    if block is None:
        return content

    data = _load_block(block, path)
    place_after = dict(place_after or {})

    for key in remove:
        if key in data:
            del data[key]

    for key, value in updates.items():
        prepared = _flow(value)
        if key in data:
            data[key] = prepared
            continue
        anchor = place_after.get(key)
        keys = list(data.keys())
        if anchor and anchor in keys:
            data.insert(keys.index(anchor) + 1, key, prepared)
        else:
            data[key] = prepared

    emitted = _dump(data).rstrip("\n")
    if block.newline != "\n":
        emitted = emitted.replace("\n", block.newline)
    document = block.open_delim + emitted + block.close_delim + block.body
    return _verify(document, data, path)


def render(fm: Mapping[str, Any], body: str, newline: str = "\n") -> str:
    """Build a complete document from a mapping and a body.

    For new files: nothing is preserved because there is nothing to preserve. The
    emitted block is re-parsed and compared with `fm` before it is returned, so an
    emitter defect surfaces as an exception instead of a corrupted file.
    """
    module = bootstrap.require("ruamel.yaml")
    data = module.comments.CommentedMap((key, _flow(value)) for key, value in fm.items())
    emitted = _dump(data).rstrip("\n")
    if newline != "\n":
        emitted = emitted.replace("\n", newline)
    document = (f"---{newline}" + emitted + f"{newline}---{newline}{newline}"
                + body.strip() + newline)
    return _verify(document, fm, None)
