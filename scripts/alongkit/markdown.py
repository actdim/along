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

from . import repo

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


def extract_heading_anchors(text: str) -> set[str]:
    """Extract all GitHub-compatible heading anchors from text outside fenced code."""
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    heading_re = re.compile(r"^ {0,3}#{1,6}\s+(.+)$")
    for _, line in iter_lines_outside_fences(text):
        m = heading_re.match(line)
        if m:
            raw_title = m.group(1).strip()
            title = re.sub(r"\s+#+\s*$", "", raw_title)
            base_slug = github_heading_anchor(title)
            if not base_slug:
                continue
            cnt = counts.get(base_slug, 0)
            slug = base_slug if cnt == 0 else f"{base_slug}-{cnt}"
            counts[base_slug] = cnt + 1
            anchors.add(slug)
    return anchors


def find_broken_links(text: str, file_path: str, repo_root: str) -> List[dict]:
    """Verify that all markdown links in text resolve to valid files and heading anchors.

    Checks:
    - Relative files exist on disk.
    - Intra-document (#anchor) and cross-document (file.md#anchor) heading anchors exist.
    - file:// pseudo-schemes are reported as broken.
    - Stable Entry Point Rule: relative links in files outside .along/ must not point directly into .along/.
    """
    broken: List[dict] = []
    repo_root = os.path.abspath(repo_root)
    file_path = os.path.abspath(file_path)
    current_anchors = extract_heading_anchors(text)
    target_cache: dict[str, set[str]] = {}

    for link in find_links(text, skip_external=False):
        raw_target = link.target.strip()
        if not raw_target:
            continue

        if is_external(raw_target) and not raw_target.startswith("#"):
            continue

        if is_placeholder(raw_target):
            continue

        if raw_target.startswith("file://"):
            broken.append({
                "link": link,
                "reason": "Forbidden file:// pseudo-scheme",
                "target": raw_target,
                "line": link.line,
            })
            continue

        # Check intra-document anchor: #anchor
        if raw_target.startswith("#"):
            anchor_slug = raw_target[1:].strip().lower()
            if anchor_slug and anchor_slug not in current_anchors:
                broken.append({
                    "link": link,
                    "reason": f"Dangling heading anchor: {raw_target}",
                    "target": raw_target,
                    "line": link.line,
                })
            continue

        # Cross-document link
        resolved = resolve_target(raw_target, file_path, repo_root)
        if resolved is None or not os.path.exists(resolved):
            broken.append({
                "link": link,
                "reason": f"Target file does not exist: {raw_target}",
                "target": raw_target,
                "line": link.line,
            })
            continue

        # Stable entry point rule: files outside .along/ must not link directly into .along/
        from_rel = repo.safe_relpath(file_path, repo_root).replace("\\", "/")
        target_rel = repo.safe_relpath(resolved, repo_root).replace("\\", "/")
        if not from_rel.startswith(".along/") and (target_rel.startswith(".along/") or "/.along/" in target_rel):
            broken.append({
                "link": link,
                "reason": f"Stable entry point violation: relative link into .along/ from {from_rel}",
                "target": raw_target,
                "line": link.line,
            })
            continue

        # Check cross-file anchor if present
        if link.anchor:
            anchor_slug = link.anchor[1:].strip().lower()
            if anchor_slug:
                if resolved not in target_cache:
                    if resolved.endswith(".md") and os.path.isfile(resolved):
                        try:
                            with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                                target_cache[resolved] = extract_heading_anchors(f.read())
                        except OSError:
                            target_cache[resolved] = set()
                    else:
                        target_cache[resolved] = set()
                if anchor_slug not in target_cache[resolved]:
                    broken.append({
                        "link": link,
                        "reason": f"Dangling heading anchor {link.anchor} in target {target_rel}",
                        "target": raw_target,
                        "line": link.line,
                    })

    return broken

