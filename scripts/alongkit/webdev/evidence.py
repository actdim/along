#!/usr/bin/env python3
"""alongkit.webdev.evidence - Artifact directory management, self-ignoring setup, and deterministic naming (REQ-8)."""

from __future__ import annotations

import hashlib
import os
import shutil
import time
import uuid
from typing import Any, Dict, List, Optional

from .. import repo


def ensure_artifacts_dir(repo_root: str) -> str:
    """Ensure .along/artifacts/ exists and is self-ignoring via .gitignore (REQ-8)."""
    art_dir = os.path.join(repo.state_dir(repo_root), "artifacts")
    os.makedirs(art_dir, exist_ok=True)
    gi = os.path.join(art_dir, ".gitignore")
    if not os.path.isfile(gi):
        try:
            with open(gi, "w", encoding="utf-8") as f:
                f.write("*\n!.gitignore\n")
        except OSError:
            pass
    return art_dir


def generate_run_id() -> str:
    """Generate timestamp-based deterministic run identifier."""
    utc_str = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    short_hash = uuid.uuid4().hex[:6]
    return f"{utc_str}-{short_hash}"


def get_run_artifacts_dir(repo_root: str, issue_key: str, run_id: str) -> str:
    """Return run-specific output directory under .along/artifacts/webdev/<issue-key>/<run-id>/."""
    art_dir = ensure_artifacts_dir(repo_root)
    run_dir = os.path.join(art_dir, "webdev", issue_key, run_id)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def evidence_filename(
    check_id: str,
    viewport: str = "desktop",
    theme: str = "light",
    step_label: str = "shot",
    ext: str = "png",
) -> str:
    """Construct deterministic artifact filename: <check-id>--<viewport>--<theme>--<step>.png."""
    clean_check = check_id.replace(" ", "_")
    clean_vp = viewport.replace(" ", "_")
    clean_theme = theme.replace(" ", "_")
    clean_step = step_label.replace(" ", "_")
    return f"{clean_check}--{clean_vp}--{clean_theme}--{clean_step}.{ext}"


def capture_screenshot(
    page: Any,
    out_path: str,
    target_locator: Optional[Any] = None,
    clip: Optional[Dict[str, float]] = None,
    full_page: bool = False,
) -> str:
    """Capture screenshot to out_path with element, region, or full page options."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    if target_locator:
        target_locator.screenshot(path=out_path)
    elif clip:
        page.screenshot(path=out_path, clip=clip)
    else:
        page.screenshot(path=out_path, full_page=full_page)
    return os.path.abspath(out_path)


def export_evidence(src_dir: str, target_dir: str) -> List[str]:
    """Copy generated evidence files to an explicit tracked directory (--keep-evidence)."""
    copied: List[str] = []
    if not os.path.isdir(src_dir):
        return copied
    os.makedirs(target_dir, exist_ok=True)
    for root, _, files in os.walk(src_dir):
        for f in files:
            if f.endswith((".png", ".webp", ".jpg")):
                src_file = os.path.join(root, f)
                dest_file = os.path.join(target_dir, f)
                shutil.copy2(src_file, dest_file)
                copied.append(dest_file)
    return copied
