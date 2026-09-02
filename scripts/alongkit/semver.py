#!/usr/bin/env python3
"""
alongkit.semver - Semantic version parsing and increments.

`parse_semver` existed in `along_version_bump.py` and `along_update.py` in two copies
that differed in their tolerance of prefixes and pre-release suffixes, while the
release engine and the updater compare versions with each other. Two parsers deciding
which of two versions is newer is a defect waiting for a pre-release tag.
"""


from __future__ import annotations
if __name__ == "__main__":
    raise SystemExit(
        f"{__name__} is a library module, not a command.\n"
        "Run: along kb-sync   (or: python scripts/along_exec.py kb-sync)"
    )


import re
from typing import Sequence, Tuple

Version = Tuple[int, int, int]

_NUMERIC_RE = re.compile(r"^\d+\.\d+\.\d+")

#: Accepted increment keywords, in order of magnitude.
BUMP_KEYWORDS: tuple = ("patch", "minor", "major")


def parse(value: str) -> Version:
    """Parse `1.2.3`, `v1.2.3`, or `1.2.3-rc1` into a `(major, minor, patch)` tuple.

    Unparseable input yields `(0, 0, 0)` rather than raising, because callers use this
    to compare an unknown installed version against a known one and must not crash on
    a malformed string they did not write.
    """
    if not value:
        return (0, 0, 0)
    cleaned = str(value).strip().lstrip("vV").split("-")[0].split("+")[0]
    parts = cleaned.split(".")
    numbers = []
    for index in range(3):
        try:
            numbers.append(int(parts[index]) if index < len(parts) else 0)
        except (ValueError, TypeError):
            return (0, 0, 0)
    return (numbers[0], numbers[1], numbers[2])


def to_str(version: Sequence[int]) -> str:
    """Render a `(major, minor, patch)` tuple as `major.minor.patch`."""
    major, minor, patch = (list(version) + [0, 0, 0])[:3]
    return f"{major}.{minor}.{patch}"


def calculate_next(current: str, bump: str) -> str:
    """Next version after applying `bump`, which is a keyword or an explicit `X.Y.Z`.

    Raises ValueError for anything else; the caller decides whether that is a usage
    error to report or a condition to recover from.
    """
    major, minor, patch = parse(current)
    keyword = str(bump).lower().strip()
    if keyword == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if keyword == "minor":
        return f"{major}.{minor + 1}.0"
    if keyword == "major":
        return f"{major + 1}.0.0"
    explicit = keyword.lstrip("vV")
    if _NUMERIC_RE.match(explicit):
        return explicit
    raise ValueError(
        f"invalid bump type or version: {bump!r}. Expected patch, minor, major, or X.Y.Z")


def is_newer(candidate: str, baseline: str) -> bool:
    """True when `candidate` is a strictly newer version than `baseline`."""
    return parse(candidate) > parse(baseline)
