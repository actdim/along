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
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along kb-sync   (or: python scripts/along_kb_sync.py)"
    )


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

_OPEN_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_CLOSE_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*$")


class FenceTracker:
    """Tracks CommonMark-compliant fenced code block state across lines."""

    def __init__(self) -> None:
        self.char: Optional[str] = None
        self.length: int = 0

    @property
    def in_fence(self) -> bool:
        return self.char is not None

    def process_line(self, line: str) -> bool:
        """Process one line. Returns True if this line is a fence boundary (opening or closing)."""
        stripped = line.rstrip("\r\n")
        if self.char is None:
            m = _OPEN_FENCE_RE.match(stripped)
            if m:
                marker = m.group(1)
                char = marker[0]
                info = m.group(2)
                # Backtick fences cannot have backticks in the info string
                if char == "`" and "`" in info:
                    return False
                self.char = char
                self.length = len(marker)
                return True
            return False
        else:
            m = _CLOSE_FENCE_RE.match(stripped)
            if m:
                marker = m.group(1)
                char = marker[0]
                length = len(marker)
                if char == self.char and length >= self.length:
                    self.char = None
                    self.length = 0
                    return True
            return False


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


_PLACEHOLDER_RE = re.compile(r"<[^>]+>|{{[^}]+}}")


def is_placeholder(target: str) -> bool:
    """True for a template or illustrative target such as `./topic--<slug>.md` or `{{var}}`."""
    stripped = target.strip()
    return bool(_PLACEHOLDER_RE.search(stripped)) or stripped in ("./target.md", "target.md")


def iter_lines_outside_fences(text: str) -> Iterator[Tuple[int, str]]:
    """Yield `(line_number, line)` for lines that are not inside a fenced code block.

    Fence lines themselves are not yielded. Tracks both ``` and ~~~ fences and requires
    the closing fence to use the same character and at least the same length.
    """
    tracker = FenceTracker()
    for number, line in enumerate(text.splitlines(), 1):
        is_boundary = tracker.process_line(line)
        if not is_boundary and not tracker.in_fence:
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
    tracker = FenceTracker()
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        is_boundary = tracker.process_line(line)
        if is_boundary or tracker.in_fence:
            out.append(line)
            continue

        def replace(m: "re.Match") -> str:
            nonlocal rewrites
            target = m.group("target").strip()
            link = Link(text=m.group("text"), target=target, line=number,
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
    """Filesystem path a link target points at, or None when it is not a valid relative file link.

    The file:// pseudo-scheme is strictly forbidden (REQ-4, REQ-5).
    """
    stripped = target.strip()
    if is_external(stripped) or is_placeholder(stripped) or stripped.startswith("file://"):
        return None
    base = stripped.split("#", 1)[0].strip().replace("\\", "/")
    if not base:
        return None

    from_dir = os.path.dirname(os.path.abspath(from_file))
    return os.path.normpath(os.path.join(from_dir, base))
