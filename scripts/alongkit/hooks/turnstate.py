#!/usr/bin/env python3
"""
alongkit.hooks.turnstate - What a turn changed in the working tree, judged by `git status`.

Shell commands are not classified before they run: whether a command writes is not decidable
from its text. Instead the working tree is snapshotted when the user's message arrives
(UserPromptSubmit) and compared at the end of the turn (Stop). A path counts as changed by the
turn when it is dirty now and was clean, or had other content, at the snapshot; files that were
already dirty and untouched are not attributed to the turn. [debt--gate-simplification]
"""

from __future__ import annotations

import hashlib
import os
from typing import Dict, List, Optional

from .. import closeout, repo

#: Files hashed per snapshot at most; beyond it the rest is compared by git status code only.
MAX_HASHED_FILES = 2000


def _digest(path: str) -> str:
    """Content hash of `path`, or a marker for a missing file / directory."""
    if not os.path.isfile(path):
        return "-"
    h = hashlib.sha1()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                h.update(chunk)
    except OSError:
        return "?"
    return h.hexdigest()


def snapshot(repo_root: str) -> Optional[Dict[str, str]]:
    """{absolute POSIX path: status code + content hash} of every dirty path, None outside git."""
    real_root = os.path.realpath(os.path.abspath(repo_root))
    top = closeout.git_top(real_root)
    if not top:
        return None
    state: Dict[str, str] = {}
    for idx, (rel, code) in enumerate(sorted(closeout.git_changes(real_root).items())):
        abs_path = os.path.join(top, rel)
        digest = _digest(abs_path) if idx < MAX_HASHED_FILES else ""
        state[repo.normalize_posix(abs_path)] = f"{code}:{digest}"
    return state


def changed_since(repo_root: str, baseline: Dict[str, str]) -> List[str]:
    """Repo-relative POSIX paths whose dirty state differs from `baseline` (sorted)."""
    now = snapshot(repo_root)
    if now is None:
        return []
    real_root = os.path.realpath(os.path.abspath(repo_root))
    changed: List[str] = []
    for abs_path, state in now.items():
        if baseline.get(abs_path) == state:
            continue
        rel = repo.safe_relpath(abs_path, real_root)
        if rel.startswith("..") or os.path.isabs(rel):
            continue
        changed.append(repo.normalize_posix(rel))
    return sorted(changed)
