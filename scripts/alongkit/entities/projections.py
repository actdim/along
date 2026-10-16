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

from .vocabulary import RECENT_DONE_LIMIT

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


def compile_issues_board(repo_root: str, recent_done_limit: int = RECENT_DONE_LIMIT) -> str:
    """Compile active issues, backlog issues, and recent completed issues into ISSUES.md content."""
    from .. import frontmatter, repo, textio
    issues_dir = os.path.join(repo.state_dir(repo_root), "ISSUES")
    done_dir = os.path.join(issues_dir, "done")
    active_items = []
    backlog_items = []
    done_items = []

    if os.path.exists(issues_dir):
        for f in sorted(os.listdir(issues_dir)):
            if f.endswith(".md") and os.path.isfile(os.path.join(issues_dir, f)):
                parts = f[:-3].split("--", 1)
                itype = parts[0]
                islug = parts[1] if len(parts) > 1 else f[:-3]
                fpath = os.path.join(issues_dir, f)
                istatus = "open"
                try:
                    content = textio.read_text(fpath)
                    fm, _, _ = frontmatter.try_parse(content, path=fpath)
                    if fm.get("status"):
                        istatus = str(fm["status"]).lower()
                except OSError:
                    pass

                entry = f"- [ ] `({itype})` [{islug}](ISSUES/{f})"
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
                try:
                    content = textio.read_text(fpath)
                    fm, _, _ = frontmatter.try_parse(content, path=fpath)
                    if fm.get("status"):
                        istatus = str(fm["status"]).lower()
                    if fm.get("completed"):
                        comp_date = str(fm["completed"])
                    elif fm.get("created"):
                        comp_date = str(fm["created"])
                except OSError:
                    pass
                if not comp_date:
                    try:
                        from datetime import datetime
                        comp_date = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d")
                    except OSError:
                        comp_date = "1970-01-01"
                done_records.append((comp_date, f, itype, islug, istatus))

        done_records.sort(key=lambda x: (x[0], x[1]), reverse=True)
        total_done = len(done_records)

        for comp_date, f, itype, islug, istatus in done_records[:recent_done_limit]:
            box = "~" if istatus in ("superseded", "cancelled", "duplicate") else "x"
            done_items.append(f"- [{box}] `({itype})` [{islug}](ISSUES/done/{f})")

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
