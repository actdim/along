#!/usr/bin/env python3
"""
alongkit.entities.stubs - Scaffold detection, criteria validation, and section linting.
[debt--split-along-exec-and-entities]
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: python .along/scripts/test.py"
    )

import os
import re
from typing import Any, Dict, List, Tuple

from .vocabulary import DELIVERED_ISSUE_STATUSES

_CRITERION_RE = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+")

SCAFFOLD_PLACEHOLDER_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(r"^\s*Describe the (?:feature|bug|technical debt|documentation|spike|problem)(?:[,\s]|$)", re.IGNORECASE),
    re.compile(r"^\s*Task requirement \d+\b", re.IGNORECASE),
    re.compile(r"\[Subject\]\s+MUST", re.IGNORECASE),
)


def acceptance_criteria(body: str) -> Tuple[int, int]:
    """(ticked, total) checkboxes under the issue's Acceptance Criteria heading."""
    ticked = total = 0
    inside = fence = False
    for line in (body or "").splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
            continue
        if fence:
            continue
        if line.startswith("## "):
            inside = line[3:].strip().lower().startswith("acceptance criteria")
            continue
        m = _CRITERION_RE.match(line) if inside else None
        if m:
            total += 1
            ticked += m.group(1) in "xX"
    return ticked, total


def is_issue_stub(content: str) -> Tuple[bool, List[str]]:
    """Check if an issue body contains default scaffold placeholder text or stub criteria."""
    from .. import frontmatter, markdown
    fm, body, _ = frontmatter.try_parse(content)
    body_text = body if fm is not None else content
    tracker = markdown.FenceTracker()
    reasons: List[str] = []

    for line_idx, line in enumerate(body_text.splitlines(), start=1):
        if tracker.process_line(line):
            continue
        if tracker.in_fence:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("`") or stripped.startswith(">"):
            continue
        for pattern in SCAFFOLD_PLACEHOLDER_PATTERNS:
            if pattern.search(stripped):
                reasons.append(f"Line {line_idx}: Contains template placeholder text: '{stripped}'")
                break

    criteria_items = markdown.extract_all_checklist_items(body_text)
    if criteria_items:
        non_stub_items = [
            text for is_ticked, text in criteria_items
            if not re.search(r"^\s*Task requirement \d+\b", text, re.IGNORECASE)
            and text.lower() != "automated tests passing"
        ]
        if not non_stub_items:
            reasons.append(
                "Acceptance Criteria contains only default scaffold items "
                "('Task requirement 1', 'Automated tests passing'). Specify concrete criteria."
            )

    return (len(reasons) > 0, reasons)


def validate_issue_completion(content: str, status: str = "done") -> Tuple[bool, List[str]]:
    """Validate that an issue is complete and ready to be closed into done/."""
    from .. import markdown
    if status not in DELIVERED_ISSUE_STATUSES:
        return (True, [])

    reasons: List[str] = []
    is_stub, stub_reasons = is_issue_stub(content)
    if is_stub:
        reasons.extend(stub_reasons)

    has_ac_heading = bool(re.search(r"^##\s+Acceptance Criteria\b", content, re.IGNORECASE | re.MULTILINE))
    ticked, total = acceptance_criteria(content)
    if not has_ac_heading:
        reasons.append("Missing mandatory '## Acceptance Criteria' section.")
    elif total == 0:
        reasons.append("Acceptance Criteria section has no checklist items (- [ ] or - [x]).")
    elif ticked == 0:
        reasons.append("No completed checklist items found in Acceptance Criteria (- [x]).")

    unchecked = markdown.extract_unchecked_checklist_items(content)
    if unchecked:
        reasons.append(
            f"Found {len(unchecked)} uncompleted checklist item(s) (- [ ]): "
            + "; ".join(f"'- [ ] {item}'" for item in unchecked[:3])
            + (f" and {len(unchecked) - 3} more" if len(unchecked) > 3 else "")
        )

    return (len(reasons) == 0, reasons)


def audit_stub_issues(repo_root: str) -> List[Dict[str, Any]]:
    """Audit all active and completed issues in the repository for stubs or incomplete criteria."""
    from .. import repo, textio
    from .query import scan_issues

    issues = scan_issues(repo_root, include_done=True)
    findings: List[Dict[str, Any]] = []
    for iss in issues:
        fpath = iss.get("file_path")
        if not fpath or not os.path.isfile(fpath):
            continue
        try:
            content = textio.read_text(fpath, strict=False)
        except OSError:
            continue
        is_stub, stub_reasons = is_issue_stub(content)
        is_done = iss.get("done") or iss.get("status") in DELIVERED_ISSUE_STATUSES
        comp_ok, comp_reasons = validate_issue_completion(content, iss.get("status", "open")) if is_done else (True, [])
        all_reasons = list(dict.fromkeys(stub_reasons + comp_reasons))
        if all_reasons:
            rel = repo.safe_relpath(fpath, repo_root).replace("\\", "/")
            findings.append({
                "slug": iss["slug"],
                "type": iss.get("type", "task"),
                "status": iss.get("status", "open"),
                "path": rel,
                "is_done": is_done,
                "reasons": all_reasons,
            })
    return findings


def lint_issue_sections(content: str) -> List[str]:
    """Check an issue body for mandatory sections: Problem, Requirements, Acceptance Criteria."""
    missing = []
    if not re.search(r"^#{1,3}\s+(?:\d+\.\s+)?Problem\b", content, re.IGNORECASE | re.MULTILINE):
        missing.append("Problem")
    if not re.search(r"^#{1,3}\s+(?:\d+\.\s+)?(?:Requirements|Architecture)\b", content, re.IGNORECASE | re.MULTILINE):
        missing.append("Requirements or Architecture")
    if not re.search(r"^#{1,3}\s+(?:\d+\.\s+)?Acceptance Criteria\b", content, re.IGNORECASE | re.MULTILINE):
        missing.append("Acceptance Criteria")
    return missing


def lint_issues(repo_root: str, strict: bool = False) -> Dict[str, Any]:
    """Audit active issues against structural section contracts."""
    from .. import repo, textio
    from .query import scan_issues

    issues = scan_issues(repo_root)
    findings = []
    for iss in issues:
        fpath = iss.get("file_path")
        if not fpath or not os.path.isfile(fpath):
            continue
        try:
            content = textio.read_text(fpath)
        except OSError:
            continue
        missing = lint_issue_sections(content)
        if missing:
            rel = repo.safe_relpath(fpath, repo_root)
            findings.append({"slug": iss["slug"], "path": rel, "missing": missing})
    return {
        "scanned": len(issues),
        "findings": findings,
        "clean": len(findings) == 0,
    }
