#!/usr/bin/env python3
"""alongkit.webdev.failures - Automated failure filing into bug issues (REQ-11)."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from .. import entities, frontmatter, repo, textio


def sanitize_slug(text: str) -> str:
    """Normalize text into clean ASCII issue slug segment."""
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return s or "failure"


def build_failure_issue_content(
    parent_issue: str,
    check_id: str,
    title: str,
    reason: str,
    steps_list: List[Dict[str, Any]],
    evidence_paths: List[str],
) -> Tuple[str, str]:
    """Construct (slug, issue_markdown) for filing a bug issue."""
    parent_slug = parent_issue.split("--")[-1] if "--" in parent_issue else parent_issue
    clean_check = sanitize_slug(check_id)
    slug = f"bug--{parent_slug}-{clean_check}"

    steps_text = "\n".join(f"{idx+1}. `{s}`" for idx, s in enumerate(steps_list)) or "1. Run check"
    ev_text = "\n".join(f"- `{p}`" for p in evidence_paths) or "- None"

    today = entities.today_iso()
    meta = (
        "---\n"
        "protocol: along\n"
        f"slug: {parent_slug}-{clean_check}\n"
        "type: bug\n"
        "status: open\n"
        "priority: high\n"
        f"created: {today}\n"
        f"updated: {today}\n"
        "agent: along-webdev\n"
        "tags: [webdev, bug, regression]\n"
        f"related: [{parent_issue}]\n"
        "---\n\n"
    )

    body = (
        f"# WebDev Verification Failure: {check_id} - {title}\n\n"
        "## Problem\n"
        f"Automated browser verification failed during check `{check_id}` in `{parent_issue}`:\n"
        f"```text\n{reason}\n```\n\n"
        "## Steps to Reproduce\n"
        f"{steps_text}\n\n"
        "## Evidence\n"
        f"{ev_text}\n\n"
        "## Acceptance Criteria\n"
        f"- [ ] Check `{check_id}` passes verification.\n"
        "- [ ] Automated tests passing\n"
    )

    return slug, meta + body


def file_failures(
    repo_root: str,
    parent_issue: str,
    failed_results: List[Dict[str, Any]],
) -> List[str]:
    """Create bug issues for each failed verification check (REQ-11)."""
    created_paths: List[str] = []
    issues_dir = os.path.join(repo.state_dir(repo_root), "ISSUES")
    os.makedirs(issues_dir, exist_ok=True)

    for r in failed_results:
        cid = r.get("check_id", "chk")
        title = r.get("title", "Verification failure")
        reason = r.get("reason", "Assertion failed")
        steps_list = r.get("steps") or []
        ev_paths = r.get("evidence") or []

        slug, md_content = build_failure_issue_content(
            parent_issue=parent_issue,
            check_id=cid,
            title=title,
            reason=reason,
            steps_list=steps_list,
            evidence_paths=ev_paths,
        )

        filename = f"{slug}.md" if not slug.endswith(".md") else slug
        target_path = os.path.join(issues_dir, filename)
        textio.write_text(target_path, md_content, newline="\n")
        created_paths.append(target_path)

    if created_paths:
        # Recompile ISSUES.md board
        board_file = os.path.join(repo.state_dir(repo_root), "ISSUES.md")
        board_content = entities.compile_issues_board(repo_root)
        textio.write_text(board_file, board_content, newline="\n")

    return created_paths
