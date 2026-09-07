#!/usr/bin/env python3
"""
alongkit.budget - Context budget measurement, token estimation, and regression checks.

Measures bytes, character counts, and estimated tokens across:
1. auto_loaded: AGENTS.md, attached rule packs, CLAUDE.md.
2. mandatory_session_start: AGENTS.md, .along/ISSUES.md, .along/CONSTRAINTS.md (or .along/DECISIONS.md).
3. per_skill: skills/*/SKILL.md footprints.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

if __name__ == "__main__":
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along context-budget   (or: python scripts/along_exec.py context-budget)"
    )

from . import repo, version

CHARS_PER_TOKEN = 3.8

DEFAULT_BUDGET_LIMITS = {
    "agents_md_bytes": 32768,          # 32 KB (measured: ~30.8 KB)
    "issues_md_bytes": 4096,           # 4 KB (measured: ~3.2 KB)
    "constraints_md_bytes": 16384,      # 16 KB (measured: ~12.3 KB)
    "mandatory_session_bytes": 49152,  # 48 KB (measured: ~46.3 KB, down from 113 KB)
}


def estimate_tokens(char_count: int) -> int:
    """Estimate token count using standard ~3.8 chars/token ratio."""
    return int(round(char_count / CHARS_PER_TOKEN))


def measure_file(path: str, repo_root: str = "") -> Optional[Dict[str, Any]]:
    """Measure a single file for size in bytes, characters, lines, and estimated tokens."""
    if not os.path.isfile(path):
        return None
    try:
        size_bytes = os.path.getsize(path)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        char_count = len(content)
        lines = len(content.splitlines())
        rel_path = os.path.relpath(path, repo_root).replace(os.sep, "/") if repo_root else path.replace(os.sep, "/")
        return {
            "path": rel_path,
            "bytes": size_bytes,
            "chars": char_count,
            "lines": lines,
            "tokens": estimate_tokens(char_count),
        }
    except OSError:
        return None


def measure_context(repo_root: str,
                    limits: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """Analyze context costs for a repository across auto_loaded, session start, and skills."""
    effective_limits = dict(DEFAULT_BUDGET_LIMITS)
    if limits:
        effective_limits.update(limits)

    # 1. Auto-loaded files
    auto_files: List[Dict[str, Any]] = []
    agents_path = os.path.join(repo_root, "AGENTS.md")
    agents_info = measure_file(agents_path, repo_root)
    if agents_info:
        auto_files.append(agents_info)

    claude_path = os.path.join(repo_root, "CLAUDE.md")
    claude_info = measure_file(claude_path, repo_root)
    if claude_info:
        auto_files.append(claude_info)

    rules_dir = os.path.join(repo_root, ".along", "rules")
    if os.path.isdir(rules_dir):
        for root, _, files in os.walk(rules_dir):
            for fname in sorted(files):
                if fname.endswith(".md"):
                    r_info = measure_file(os.path.join(root, fname), repo_root)
                    if r_info:
                        auto_files.append(r_info)

    # 2. Mandatory session start files
    session_files: List[Dict[str, Any]] = []
    if agents_info:
        session_files.append(agents_info)

    issues_path = os.path.join(repo_root, ".along", "ISSUES.md")
    issues_info = measure_file(issues_path, repo_root)
    if issues_info:
        session_files.append(issues_info)

    # Prefer CONSTRAINTS.md if present, otherwise DECISIONS.md
    constraints_path = os.path.join(repo_root, ".along", "CONSTRAINTS.md")
    constraints_info = measure_file(constraints_path, repo_root)
    if constraints_info:
        session_files.append(constraints_info)
    else:
        decisions_path = os.path.join(repo_root, ".along", "DECISIONS.md")
        decisions_info = measure_file(decisions_path, repo_root)
        if decisions_info:
            session_files.append(decisions_info)

    # 3. Per-skill footprints
    skill_items: List[Dict[str, Any]] = []
    skills_dir = os.path.join(repo_root, "skills")
    if os.path.isdir(skills_dir):
        for name in sorted(os.listdir(skills_dir)):
            skill_manifest = os.path.join(skills_dir, name, "SKILL.md")
            if os.path.isfile(skill_manifest):
                s_info = measure_file(skill_manifest, repo_root)
                if s_info:
                    s_info["name"] = name
                    skill_items.append(s_info)

    def summarize_files(file_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        t_bytes = sum(item["bytes"] for item in file_list)
        t_chars = sum(item["chars"] for item in file_list)
        t_lines = sum(item["lines"] for item in file_list)
        t_tokens = sum(item["tokens"] for item in file_list)
        return {
            "total_bytes": t_bytes,
            "total_chars": t_chars,
            "total_lines": t_lines,
            "total_tokens": t_tokens,
            "file_count": len(file_list),
            "files": file_list,
        }

    auto_summary = summarize_files(auto_files)
    session_summary = summarize_files(session_files)

    skills_bytes = sum(s["bytes"] for s in skill_items)
    skills_tokens = sum(s["tokens"] for s in skill_items)
    skills_summary = {
        "total_skills": len(skill_items),
        "total_bytes": skills_bytes,
        "total_tokens": skills_tokens,
        "mean_bytes": int(round(skills_bytes / len(skill_items))) if skill_items else 0,
        "skills": skill_items,
    }

    # Budget checks
    checks: Dict[str, Dict[str, Any]] = {}
    actual_agents = agents_info["bytes"] if agents_info else 0
    checks["agents_md_bytes"] = {
        "limit": effective_limits["agents_md_bytes"],
        "actual": actual_agents,
        "passed": actual_agents <= effective_limits["agents_md_bytes"],
    }

    actual_issues = issues_info["bytes"] if issues_info else 0
    checks["issues_md_bytes"] = {
        "limit": effective_limits["issues_md_bytes"],
        "actual": actual_issues,
        "passed": actual_issues <= effective_limits["issues_md_bytes"],
    }

    actual_constraints = constraints_info["bytes"] if constraints_info else 0
    checks["constraints_md_bytes"] = {
        "limit": effective_limits["constraints_md_bytes"],
        "actual": actual_constraints,
        "passed": (actual_constraints <= effective_limits["constraints_md_bytes"]) if constraints_info else True,
    }

    actual_session = session_summary["total_bytes"]
    checks["mandatory_session_bytes"] = {
        "limit": effective_limits["mandatory_session_bytes"],
        "actual": actual_session,
        "passed": actual_session <= effective_limits["mandatory_session_bytes"],
    }

    all_passed = all(c["passed"] for c in checks.values())

    return {
        "protocol": "along",
        "protocol_version": version.CURRENT_PROTOCOL_VERSION,
        "repo_root": repo_root.replace(os.sep, "/"),
        "chars_per_token": CHARS_PER_TOKEN,
        "categories": {
            "auto_loaded": auto_summary,
            "mandatory_session_start": session_summary,
            "per_skill": skills_summary,
        },
        "summary": {
            "mandatory_startup_bytes": session_summary["total_bytes"],
            "mandatory_startup_tokens": session_summary["total_tokens"],
        },
        "checks": checks,
        "all_passed": all_passed,
    }


def format_budget_text(report: Dict[str, Any]) -> str:
    """Format human-readable budget report."""
    cats = report["categories"]
    auto = cats["auto_loaded"]
    session = cats["mandatory_session_start"]
    skills = cats["per_skill"]
    checks = report["checks"]

    lines = [
        "=== Along Context Budget Report ===",
        f"Repository: {report['repo_root']}",
        f"Protocol:   Along v{report['protocol_version']} (ratio: {report['chars_per_token']} chars/token)",
        "",
        f"1. Auto-loaded files: {auto['total_bytes']:,} bytes (~{auto['total_tokens']:,} tokens, {auto['file_count']} files)",
    ]
    for f in auto["files"]:
        lines.append(f"   - {f['path']:<35} {f['bytes']:>8,} bytes  ~{f['tokens']:>6,} tokens")

    lines.extend([
        "",
        f"2. Mandatory Session-Start: {session['total_bytes']:,} bytes (~{session['total_tokens']:,} tokens, {session['file_count']} files)",
    ])
    for f in session["files"]:
        lines.append(f"   - {f['path']:<35} {f['bytes']:>8,} bytes  ~{f['tokens']:>6,} tokens")

    lines.extend([
        "",
        f"3. Skills Footprint: {skills['total_bytes']:,} bytes (~{skills['total_tokens']:,} tokens, {skills['total_skills']} skills, avg {skills['mean_bytes']:,} B)",
        "",
        "=== Budget Compliance ===",
    ])
    for check_name, c in checks.items():
        status = "[PASS]" if c["passed"] else "[FAIL]"
        lines.append(f"   {status} {check_name:<25} actual: {c['actual']:>7,} B  (limit: {c['limit']:>7,} B)")

    overall = "ALL BUDGET CHECKS PASSED" if report["all_passed"] else "BUDGET OVERRUN DETECTED"
    lines.append(f"\nResult: {overall}")
    return "\n".join(lines)
