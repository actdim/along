#!/usr/bin/env python3
"""alongkit.webdev.results - Results reporting, ReportPayload JSON, and issue section updating (REQ-11)."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from .. import entities, frontmatter, repo, textio

SECTION_HEADER = "## Browser Verification Results"


def format_results_markdown(run_id: str, results: List[Dict[str, Any]]) -> str:
    """Format check execution results into GitHub-flavored Markdown summary table."""
    lines = [
        f"{SECTION_HEADER}",
        f"Run ID: `{run_id}` (evaluated at {time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime())})",
        "",
        "| Check | AC | Viewport | Theme | Status | Reason | Evidence |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for r in results:
        cid = r.get("check_id", "")
        title = r.get("title", "")
        check_col = f"**{cid}**: {title}" if title else cid
        ac = r.get("ac") or "-"
        vp = r.get("viewport") or "-"
        theme = r.get("theme") or "-"
        status = r.get("status", "NOT RUN")
        reason = r.get("reason") or "-"

        evidence_links = []
        for ev in r.get("evidence") or []:
            rel = os.path.basename(ev)
            evidence_links.append(f"[{rel}]({ev})")
        ev_col = ", ".join(evidence_links) if evidence_links else "-"

        lines.append(f"| {check_col} | {ac} | {vp} | {theme} | **{status}** | {reason} | {ev_col} |")

    lines.append("")
    return "\n".join(lines)


def build_report_payload(
    issue_key: str,
    run_id: str,
    results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Construct structured report payload matching feat--along-report-engine contract."""
    passed = sum(1 for r in results if r.get("status") == "PASS")
    failed = sum(1 for r in results if r.get("status") == "FAIL")
    not_run = sum(1 for r in results if r.get("status") == "NOT RUN")

    return {
        "run_id": run_id,
        "issue": issue_key,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
        "summary": {
            "passed": passed,
            "failed": failed,
            "not_run": not_run,
            "total": len(results),
        },
        "results": results,
    }


def update_issue_results(
    repo_root: str,
    issue_key: str,
    results_markdown: str,
) -> bool:
    """Replace (not append) ## Browser Verification Results in issue body (REQ-11)."""
    issue_data = entities.find_issue_by_slug(repo_root, issue_key)
    if not issue_data:
        return False

    issue_path = issue_data.get("file_path") or issue_data.get("path")
    if not issue_path or not os.path.isfile(issue_path):
        return False

    content = textio.read_text(issue_path)
    block = frontmatter.split(content)
    if not block:
        return False

    body = block.body

    # Pattern to match existing ## Browser Verification Results section up to next ## or EOF
    pattern = re.compile(
        r"^## Browser Verification Results\b.*?(?=(^## |\Z))",
        re.MULTILINE | re.DOTALL,
    )

    clean_results = results_markdown.strip() + "\n\n"
    if pattern.search(body):
        new_body = pattern.sub(clean_results, body)
    else:
        new_body = body.rstrip() + "\n\n" + clean_results

    new_content = block.bom + block.open_delim + block.raw + block.close_delim + new_body
    textio.write_text(issue_path, new_content, newline="\n")
    return True
