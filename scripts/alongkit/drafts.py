#!/usr/bin/env python3
"""alongkit.drafts - Issue drafts storage, listing, and promotion engine.

[feat--issue-drafts-lifecycle]
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along issue --help   (or: python scripts/along_exec.py issue --help)"
    )

import os
from typing import Any, Dict, List, Optional

from . import entities, frontmatter, repo, textio
from .exceptions import ValidationError

DRAFTS_DIRNAME = ".drafts"


def drafts_dir(repo_root: str) -> str:
    """Canonical path to <state_dir>/.drafts, initialized with a '*' .gitignore."""
    path = os.path.join(repo.state_dir(repo_root), DRAFTS_DIRNAME)
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
    gi = os.path.join(path, ".gitignore")
    if not os.path.isfile(gi):
        try:
            textio.write_text(gi, "*\n", newline="\n")
        except OSError:
            pass
    return path


def find_draft(repo_root: str, slug: str) -> Optional[str]:
    """Return the filesystem path of draft <type>--<slug>.md or None."""
    ddir = drafts_dir(repo_root)
    if not os.path.isdir(ddir):
        return None
    clean_slug = slug.strip()
    if clean_slug.endswith(".md"):
        clean_slug = clean_slug[:-3]
    if "--" in clean_slug:
        clean_slug = clean_slug.split("--", 1)[1]
    try:
        entries = sorted(os.listdir(ddir))
    except OSError:
        return None
    for item in entries:
        if not item.endswith(".md") or item.startswith("."):
            continue
        stem = item[:-3]
        item_slug = stem.split("--", 1)[1] if "--" in stem else stem
        if item_slug == clean_slug or stem == slug:
            return os.path.join(ddir, item)
    return None


def list_drafts(repo_root: str) -> List[Dict[str, Any]]:
    """List all drafts in <state_dir>/.drafts as [{key, path, mtime}]."""
    ddir = drafts_dir(repo_root)
    if not os.path.isdir(ddir):
        return []
    results: List[Dict[str, Any]] = []
    try:
        entries = sorted(os.listdir(ddir))
    except OSError:
        return []
    for item in entries:
        if not item.endswith(".md") or item.startswith("."):
            continue
        fpath = os.path.join(ddir, item)
        if not os.path.isfile(fpath):
            continue
        try:
            st = os.stat(fpath)
            mtime = st.st_mtime
        except OSError:
            mtime = 0.0
        key = item[:-3]
        results.append({
            "key": key,
            "path": fpath,
            "mtime": mtime,
        })
    return results


def promote(repo_root: str, slug: str) -> str:
    """Promote a draft from .along/.drafts/ to .along/ISSUES/.

    Validates schema and placeholders, checks for duplicate slug, moves the file,
    and synchronizes ISSUES.md.
    """
    draft_path = find_draft(repo_root, slug)
    if not draft_path or not os.path.isfile(draft_path):
        raise ValidationError(f"Draft '{slug}' not found.")

    content = textio.read_text(draft_path)
    fm, body, err = frontmatter.try_parse(content)
    if err or not fm:
        raise ValidationError(f"Draft '{slug}' has invalid frontmatter: {err or 'Missing frontmatter'}")

    is_stub, reasons = entities.is_issue_stub(content)
    if is_stub:
        raise ValidationError(f"Draft '{slug}' contains placeholder content: {'; '.join(reasons)}")

    clean_slug = fm.get("slug") or (slug.split("--", 1)[1] if "--" in slug else slug)
    existing = entities.find_issue_by_slug(repo_root, clean_slug)
    if existing:
        raise ValidationError(f"Issue '{clean_slug}' already exists in .along/ISSUES/.")

    filename = os.path.basename(draft_path)
    if "--" not in filename:
        itype = fm.get("type", "task")
        filename = f"{itype}--{clean_slug}.md"

    target_dir = os.path.join(repo.state_dir(repo_root), "ISSUES")
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, filename)

    os.replace(draft_path, target_path)
    entities.sync_issues_board(repo_root)
    return target_path
