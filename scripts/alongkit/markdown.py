#!/usr/bin/env python3
"""
alongkit.markdown - Markdown link and heading primitives.

Link handling used to be reimplemented in every engine that touched markdown:
`along_kb_sync.py` had one regex for rewriting and another for validating,
`along_kb_search.py` had its own heading-anchor function, and the rules for what
counts as an external target were spelled out inline at each site with slightly
different lists. The consequences are tracked as
`[bug--kb-sync-rewrites-unrelated-numbered-links]` and
`[bug--generated-docs-emit-file-uri-links]`.

Fenced code is tracked here rather than at the call site, because a link inside a
```` ``` ```` block is documentation about a link, not a link.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Callable, Iterator, List, Optional, Tuple

#: `[text](target)` with the parts a rewriter needs to reassemble the link.
LINK_RE = re.compile(r"(?P<prefix>\[(?P<text>[^\]]*)\]\()(?P<target>[^)]*)(?P<suffix>\))")

#: Schemes that never point at a file in the repository.
EXTERNAL_PREFIXES: tuple = (
    "http://", "https://", "mailto:", "ftp://", "ftps://", "data:", "tel:", "//",
)

_FENCE_RE = re.compile(r"^\s*(```+|~~~+)")


@dataclass(frozen=True)
class Link:
    """One markdown link found outside fenced code."""

    text: str
    target: str
    line: int
    start: int
    end: int

    @property
    def path_part(self) -> str:
        """Target without its `#anchor`."""
        return self.target.split("#", 1)[0].strip()

    @property
    def anchor(self) -> str:
        """The `#anchor` including its hash, or an empty string."""
        return "#" + self.target.split("#", 1)[1] if "#" in self.target else ""


def is_external(target: str) -> bool:
    """True for a target that cannot be resolved against the filesystem."""
    stripped = target.strip()
    return not stripped or stripped.startswith("#") or stripped.startswith(EXTERNAL_PREFIXES)


def is_placeholder(target: str) -> bool:
    """True for a template or illustrative target such as `./topic--<slug>.md` or `{{var}}`."""
    stripped = target.strip()
    return "<" in stripped or ">" in stripped or stripped.startswith("{{")


def iter_lines_outside_fences(text: str) -> Iterator[Tuple[int, str]]:
    """Yield `(line_number, line)` for lines that are not inside a fenced code block.

    Fence lines themselves are not yielded. Tracks both ``` and ~~~ fences and requires
    the closing fence to use the same character, so a ``` inside a ~~~ block does not
    end it.
    """
    fence: Optional[str] = None
    for number, line in enumerate(text.splitlines(), 1):
        match = _FENCE_RE.match(line)
        if match:
            marker = match.group(1)[0]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence is None:
            yield number, line


def find_links(text: str, skip_external: bool = False) -> List[Link]:
    """All markdown links outside fenced code, in document order."""
    links: List[Link] = []
    for number, line in iter_lines_outside_fences(text):
        for match in LINK_RE.finditer(line):
            target = match.group("target").strip()
            if skip_external and is_external(target):
                continue
            links.append(Link(text=match.group("text"), target=target, line=number,
                              start=match.start(), end=match.end()))
    return links


def rewrite_links(text: str, transform: Callable[[Link], Optional[str]]) -> Tuple[str, int]:
    """Rewrite link targets outside fenced code, returning `(new_text, count)`.

    `transform` receives a Link and returns the replacement target, or None to leave
    the link alone. Text inside fenced code is copied verbatim, which is what keeps a
    documented example from being rewritten as if it were a real link.
    """
    rewrites = 0
    out: List[str] = []
    fence: Optional[str] = None
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        match = _FENCE_RE.match(stripped)
        if match:
            marker = match.group(1)[0]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            out.append(line)
            continue
        if fence is not None:
            out.append(line)
            continue

        def replace(m: "re.Match") -> str:
            nonlocal rewrites
            target = m.group("target").strip()
            link = Link(text=m.group("text"), target=target, line=0,
                        start=m.start(), end=m.end())
            replacement = transform(link)
            if replacement is None or replacement == target:
                return m.group(0)
            rewrites += 1
            return m.group("prefix") + replacement + m.group("suffix")

        out.append(LINK_RE.sub(replace, line))
    return "".join(out), rewrites


def github_heading_anchor(heading: str) -> str:
    """Mirror the GitHub Markdown heading anchor algorithm for stable deep links."""
    anchor = heading.strip().lstrip("#").strip().lower()
    anchor = re.sub(r"[^\w\s-]", "", anchor)
    return re.sub(r"\s+", "-", anchor).strip("-")


def resolve_target(target: str, from_file: str, repo_root: str) -> Optional[str]:
    """Filesystem path a link target points at, or None when it is not a file link.

    Handles the `file://` forms this repository has emitted historically, including
    `file:///d:/...` absolute Windows paths and `file://docs/x.md` repository-relative
    ones, which are dead on every renderer and tracked as
    `[bug--generated-docs-emit-file-uri-links]`.
    """
    stripped = target.strip()
    if is_external(stripped) or is_placeholder(stripped):
        return None
    base = stripped.split("#", 1)[0].strip().replace("\\", "/")
    if not base:
        return None

    from_dir = os.path.dirname(os.path.abspath(from_file))
    if base.startswith("file:///"):
        remainder = base[8:]
        if len(remainder) > 2 and remainder[1] == ":":
            return os.path.normpath(remainder)
        return os.path.normpath("/" + remainder)
    if base.startswith("file://"):
        remainder = base[7:].lstrip("/")
        if len(remainder) > 2 and remainder[1] == ":":
            return os.path.normpath(remainder)
        return os.path.normpath(os.path.join(repo_root, remainder))
    return os.path.normpath(os.path.join(from_dir, base))
