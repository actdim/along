"""Extract and validate write-scope file paths from an approved plan.

[feat--plan-grants-write-scope]
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along plan --help   (or: python scripts/along_exec.py plan --help)"
    )

import os
import re
from typing import List, Optional, Tuple

from . import repo


_HEADING = re.compile(
    r"^#{1,6}\s+.*\b(files?\s+to\s+(change|modify|edit)|critical\s+files)\b",
    re.IGNORECASE,
)
_PATH = re.compile(r"`([^`\s]+)`")
_LINE_SUFFIX = re.compile(r":\d+(?:-\d+)?$")


def plan_paths(plan_text: str) -> List[str]:
    """Paths in backticks inside the plan's 'Files to change' section.

    Parsed until the next heading of the same or higher level.
    Keeps only tokens with a '/' or a '.' in the last segment;
    strips a trailing ':line' suffix; dedups, keeps order.
    """
    if not plan_text:
        return []

    lines = plan_text.splitlines()
    in_section = False
    target_level = 0
    extracted: List[str] = []

    for line in lines:
        stripped = line.strip()
        m_head = re.match(r"^(#{1,6})\s+", stripped)
        if m_head:
            level = len(m_head.group(1))
            if in_section:
                if level <= target_level:
                    in_section = False
                    if _HEADING.match(stripped):
                        in_section = True
                        target_level = level
                        continue
            else:
                if _HEADING.match(stripped):
                    in_section = True
                    target_level = level
                    continue

        if in_section:
            for token in _PATH.findall(stripped):
                clean = _LINE_SUFFIX.sub("", token.strip())
                norm = clean.replace("\\", "/")
                parts = norm.split("/")
                last_seg = parts[-1]
                if not last_seg or last_seg in (".", ".."):
                    continue
                if ("/" in clean or "\\" in clean) or ("." in last_seg):
                    if clean not in extracted:
                        extracted.append(clean)

    return extracted


def split_grantable(
    paths: List[str],
    ctx: str,
    workspace_root: str,
    allowed_roots: Optional[List[str]] = None,
) -> Tuple[List[str], List[str]]:
    """(grant, rejected): resolve each path against `ctx`; skip paths inside `ctx`
    (already in scope); grant paths inside `workspace_root` or any of `allowed_roots`;
    reject the rest.
    """
    grant: List[str] = []
    rejected: List[str] = []
    roots = [os.path.abspath(r) for r in (allowed_roots or []) if r]

    for p in paths:
        if os.path.isabs(p):
            abs_p = os.path.normpath(p)
        else:
            abs_p = os.path.normpath(os.path.join(ctx, p))

        if repo.is_within(abs_p, ctx):
            continue

        is_allowed = repo.is_within(abs_p, workspace_root) or any(
            repo.is_within(abs_p, r) for r in roots
        )

        if is_allowed:
            rel = repo.canonical_relpath(abs_p, ctx)
            if rel not in grant:
                grant.append(rel)
        else:
            if p not in rejected:
                rejected.append(p)

    return grant, rejected
