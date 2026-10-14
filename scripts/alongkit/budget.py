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
import re
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
    # AGENTS.md without its "Project specifics" section: the protocol Along owns.
    "agents_md_bytes": 14336,          # 14 KB (measured: ~10.6 KB)
    # The repository's own "Project specifics" section: a soft limit (warns, never fails);
    # past it, move details into docs/topic--*.md and link them.
    # [debt--agents-md-budget-project-specifics]
    "project_specifics_bytes": 4096,
    "issues_md_bytes": 8192,           # 8 KB (measured: ~6.9 KB with extended backlog)
    "constraints_md_bytes": 16384,      # 16 KB (measured: ~12.3 KB)
    "mandatory_session_bytes": 36864,  # 36 KB (measured: ~29 KB)
}


def project_specifics_bytes(agents_md: str) -> int:
    """UTF-8 size of the "Project specifics" section of AGENTS.md outside the managed block.

    The section runs from its heading to the next top-level heading or the managed block,
    whichever comes first. [debt--agents-md-budget-project-specifics]
    """
    from .scaffold import MANAGED_BLOCK_RE, _SPECIFICS_HEADING_RE

    try:
        with open(agents_md, "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return 0
    outside = MANAGED_BLOCK_RE.sub("", text)
    match = _SPECIFICS_HEADING_RE.search(outside)
    if not match:
        return 0
    level = len(match.group(0)) - len(match.group(0).lstrip("#"))
    rest = outside[match.start():]
    end = re.search(rf"^#{{1,{level}}}[ \t]+\S", rest[len(match.group(0)):], re.MULTILINE)
    section = rest[:len(match.group(0)) + end.start()] if end else rest
    return len(section.encode("utf-8"))


def config_limits(repo_root: str) -> Dict[str, int]:
    """`budget` overrides from `.along/config.json` (positive integers only)."""
    import json

    path = os.path.join(repo.state_dir(repo_root), "config.json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    block = data.get("budget") if isinstance(data, dict) else None
    if not isinstance(block, dict):
        return {}
    return {k: int(v) for k, v in block.items()
            if k in DEFAULT_BUDGET_LIMITS and isinstance(v, int) and not isinstance(v, bool) and v > 0}


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
        rel_path = repo.canonical_relpath(path, repo_root) if repo_root else repo.normalize_posix(path)
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
    total_agents = agents_info["bytes"] if agents_info else 0
    specifics = project_specifics_bytes(os.path.join(repo_root, "AGENTS.md")) if agents_info else 0
    actual_agents = total_agents - specifics
    checks["agents_md_bytes"] = {
        "limit": effective_limits["agents_md_bytes"],
        "actual": actual_agents,
        "passed": actual_agents <= effective_limits["agents_md_bytes"],
        "hint": "the managed protocol block is over budget; run 'along update' or report it",
    }
    checks["project_specifics_bytes"] = {
        "limit": effective_limits["project_specifics_bytes"],
        "actual": specifics,
        "passed": True,
        "warn": specifics > effective_limits["project_specifics_bytes"],
        "hint": "move details of 'Project specifics' into docs/topic--*.md and link them",
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
        status = "[FAIL]" if not c["passed"] else ("[WARN]" if c.get("warn") else "[PASS]")
        lines.append(f"   {status} {check_name:<25} actual: {c['actual']:>7,} B  (limit: {c['limit']:>7,} B)")
        if status != "[PASS]" and c.get("hint"):
            lines.append(f"          -> {c['hint']}")

    overall = "ALL BUDGET CHECKS PASSED" if report["all_passed"] else "BUDGET OVERRUN DETECTED"
    lines.append(f"\nResult: {overall}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt Footprint and Attention Leak Detection (feat--bounded-prompt-footprint-gate)
# ---------------------------------------------------------------------------
DEFAULT_PROMPT_HARD_LIMIT_BYTES = 32768  # 32 KB (~8,623 tokens)
DEFAULT_PROMPT_SOFT_LIMIT_BYTES = 16384  # 16 KB (~4,311 tokens)
MAX_UNPARSED_LOG_LINES = 50
MAX_RAW_CODE_DUMP_LINES = 50

LOG_LINE_PATTERNS: List[re.Pattern] = [
    re.compile(r"^\s*Traceback \(most recent call last\):", re.IGNORECASE),
    re.compile(r'^\s*File "[^"]+", line \d+', re.IGNORECASE),
    re.compile(r"^\s*(?:FAIL|FAILED|ERROR|AssertionError|Exception|Error):", re.IGNORECASE),
    re.compile(r"^\s*at\s+.*\(.*:\d+:\d+\)"),
    re.compile(r"^\s*npm\s+(?:ERR!|error|warn)", re.IGNORECASE),
    re.compile(r"^\s*(?:===|---|\*\*\*)\s*(?:FAIL|ERROR|PASS|test)", re.IGNORECASE),
    re.compile(r"^\s*(?:[A-Za-z0-9_.-]+(?:\.py|\.ts|\.js|\.rs|\.go|\.cs):\d+:\d+: (?:error|warning):)", re.IGNORECASE),
    re.compile(r"^\s*\d+\s+(?:failed|passed|skipped|errors)\b", re.IGNORECASE),
    re.compile(r"^\s*(?:Ran \d+ tests? in|PASSED in|FAILED in)\b", re.IGNORECASE),
    re.compile(r"^\s*\[(?:INFO|DEBUG|WARN|WARNING|ERROR|CRITICAL|FAIL|OK)\]", re.IGNORECASE),
]

CODE_FENCE_RE = re.compile(r"```([a-zA-Z0-9_-]*)\r?\n(.*?)\r?\n```", re.DOTALL)
REVIEW_MANIFEST_RE = re.compile(r"Gate Execution Manifest:", re.IGNORECASE)
REVIEW_VERDICT_RE = re.compile(r"\bVERDICT:\s*(?:PASS|FAIL)\b", re.IGNORECASE)
STEP_REVIEW_HEADING_RE = re.compile(r"^#+\s*Step\s+\d+\s+Review\b", re.MULTILINE | re.IGNORECASE)


def detect_attention_leaks(text: str) -> List[Dict[str, Any]]:
    """Detect prompt context bloat anti-patterns.

    Identifies:
    1. Unparsed log outputs (> 50 lines).
    2. Repetition of previous passed step reviews.
    3. Embedding raw file dumps (> 50 lines).
    """
    leaks: List[Dict[str, Any]] = []

    # 1. Unparsed log outputs
    # Check within code fences
    fences = CODE_FENCE_RE.findall(text)
    for lang, body in fences:
        body_lines = [l for l in body.splitlines() if l.strip()]
        line_count = len(body_lines)
        if line_count > MAX_UNPARSED_LOG_LINES:
            log_matches = sum(1 for line in body_lines if any(pat.search(line) for pat in LOG_LINE_PATTERNS))
            is_log_lang = lang.lower() in ("log", "logs", "txt", "output", "bash", "sh", "console", "terminal", "stdout", "stderr")
            if (log_matches >= 10 or (log_matches / line_count >= 0.25)) or is_log_lang:
                leaks.append({
                    "type": "unparsed_log",
                    "severity": "warning",
                    "lines": line_count,
                    "description": f"Unparsed log output detected ({line_count} lines > {MAX_UNPARSED_LOG_LINES}). Use distilled summaries instead of full log dumps.",
                })

    # Check un-fenced continuous log blocks
    raw_lines = text.splitlines()
    consecutive_log_lines = 0
    for line in raw_lines:
        if any(pat.search(line) for pat in LOG_LINE_PATTERNS):
            consecutive_log_lines += 1
        elif consecutive_log_lines > 0 and not line.strip():
            # Allow blank lines within logs
            continue
        else:
            if consecutive_log_lines > MAX_UNPARSED_LOG_LINES:
                leaks.append({
                    "type": "unparsed_log",
                    "severity": "warning",
                    "lines": consecutive_log_lines,
                    "description": f"Unparsed log block detected ({consecutive_log_lines} consecutive lines > {MAX_UNPARSED_LOG_LINES}). Distill error outputs before prompt injection.",
                })
            consecutive_log_lines = 0
    if consecutive_log_lines > MAX_UNPARSED_LOG_LINES:
        leaks.append({
            "type": "unparsed_log",
            "severity": "warning",
            "lines": consecutive_log_lines,
            "description": f"Unparsed log block detected ({consecutive_log_lines} consecutive lines > {MAX_UNPARSED_LOG_LINES}). Distill error outputs before prompt injection.",
        })

    # 2. Repetition of previous passed step reviews
    manifest_count = len(REVIEW_MANIFEST_RE.findall(text))
    verdict_count = len(REVIEW_VERDICT_RE.findall(text))
    heading_count = len(STEP_REVIEW_HEADING_RE.findall(text))
    max_review_indicators = max(manifest_count, verdict_count, heading_count)
    if max_review_indicators > 1:
        leaks.append({
            "type": "repeated_reviews",
            "severity": "warning",
            "count": max_review_indicators,
            "description": f"Repeated historical review artifacts detected ({max_review_indicators} instances). Isolate context to the active step instead of re-injecting prior reviews.",
        })

    # 3. Embedding raw file dumps (> 50 lines)
    code_langs = (
        "py", "python", "ts", "typescript", "js", "javascript", "json", "yaml", "yml",
        "rust", "rs", "go", "c", "cpp", "cs", "html", "css", "sql", "sh", "bash", "ps1",
    )
    for lang, body in fences:
        body_lines = body.splitlines()
        line_count = len(body_lines)
        if line_count > MAX_RAW_CODE_DUMP_LINES:
            # Distinguish source code from log output
            is_code_lang = lang.lower() in code_langs
            has_code_syntax = any(re.search(r"^\s*(?:def\s+|class\s+|import\s+|from\s+|function\s+|const\s+|let\s+|var\s+|interface\s+|type\s+|public\s+|private\s+)", l) for l in body_lines)
            if is_code_lang or has_code_syntax:
                # Avoid duplicate flagging if already flagged as unparsed_log
                if not any(l["type"] == "unparsed_log" and l.get("lines") == line_count for l in leaks):
                    leaks.append({
                        "type": "raw_file_dump",
                        "severity": "warning",
                        "lines": line_count,
                        "description": f"Embedded raw source code dump ({line_count} lines > {MAX_RAW_CODE_DUMP_LINES}). Reference files by path and line anchors (e.g. path#L1-L50) instead.",
                    })

    return leaks


def check_prompt(
    payload_or_path: str,
    limits: Optional[Dict[str, int]] = None,
    allow_oversized: bool = False,
) -> Dict[str, Any]:
    """Measure prompt payload footprint, compare against bounds, and detect attention leaks."""
    text = payload_or_path
    path: Optional[str] = None
    if os.path.isfile(payload_or_path):
        path = payload_or_path
        try:
            with open(payload_or_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            text = payload_or_path

    size_bytes = len(text.encode("utf-8"))
    char_count = len(text)
    line_count = len(text.splitlines())
    token_est = estimate_tokens(char_count)

    hard_limit = (limits or {}).get("hard_limit_bytes", DEFAULT_PROMPT_HARD_LIMIT_BYTES)
    soft_limit = (limits or {}).get("soft_limit_bytes", DEFAULT_PROMPT_SOFT_LIMIT_BYTES)

    leaks = detect_attention_leaks(text)
    is_oversized = size_bytes > hard_limit
    passed = (not is_oversized or allow_oversized)
    warn = (size_bytes > soft_limit) or bool(leaks)

    if not passed:
        status = "FAIL"
    elif warn:
        status = "WARN"
    else:
        status = "PASS"

    return {
        "path": path,
        "bytes": size_bytes,
        "chars": char_count,
        "lines": line_count,
        "tokens": token_est,
        "hard_limit_bytes": hard_limit,
        "soft_limit_bytes": soft_limit,
        "allow_oversized": allow_oversized,
        "is_oversized": is_oversized,
        "passed": passed,
        "warn": warn,
        "status": status,
        "leaks": leaks,
    }


def format_prompt_budget_text(report: Dict[str, Any]) -> str:
    """Format human-readable terminal report for prompt footprint and attention leaks."""
    status_tag = f"[{report['status']}]"
    lines = [
        "=== Along Prompt Footprint & Attention Leak Report ===",
        f"Status:      {status_tag}",
        f"Footprint:   {report['bytes']:,} bytes (~{report['tokens']:,} tokens, {report['lines']:,} lines, {report['chars']:,} chars)",
        f"Thresholds:  Soft: {report['soft_limit_bytes']:,} B | Hard: {report['hard_limit_bytes']:,} B",
        f"Override:    {report['allow_oversized']}",
    ]
    if report.get("path"):
        lines.append(f"Source File: {report['path']}")

    leaks = report.get("leaks", [])
    lines.append("")
    if not leaks:
        lines.append("Attention Leaks: None detected (Clean O(1) prompt footprint)")
    else:
        lines.append(f"Attention Leaks ({len(leaks)} detected):")
        for idx, leak in enumerate(leaks, 1):
            sev = f"[{leak.get('severity', 'warning').upper()}]"
            ltype = leak.get("type", "unknown")
            desc = leak.get("description", "")
            lines.append(f"  {idx}. {sev} {ltype}: {desc}")

    if report["status"] == "FAIL":
        lines.append("\nResult: PROMPT BUDGET EXCEEDED (Hard limit violation without override)")
    elif report["status"] == "WARN":
        lines.append("\nResult: PROMPT BUDGET ADVISORY (Threshold warning or attention leaks present)")
    else:
        lines.append("\nResult: ALL PROMPT CHECKS PASSED")

    return "\n".join(lines)
