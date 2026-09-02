#!/usr/bin/env python3
"""
along_history_sync.py - Reconstruct and reconcile .along/ project history from Git commits, tags, and PRs.

Analyzes Git commits, tags, and history to synthesize missing .along/ entities
(ISSUES/done/, MILESTONES/, SESSIONS/, HISTORY.md) with `protocol: along`.

Usage:
    python skills/along-history-sync/along_history_sync.py [REPO_ROOT] [OPTIONS]
    Options:
      --check           Inspect and report unmapped commits without creating files (default).
      --synthesize      Synthesize missing session logs and done issues in .along/.
      --limit <N>       Limit number of commits to scan (default: 100).
      --json            Output report in structured JSON format.
      --quiet / -q      Minimal console output.
"""

import os
import sys
import json
import re
import argparse
import glob
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap
bootstrap.ensure_deps()


from alongkit import proc, repo


def run_git_cmd(args: List[str], cwd: Optional[str] = None) -> str:
    """Stdout of a git command, or an empty string when it fails."""
    res = proc.git(args, cwd=cwd or os.getcwd())
    if not res.ok:
        print(f"Git error: {res.stderr.strip()}", file=sys.stderr)
        return ""
    return res.out


def get_mapped_commits(agents_dir: str) -> Set[str]:
    mapped_commits = set()
    scan_files = (
        glob.glob(os.path.join(agents_dir, "SESSIONS", "**", "*.md"), recursive=True)
        + glob.glob(os.path.join(agents_dir, "ISSUES", "**", "*.md"), recursive=True)
    )
    for sf in scan_files:
        try:
            with open(sf, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            for m in re.finditer(r"commit:\s*([a-fA-F0-9]+)", content):
                mapped_commits.add(m.group(1).strip()[:7].lower())
            for m in re.finditer(r"commits(?:_covered)?:\s*\[([^\]]+)\]", content):
                for h in m.group(1).split(","):
                    clean = h.strip().strip("'\"")[:7].lower()
                    if clean:
                        mapped_commits.add(clean)
            for m in re.finditer(r"`([a-fA-F0-9]{7,40})`", content):
                mapped_commits.add(m.group(1).strip()[:7].lower())
        except Exception:
            pass
    return mapped_commits


def get_git_tags(repo_root: str) -> List[Dict[str, str]]:
    tags_raw = run_git_cmd(["tag", "-l", "--sort=-creatordate", "--format=%(refname:short)|%(creatordate:short)|%(subject)"], repo_root)
    tags = []
    for line in tags_raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("|", 2)
        if len(parts) >= 2:
            tags.append({
                "tag": parts[0],
                "date": parts[1],
                "subject": parts[2] if len(parts) > 2 else ""
            })
    return tags


def extract_commits(repo_root: str, max_count: int = 100) -> List[Dict[str, Any]]:
    cmd = ["log", f"-n{max_count}", "--pretty=format:%H|%h|%an|%ad|%s", "--date=short"]
    raw_log = run_git_cmd(cmd, repo_root)
    commits = []
    for line in raw_log.splitlines():
        if not line.strip():
            continue
        parts = line.split("|", 4)
        if len(parts) == 5:
            full_hash, short_hash, author, c_date, subject = parts
            c_type = "feat"
            lower_s = subject.lower()
            if lower_s.startswith("fix") or "bug" in lower_s:
                c_type = "bug"
            elif lower_s.startswith("refactor") or "debt" in lower_s or "clean" in lower_s:
                c_type = "debt"
            elif lower_s.startswith("docs") or "readme" in lower_s:
                c_type = "docs"
            elif lower_s.startswith("test") or "chore" in lower_s:
                c_type = "task"

            # Clean slug
            slug_cand = re.sub(r"^(?:feat|fix|refactor|docs|test|chore|style|perf)(?:\([^)]+\))?:\s*", "", subject, flags=re.IGNORECASE)
            slug = re.sub(r"[^a-zA-Z0-9]+", "-", slug_cand).strip("-").lower()
            if len(slug) > 40:
                slug = slug[:40].rstrip("-")
            if not slug:
                slug = f"commit-{short_hash}"

            commits.append({
                "full_hash": full_hash,
                "short_hash": short_hash,
                "author": author,
                "date": c_date,
                "subject": subject,
                "inferred_type": c_type,
                "slug": slug,
            })
    return commits


def synthesize_history_entities(repo_root: str, unmapped_commits: List[Dict[str, Any]]) -> Tuple[int, int]:
    """Synthesize missing done issues and sessions in .along/ from unmapped commits."""
    along_dir = os.path.join(repo_root, ".along")
    os.makedirs(along_dir, exist_ok=True)
    done_issues_dir = os.path.join(along_dir, "ISSUES", "done")
    os.makedirs(done_issues_dir, exist_ok=True)
    sessions_dir = os.path.join(along_dir, "SESSIONS")
    os.makedirs(sessions_dir, exist_ok=True)
    history_file = os.path.join(along_dir, "HISTORY.md")

    issues_created = 0
    sessions_created = 0
    history_lines = []

    for c in reversed(unmapped_commits):
        c_date = c["date"]
        c_year = c_date.split("-")[0] if "-" in c_date else "2026"
        c_type = c["inferred_type"]
        slug = c["slug"]
        short_hash = c["short_hash"]
        full_hash = c["full_hash"]
        subject = c["subject"].replace('"', "'")

        # 1. Synthesize Done Issue
        issue_file = os.path.join(done_issues_dir, f"{c_type}--{slug}.md")
        if not os.path.exists(issue_file):
            issue_content = f"""---
protocol: along
slug: {slug}
type: {c_type}
status: done
priority: medium
created: {c_date}
updated: {c_date}
completed: {c_date}
agent: git-reconstructed
tags: [git-reconstructed]
---

# {subject}

Reconstructed from Git commit `{short_hash}`.

## Commit Details
- Hash: `{full_hash}`
- Author: {c['author']}
- Date: {c_date}
"""
            with open(issue_file, "w", encoding="utf-8", newline="\n") as f:
                f.write(issue_content)
            issues_created += 1

        # 2. Synthesize Session Log
        year_dir = os.path.join(sessions_dir, c_year)
        os.makedirs(year_dir, exist_ok=True)
        session_file = os.path.join(year_dir, f"{c_date}--{slug}.md")
        if not os.path.exists(session_file):
            session_content = f"""---
protocol: along
date: {c_date}
slug: {slug}
agent: git-reconstructed
branch: main
commit: {short_hash}
summary: "{subject}"
milestone: null
issues_advanced: []
issues_completed: [{slug}]
decisions: []
risks_logged: []
spikes_conducted: []
---

# Session Log: {subject}

## Summary of Changes
- Reconstructed retroactively from Git commit `{short_hash}` ({c_date}).
- Author: {c['author']}.
"""
            with open(session_file, "w", encoding="utf-8", newline="\n") as f:
                f.write(session_content)
            sessions_created += 1

        # 3. History entry
        rel_sess = f".along/SESSIONS/{c_year}/{c_date}--{slug}.md"
        history_lines.append(f"{c_date} - {slug} - git-reconstructed - {subject} - [{rel_sess}](file://{rel_sess})")

    # Update HISTORY.md if lines created
    if history_lines and os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                existing_hist = f.read()
            for h_line in history_lines:
                if h_line.split(" - ")[1] not in existing_hist:
                    existing_hist += "\n" + h_line
            with open(history_file, "w", encoding="utf-8", newline="\n") as f:
                f.write(existing_hist.strip() + "\n")
        except Exception:
            pass

    return issues_created, sessions_created


def run_history_sync(repo_root: str, synthesize: bool = False, limit: int = 100) -> Dict[str, Any]:
    repo_root = os.path.abspath(repo_root)
    along_dir = os.path.join(repo_root, ".along")

    mapped = get_mapped_commits(along_dir) if os.path.exists(along_dir) else set()
    tags = get_git_tags(repo_root)
    commits = extract_commits(repo_root, max_count=limit)

    unmapped = []
    for c in commits:
        short = c["short_hash"].lower()
        full = c["full_hash"].lower()
        if short not in mapped and not any(full.startswith(m) for m in mapped):
            unmapped.append(c)

    issues_created = 0
    sessions_created = 0
    if synthesize and unmapped:
        issues_created, sessions_created = synthesize_history_entities(repo_root, unmapped)

    return {
        "repo_root": repo_root,
        "total_tags": len(tags),
        "tags": tags[:10],
        "total_commits_scanned": len(commits),
        "mapped_commits_count": len(commits) - len(unmapped),
        "unmapped_commits_count": len(unmapped),
        "unmapped_commits": unmapped,
        "synthesized_issues": issues_created,
        "synthesized_sessions": sessions_created,
    }


def main():
    parser = argparse.ArgumentParser(description="Reconstruct and reconcile .along/ project history from Git commits, tags, and PRs.")
    parser.add_argument("repo_root", nargs="?", default=".", help="Target repository root directory")
    parser.add_argument("--check", action="store_true", help="Inspect and report unmapped commits without modifying files")
    parser.add_argument("--synthesize", "--apply", action="store_true", help="Synthesize missing done issues and session logs in .along/")
    parser.add_argument("--limit", type=int, default=100, help="Maximum number of commits to scan (default: 100)")
    parser.add_argument("--json", action="store_true", help="Output report in JSON format")
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal console output")

    args = parser.parse_args()
    repo_root = repo.find_repo_root(args.repo_root)

    do_synthesize = args.synthesize and not args.check
    results = run_history_sync(repo_root, synthesize=do_synthesize, limit=args.limit)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    if not args.quiet:
        print("==================================================")
        print("-> [Along Git History Reconciler] (/along-history-sync)")
        print(f"   Target Repository: {repo_root}")
        print(f"   Scanned Commits:   {results['total_commits_scanned']}")
        print(f"   Mapped Commits:    {results['mapped_commits_count']}")
        print(f"   Unmapped Commits:  {results['unmapped_commits_count']}")
        print(f"   Release Tags:      {results['total_tags']}")
        print("==================================================")

        if results["unmapped_commits"]:
            print(f"\n-> Found {results['unmapped_commits_count']} unmapped commits:")
            for c in results["unmapped_commits"][:10]:
                print(f"   - [{c['short_hash']}] {c['date']} ({c['inferred_type']}): {c['subject']}")
            if len(results["unmapped_commits"]) > 10:
                print(f"   ... and {len(results['unmapped_commits']) - 10} more.")

            if do_synthesize:
                print(f"\n[OK] Synthesized {results['synthesized_issues']} done issues and {results['synthesized_sessions']} session logs in .along/")
            else:
                print("\n[Tip] Run `python skills/along-history-sync/along_history_sync.py --synthesize` to retroactively create .along/ entities.")
        else:
            print("\n[OK] All scanned commits are mapped to .along/ project history.")


if __name__ == "__main__":
    main()
