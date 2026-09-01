#!/usr/bin/env python3
# along_kb_search.py - Unified Multi-Scope Knowledge Retrieval Engine across docs/ and .along/ artifacts.

import os
import re
import sys
import argparse

# Current format:  ## ADR-YYYY-MM-DD--<slug> - <Title>      (protocol >= v2.2.0)
# Legacy format:   ## <NNN> - <Title> / ## <NNN>: <Title>  (protocol < v2.2.0)
# A bare ISO date heading (## 2026-08-15 ...) is explicitly not an ADR.
_ADR_HEADING = (
    r"(?:ADR-\d{4}-\d{2}-\d{2}--[A-Za-z0-9._-]+|(?!\d{4}-\d{2}-\d{2})\d{1,4}\s*[-.:])"
)
ADR_SPLIT_RE = re.compile(r"\n(?=##\s+" + _ADR_HEADING + r")")
ADR_HEADER_RE = re.compile(
    r"^##\s+(?:(?P<key>ADR-\d{4}-\d{2}-\d{2}--[A-Za-z0-9._-]+)"
    r"|(?!\d{4}-\d{2}-\d{2})(?P<num>\d{1,4})\s*[-.:])"
    r"\s*(?:-\s*)?(?P<title>.*)$"
)


def github_heading_anchor(heading):
    """Mirror the GitHub Markdown heading anchor algorithm for stable deep links."""
    anchor = heading.strip().lower()
    anchor = re.sub(r"[^\w\s-]", "", anchor)
    return re.sub(r"\s+", "-", anchor).strip("-")


def parse_decision_entries(dec_raw, rel_path=".along/DECISIONS.md"):
    """
    Split an append-only DECISIONS.md into individual searchable ADR entries.

    Supports both header formats:
    - Current decentralized slug format (protocol >= v2.2.0):
        ## ADR-YYYY-MM-DD--<slug> - <Title>
    - Legacy numeric format (protocol < v2.2.0):
        ## <NNN> - <Title>

    The schema template placeholder (literal `<slug>` / `YYYY-MM-DD` header) is skipped so
    it never surfaces as a search result.
    """
    entries = []
    for blk in ADR_SPLIT_RE.split(dec_raw):
        blk = blk.strip()
        if not blk:
            continue
        lines = blk.splitlines()
        heading = lines[0].strip()
        header_m = ADR_HEADER_RE.match(heading)
        if not header_m:
            continue

        # An ADR block ends at the next level-2 heading of any kind, so unrelated
        # sections appended to the log never bleed into an ADR body or snippet.
        end = len(lines)
        for i, ln in enumerate(lines[1:], 1):
            if ln.startswith("## "):
                end = i
                break
        blk = "\n".join(lines[:end]).strip()

        key = header_m.group("key")
        human_title = (header_m.group("title") or "").strip()

        if key:
            if "<" in key or "YYYY" in key:
                continue
            adr_key = key
            slug = key.lower()
        else:
            adr_key = f"ADR-{header_m.group('num')}"
            slug = adr_key.lower()

        entries.append({
            "category": "decision",
            "category_label": "ADR",
            "title": f"{adr_key} - {human_title}" if human_title else adr_key,
            "slug": slug,
            "type": "adr",
            "tags": ["adr", "architecture", "decision"],
            "status": "superseded" if re.search(r"superseded\s+by", blk, re.IGNORECASE) else "active",
            "file_path": f"{rel_path}#{github_heading_anchor(heading.lstrip('#').strip())}",
            "body": blk,
        })
    return entries


def parse_frontmatter(content):
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", content, re.DOTALL)
    if not match:
        return {}, content
    fm_str, body = match.group(1), match.group(2)
    fm = {}
    for line in fm_str.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if v.startswith("[") and v.endswith("]"):
                items = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",") if x.strip()]
                fm[k] = items
            else:
                fm[k] = v
    return fm, body

def collect_all_entries(repo_root):
    entries = []
    repo_root = os.path.abspath(repo_root)
    docs_dir = os.path.join(repo_root, "docs")
    along_dir = os.path.join(repo_root, ".along")
    if not os.path.exists(along_dir):
        along_dir = os.path.join(repo_root, ".agents")

    # 1. Curated Knowledge Base (docs/*.md)
    if os.path.exists(docs_dir):
        for f in sorted(os.listdir(docs_dir)):
            if not f.endswith(".md") or f == "INDEX.md":
                continue
            fp = os.path.join(docs_dir, f)
            if not os.path.isfile(fp):
                continue
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as p:
                    raw = p.read()
                fm, body = parse_frontmatter(raw)
                entries.append({
                    "category": "kb",
                    "category_label": "KB Topic",
                    "title": fm.get("title", f.replace("topic--", "").replace(".md", "").replace("-", " ").title()),
                    "slug": fm.get("slug", f.replace(".md", "")),
                    "type": fm.get("type", "topic"),
                    "tags": fm.get("tags", []) if isinstance(fm.get("tags", []), list) else ([fm.get("tags")] if fm.get("tags") else []),
                    "status": "active",
                    "file_path": f"docs/{f}",
                    "body": body
                })
            except Exception:
                pass

    # 2. Issues & Backlog (.along/ISSUES/**/*.md)
    issues_dir = os.path.join(along_dir, "ISSUES")
    if os.path.exists(issues_dir):
        for root, _, files in os.walk(issues_dir):
            for f in files:
                if not f.endswith(".md"):
                    continue
                fp = os.path.join(root, f)
                try:
                    with open(fp, "r", encoding="utf-8", errors="replace") as p:
                        raw = p.read()
                    fm, body = parse_frontmatter(raw)
                    rel_path = os.path.relpath(fp, repo_root).replace("\\", "/")
                    slug = fm.get("slug", f.replace(".md", ""))
                    status = fm.get("status", "done" if "done" in rel_path else "open")
                    iss_type = fm.get("type", "task")
                    entries.append({
                        "category": "issue",
                        "category_label": f"Issue ({status})",
                        "title": f"[{iss_type.upper()}] {slug.replace('-', ' ').title()}",
                        "slug": slug,
                        "type": iss_type,
                        "tags": fm.get("tags", []) if isinstance(fm.get("tags", []), list) else ([fm.get("tags")] if fm.get("tags") else []),
                        "status": status,
                        "priority": fm.get("priority", "medium"),
                        "file_path": rel_path,
                        "body": body
                    })
                except Exception:
                    pass

    # 3. Architectural Decision Records (.along/DECISIONS.md)
    decisions_path = os.path.join(along_dir, "DECISIONS.md")
    if os.path.exists(decisions_path):
        try:
            with open(decisions_path, "r", encoding="utf-8", errors="replace") as p:
                dec_raw = p.read()
            dec_rel = os.path.relpath(decisions_path, repo_root).replace("\\", "/")
            entries.extend(parse_decision_entries(dec_raw, rel_path=dec_rel))
        except Exception:
            pass

    # 4. Milestones & Sprints (.along/MILESTONES/*.md)
    ms_dir = os.path.join(along_dir, "MILESTONES")
    if os.path.exists(ms_dir):
        for f in os.listdir(ms_dir):
            if not f.endswith(".md"):
                continue
            fp = os.path.join(ms_dir, f)
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as p:
                    raw = p.read()
                fm, body = parse_frontmatter(raw)
                rel_path = os.path.relpath(fp, repo_root).replace("\\", "/")
                entries.append({
                    "category": "milestone",
                    "category_label": "Milestone",
                    "title": fm.get("title", f.replace(".md", "").title()),
                    "slug": fm.get("slug", f.replace(".md", "")),
                    "type": "milestone",
                    "tags": ["milestone", "sprint"],
                    "status": fm.get("status", "open"),
                    "file_path": rel_path,
                    "body": body
                })
            except Exception:
                pass

    # 5. Risks & Blockers (.along/RISKS/*.md)
    risks_dir = os.path.join(along_dir, "RISKS")
    if os.path.exists(risks_dir):
        for f in os.listdir(risks_dir):
            if not f.endswith(".md"):
                continue
            fp = os.path.join(risks_dir, f)
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as p:
                    raw = p.read()
                fm, body = parse_frontmatter(raw)
                rel_path = os.path.relpath(fp, repo_root).replace("\\", "/")
                entries.append({
                    "category": "risk",
                    "category_label": f"Risk ({fm.get('severity', 'medium')})",
                    "title": fm.get("title", f.replace(".md", "").title()),
                    "slug": fm.get("slug", f.replace(".md", "")),
                    "type": "risk",
                    "tags": ["risk", "blocker", fm.get("severity", "medium")],
                    "status": fm.get("status", "active"),
                    "file_path": rel_path,
                    "body": body
                })
            except Exception:
                pass

    # 6. Spikes & R&D (.along/SPIKES/*.md)
    spikes_dir = os.path.join(along_dir, "SPIKES")
    if os.path.exists(spikes_dir):
        for f in os.listdir(spikes_dir):
            if not f.endswith(".md"):
                continue
            fp = os.path.join(spikes_dir, f)
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as p:
                    raw = p.read()
                fm, body = parse_frontmatter(raw)
                rel_path = os.path.relpath(fp, repo_root).replace("\\", "/")
                entries.append({
                    "category": "spike",
                    "category_label": "Spike R&D",
                    "title": fm.get("title", f.replace(".md", "").title()),
                    "slug": fm.get("slug", f.replace(".md", "")),
                    "type": "spike",
                    "tags": ["spike", "experiment"],
                    "status": fm.get("status", "evaluating"),
                    "file_path": rel_path,
                    "body": body
                })
            except Exception:
                pass

    # 7. Session Logs (.along/SESSIONS/**/*.md)
    sess_dir = os.path.join(along_dir, "SESSIONS")
    if os.path.exists(sess_dir):
        for root, _, files in os.walk(sess_dir):
            for f in files:
                if not f.endswith(".md"):
                    continue
                fp = os.path.join(root, f)
                try:
                    with open(fp, "r", encoding="utf-8", errors="replace") as p:
                        raw = p.read()
                    fm, body = parse_frontmatter(raw)
                    rel_p = os.path.relpath(fp, repo_root).replace("\\", "/")
                    slug = fm.get("slug", f.replace(".md", ""))
                    entries.append({
                        "category": "session",
                        "category_label": "Session Log",
                        "title": f"Session {fm.get('date', '')}: {slug.replace('-', ' ').title()}",
                        "slug": slug,
                        "type": "session",
                        "tags": ["session", "log"],
                        "status": "completed",
                        "file_path": rel_p,
                        "body": body
                    })
                except Exception:
                    pass

    return entries

def search_knowledge_base(query, repo_root=".", limit=5, category=None, filter_tag=None):
    repo_root = os.path.abspath(repo_root)
    query_terms = [t.lower().strip() for t in query.split() if t.strip()]
    entries = collect_all_entries(repo_root)

    results = []
    for e in entries:
        if category and category.lower() != "all" and e["category"].lower() != category.lower():
            continue
        if filter_tag and filter_tag.lower() not in [t.lower() for t in e["tags"]]:
            continue

        title_lower = e["title"].lower()
        slug_lower = e["slug"].lower()
        body_lower = e["body"].lower()
        tags_lower = [t.lower() for t in e["tags"]]

        term_matches = 0
        score = 0.0
        for term in query_terms:
            if term in title_lower or term in slug_lower:
                score += 10.0
                term_matches += 1
            for t in tags_lower:
                if term in t:
                    score += 5.0
                    term_matches += 1
            matches = body_lower.count(term)
            if matches > 0:
                score += min(matches * 1.0, 10.0)
                term_matches += matches

        if query_terms and term_matches == 0:
            continue

        # Category boost for active items
        if e.get("status") in ["open", "in-progress", "active"]:
            score += 2.0

        snippet = ""
        if query_terms:
            pos = body_lower.find(query_terms[0])
            if pos != -1:
                start = max(0, pos - 80)
                end = min(len(e["body"]), pos + 150)
                snippet = e["body"][start:end].replace("\n", " ").strip()
        if not snippet:
            snippet = e["body"][:180].replace("\n", " ").strip()

        results.append({
            "category": e["category"],
            "category_label": e["category_label"],
            "title": e["title"],
            "slug": e["slug"],
            "status": e.get("status", "active"),
            "file_path": e["file_path"],
            "tags": e["tags"],
            "score": score,
            "snippet": snippet
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]

def main():
    parser = argparse.ArgumentParser(description="Along Unified Knowledge & Memory Retrieval Engine")
    parser.add_argument("query", nargs="?", default="", help="Search query terms")
    parser.add_argument("--repo", default=".", help="Target repository root")
    parser.add_argument("--limit", type=int, default=8, help="Maximum results to return")
    parser.add_argument("--category", choices=["all", "kb", "issue", "decision", "milestone", "risk", "spike", "session"], default="all", help="Filter by knowledge category")
    parser.add_argument("--tag", default=None, help="Filter by specific tag")
    args = parser.parse_args()

    results = search_knowledge_base(args.query, repo_root=args.repo, limit=args.limit, category=args.category, filter_tag=args.tag)
    print(f"=== Along Unified Knowledge Search: '{args.query}' ({len(results)} matches) ===")
    for i, r in enumerate(results, 1):
        tags_str = ", ".join(r["tags"]) if r["tags"] else "none"
        print(f"{i}. [{r['category_label']}] {r['title']} (./{r['file_path']})")
        print(f"   \"{r['snippet']}...\"\n")

if __name__ == "__main__":
    main()
