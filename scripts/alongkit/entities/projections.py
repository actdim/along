#!/usr/bin/env python3
"""
alongkit.entities.projections - Board rendering and compilation for ISSUES.md.
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
from typing import Any, Dict, Optional

from .vocabulary import RECENT_DONE_LIMIT, canonical_key, parse_key
from .query import _ref_key, scan_issues

_PLAN_STATUS_NOTES: Dict[str, str] = {
    "approved": " - plan approved",
    "needs-approval": " - plan: needs approval",
    "needs-rework": " - plan: needs rework",
}

BOARD_ENTRY_RE = re.compile(
    r"^-\s+\[(?P<box>[ xX~])\]\s+`\((?P<type>\w+)\)`\s+\[(?P<slug>[^\]]+)\]\((?P<link>[^\)]+)\)"
)


def format_board_entry(entity_type: str, slug: str, done: bool = False, link: Optional[str] = None) -> str:
    """Render one item on the ISSUES.md projection board."""
    box = "x" if done else " "
    default_link = f"ISSUES/done/{entity_type}--{slug}.md" if done else f"ISSUES/{entity_type}--{slug}.md"
    target_link = link or default_link
    return f"- [{box}] `({entity_type})` [{slug}]({target_link})"


def parse_board_entry(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single board entry line, returning dict with type, slug, done, link, or None."""
    m = BOARD_ENTRY_RE.match(line.strip())
    if not m:
        return None
    return {
        "type": m.group("type"),
        "slug": m.group("slug"),
        "done": m.group("box").lower() == "x",
        "link": m.group("link"),
    }


def _format_external_children(repo_root: str, ext_children: List[Tuple[str, str]]) -> str:
    if not ext_children:
        return ""
    child_links = []
    for q, k in ext_children:
        short_q = os.path.basename(q) if "/" in q else q
        display = f"{short_q}:{k}"
        sub_along = os.path.join(repo_root, q, ".along", "ISSUES")
        if os.path.isfile(os.path.join(sub_along, "done", f"{k}.md")):
            target = f"{q}/.along/ISSUES/done/{k}.md"
        else:
            target = f"{q}/.along/ISSUES/{k}.md"
        child_links.append(f"[{display}]({target})")
    return f"\n  - External Children: {', '.join(child_links)}"


def compile_issues_board(repo_root: str, recent_done_limit: int = RECENT_DONE_LIMIT) -> str:
    """Compile active issues, backlog issues, and recent completed issues into ISSUES.md content."""
    from .. import frontmatter, repo, textio
    issues_dir = os.path.join(repo.state_dir(repo_root), "ISSUES")
    done_dir = os.path.join(issues_dir, "done")
    active_items = []
    backlog_items = []
    done_items = []

    subproject_children: Dict[str, List[Tuple[str, str]]] = {}
    try:
        contexts = repo.find_agent_contexts(repo_root)
        for ctx in contexts:
            if repo._same_path(ctx, repo_root):
                continue
            sub_rel = repo.canonical_relpath(ctx, repo_root)
            for s_iss in scan_issues(ctx, include_done=True):
                s_fm = s_iss.get("frontmatter") or {}
                p = s_fm.get("parent")
                if p:
                    _, p_clean = _ref_key(p)
                    _, p_slug = parse_key(p_clean)
                    k = canonical_key(s_iss["type"], s_iss["slug"])
                    subproject_children.setdefault(p_slug, []).append((sub_rel, k))
                    subproject_children.setdefault(p_clean, []).append((sub_rel, k))
    except (OSError, ValueError):
        pass

    if os.path.exists(issues_dir):
        for f in sorted(os.listdir(issues_dir)):
            if f.endswith(".md") and os.path.isfile(os.path.join(issues_dir, f)):
                parts = f[:-3].split("--", 1)
                itype = parts[0]
                islug = parts[1] if len(parts) > 1 else f[:-3]
                fpath = os.path.join(issues_dir, f)
                istatus = "open"
                plan_note = ""
                fm: Dict[str, Any] = {}
                try:
                    content = textio.read_text(fpath)
                    fm, _, _ = frontmatter.try_parse(content, path=fpath)
                    if fm.get("status"):
                        istatus = str(fm["status"]).lower()
                    # The ticket's plan status [feat--pre-approved-plans]; a marker only, never approval.
                    plan_note = _PLAN_STATUS_NOTES.get(str(fm.get("plan_status") or "").strip().lower(), "")
                except (OSError, ValueError):
                    pass

                entry = f"- [ ] `({itype})` [{islug}](ISSUES/{f}){plan_note}"
                canon_key = canonical_key(itype, islug)
                ext_children: List[Tuple[str, str]] = []
                for item in subproject_children.get(islug, []) + subproject_children.get(canon_key, []):
                    if item not in ext_children:
                        ext_children.append(item)
                fm_children = fm.get("children") or []
                if isinstance(fm_children, list):
                    for c in fm_children:
                        cq, ck = _ref_key(c)
                        if cq and cq != "root" and (cq, ck) not in ext_children:
                            ext_children.append((cq, ck))
                entry += _format_external_children(repo_root, ext_children)

                if istatus == "in-progress":
                    active_items.append(entry)
                else:
                    backlog_items.append(entry)

    if os.path.exists(done_dir):
        done_records = []
        for f in os.listdir(done_dir):
            if f.endswith(".md") and os.path.isfile(os.path.join(done_dir, f)):
                parts = f[:-3].split("--", 1)
                itype = parts[0]
                islug = parts[1] if len(parts) > 1 else f[:-3]
                fpath = os.path.join(done_dir, f)
                comp_date = ""
                istatus = "done"
                fm_done: Dict[str, Any] = {}
                try:
                    content = textio.read_text(fpath)
                    fm_done, _, _ = frontmatter.try_parse(content, path=fpath)
                    if fm_done.get("status"):
                        istatus = str(fm_done["status"]).lower()
                    if fm_done.get("completed"):
                        comp_date = str(fm_done["completed"])
                    elif fm_done.get("created"):
                        comp_date = str(fm_done["created"])
                except (OSError, ValueError):
                    pass
                if not comp_date:
                    try:
                        from datetime import datetime
                        comp_date = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d")
                    except OSError:
                        comp_date = "1970-01-01"
                done_records.append((comp_date, f, itype, islug, istatus, fm_done))

        done_records.sort(key=lambda x: (x[0], x[1]), reverse=True)
        total_done = len(done_records)

        for comp_date, f, itype, islug, istatus, fm_done in done_records[:recent_done_limit]:
            box = "~" if istatus in ("superseded", "cancelled", "duplicate") else "x"
            canon_key = canonical_key(itype, islug)
            ext_children = []
            for item in subproject_children.get(islug, []) + subproject_children.get(canon_key, []):
                if item not in ext_children:
                    ext_children.append(item)
            fm_children = fm_done.get("children") or []
            if isinstance(fm_children, list):
                for c in fm_children:
                    cq, ck = _ref_key(c)
                    if cq and cq != "root" and (cq, ck) not in ext_children:
                        ext_children.append((cq, ck))
            done_entry = f"- [{box}] `({itype})` [{islug}](ISSUES/done/{f})"
            done_entry += _format_external_children(repo_root, ext_children)
            done_items.append(done_entry)

        if total_done > recent_done_limit:
            archived_count = total_done - recent_done_limit
            done_items.append(f"<!-- {archived_count} older completed issue(s) archived in .along/ISSUES/done/ -->")

    return f"""# Active Issues

## Active
{chr(10).join(active_items) if active_items else "<!-- No active issues -->"}

## Backlog
{chr(10).join(backlog_items) if backlog_items else "<!-- No backlog issues -->"}

## Done (recent)
{chr(10).join(done_items) if done_items else "<!-- No completed issues -->"}
"""


def sync_issues_board(repo_root: str, recent_done_limit: int = RECENT_DONE_LIMIT) -> str:
    """Compile and write the .along/ISSUES.md projection board."""
    from .. import repo, textio
    board_path = os.path.join(repo.state_dir(repo_root), "ISSUES.md")
    content = compile_issues_board(repo_root, recent_done_limit=recent_done_limit)
    textio.write_text(board_path, content, newline="\n")
    return content
