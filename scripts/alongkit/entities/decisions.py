#!/usr/bin/env python3
"""
alongkit.entities.decisions - ADR parsing, compilation, file creation, and conflict checking.
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
from typing import Any, Dict, List, Optional

from ..markdown import github_heading_anchor
from .vocabulary import (
    ACTIVE_DECISION_STATUSES,
    today_iso,
)

_ADR_HEADING = (
    r"(?:ADR-\d{4}-\d{2}-\d{2}--[A-Za-z0-9._-]+|(?!\d{4}-\d{2}-\d{2})\d{1,4}\s*[-.:])"
)
ADR_SPLIT_RE = re.compile(r"\n(?=##\s+" + _ADR_HEADING + r")")
ADR_HEADER_RE = re.compile(
    r"^##\s+(?:(?P<key>ADR-\d{4}-\d{2}-\d{2}--[A-Za-z0-9._-]+)"
    r"|(?!\d{4}-\d{2}-\d{2})(?P<num>\d{1,4})\s*[-.:])"
    r"\s*(?:-\s*)?(?P<title>.*)$"
)

DECISIONS_FILE = "DECISIONS.md"
GENERIC_DECISION_TAGS: frozenset = frozenset({"adr", "architecture", "decision"})


def adr_key(day: str, slug: str) -> str:
    """Canonical ADR key: ADR-YYYY-MM-DD--<slug>."""
    return f"ADR-{day}--{slug}"


def format_adr(slug: str, title: str, context: str, decision: str, consequences: str,
               day: Optional[str] = None, status: str = "accepted") -> str:
    """Render one append-only ADR entry."""
    day = day or today_iso()
    return (
        f"\n## {adr_key(day, slug)} - {title}\n"
        f"- Date: {day}\n"
        f"- Status: {status}\n"
        f"- Context: {context}\n"
        f"- Decision: {decision}\n"
        f"- Consequences: {consequences}\n"
    )


def parse_decision_entries(dec_raw: str,
                           rel_path: str = ".along/DECISIONS.md") -> List[Dict[str, Any]]:
    """Split an append-only DECISIONS.md into individual searchable ADR entries."""
    entries: List[Dict[str, Any]] = []
    for block in ADR_SPLIT_RE.split(dec_raw):
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        heading = lines[0].strip()
        header = ADR_HEADER_RE.match(heading)
        if not header:
            continue

        end = len(lines)
        for offset, line in enumerate(lines[1:], 1):
            if line.startswith("## "):
                end = offset
                break
        block = "\n".join(lines[:end]).strip()

        key = header.group("key")
        human_title = (header.group("title") or "").strip()

        if key:
            if "<" in key or "YYYY" in key:
                continue
            entry_key = key
            slug = key.lower()
        else:
            entry_key = f"ADR-{header.group('num')}"
            slug = entry_key.lower()

        entries.append({
            "category": "decision",
            "category_label": "ADR",
            "title": f"{entry_key} - {human_title}" if human_title else entry_key,
            "slug": slug,
            "type": "adr",
            "tags": ["adr", "architecture", "decision"],
            "status": ("superseded" if re.search(r"superseded\s+by", block, re.IGNORECASE)
                       else "active"),
            "file_path": f"{rel_path}#{github_heading_anchor(heading)}",
            "body": block,
        })

    if not entries:
        for line in dec_raw.splitlines():
            line = line.strip()
            m = re.match(r"^-\s+\[(?P<label>[^\]]+)\]\((?P<link>DECISIONS/(?:ADR-\d{4}-\d{2}-\d{2}--)?(?P<slug>[^.]+)\.md)\)(?:\s+-\s+(?P<extra>.*))?", line)
            if not m:
                continue
            slug = m.group("slug").lower()
            link = m.group("link")
            extra = (m.group("extra") or "").strip()
            label = m.group("label").strip()
            title = extra if extra else label
            clean_title = re.sub(r"\s*\*\(superseded.*?\)\*", "", title).strip()
            status = "superseded" if "superseded" in line.lower() else "active"
            entries.append({
                "category": "decision",
                "category_label": "ADR",
                "title": f"ADR - {clean_title}",
                "slug": slug,
                "type": "adr",
                "tags": ["adr", "architecture", "decision"],
                "status": status,
                "file_path": link,
                "body": f"# {clean_title}\n\n- Slug: {slug}\n- Status: {status}\n- File: {link}\n",
            })
    return entries


def uses_slug_adr_format(dec_raw: str) -> bool:
    """True when DECISIONS.md uses the decentralized ADR-YYYY-MM-DD--<slug> headers."""
    return bool(re.search(r"^##\s+ADR-\d{4}-\d{2}-\d{2}--", dec_raw, re.MULTILINE))


def extract_decision_summary(text: str, max_chars: int = 160) -> str:
    """Extract a concise single-line summary of an ADR decision for CONSTRAINTS.md."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return ""
    first = re.sub(r"^(\d+\.|\-|\*)\s*", "", lines[0])
    buf = first
    idx = 1
    while len(buf) < max_chars and idx < len(lines):
        nxt = re.sub(r"^(\d+\.|\-|\*)\s*", "", lines[idx])
        buf += " " + nxt
        idx += 1
    if len(buf) > max_chars:
        cut = buf[:max_chars].rsplit(" ", 1)[0]
        return cut.rstrip(".,:;") + "..."
    return buf.strip()


def scan_decisions(repo_root: str) -> List[Dict[str, Any]]:
    """List decisions from .along/DECISIONS/*.md (with fallback to .along/DECISIONS.md)."""
    from .. import frontmatter, repo, textio

    sdir = repo.state_dir(repo_root)
    dec_dir = os.path.join(sdir, "DECISIONS")
    decisions: List[Dict[str, Any]] = []

    if os.path.isdir(dec_dir):
        for fname in sorted(os.listdir(dec_dir)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(dec_dir, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                content = textio.read_text(fpath)
            except OSError:
                continue
            fm, body, _ = frontmatter.try_parse(content, path=fpath)
            fslug = fname[:-3]
            slug_match = re.match(r"^ADR-\d{4}-\d{2}-\d{2}--(?P<slug>.+)$", fslug)
            inferred_slug = slug_match.group("slug") if slug_match else fslug
            dslug = fm.get("slug") or inferred_slug
            title = fm.get("title")
            if not title:
                first_line = body.strip().splitlines()[0] if body.strip() else ""
                h_match = re.match(r"^#+\s+(?:ADR-[^-\s]+--[^\s]+\s+-\s+)?(.*)$", first_line)
                title = h_match.group(1).strip() if h_match and h_match.group(1) else dslug.replace("-", " ").title()
            ddate = fm.get("date")
            if not ddate:
                d_match = re.search(r"-\s*Date:\s*(\d{4}-\d{2}-\d{2})", body)
                ddate = d_match.group(1) if d_match else None
            status = fm.get("status")
            if not status:
                status = "superseded" if re.search(r"superseded\s+by", body, re.IGNORECASE) else "accepted"

            c_match = re.search(r"-\s*Context:\s*(.*?)(?=\n-\s*[A-Z]|\Z)", body, re.DOTALL)
            d_match = re.search(r"-\s*Decision:\s*(.*?)(?=\n-\s*[A-Z]|\Z)", body, re.DOTALL)
            q_match = re.search(r"-\s*Consequences:\s*(.*?)(?=\n-\s*[A-Z]|\Z)", body, re.DOTALL)
            sup_by = fm.get("superseded_by")
            if not sup_by:
                sup_m = re.search(r"superseded\s+by\s+(?:ADR-\d{4}-\d{2}-\d{2}--)?(?P<target>[A-Za-z0-9._-]+)", body, re.IGNORECASE)
                if sup_m:
                    sup_by = sup_m.group("target")

            rel_path = repo.canonical_relpath(fpath, repo_root)
            decisions.append({
                "category": "decision",
                "category_label": "ADR",
                "slug": dslug,
                "title": title,
                "date": ddate,
                "status": status,
                "superseded_by": sup_by,
                "context": c_match.group(1).strip() if c_match else "",
                "decision": d_match.group(1).strip() if d_match else "",
                "consequences": q_match.group(1).strip() if q_match else "",
                "tags": fm.get("tags") or ["adr", "architecture", "decision"],
                "file_path": rel_path,
                "abs_path": fpath,
                "filename": fname,
                "body": body,
                "frontmatter": fm,
            })

    if not decisions:
        dec_path = os.path.join(sdir, "DECISIONS.md")
        if os.path.isfile(dec_path):
            try:
                raw = textio.read_text(dec_path)
                entries = parse_decision_entries(raw, rel_path=".along/DECISIONS.md")
                for e in entries:
                    raw_slug = e["slug"]
                    m_slug = re.match(r"^adr-\d{4}-\d{2}-\d{2}--(?P<slug>.+)$", raw_slug, re.IGNORECASE)
                    clean_slug = m_slug.group("slug") if m_slug else raw_slug

                    c_match = re.search(r"-\s*Context:\s*(.*?)(?=\n-\s*[A-Z]|\Z)", e["body"], re.DOTALL)
                    d_match = re.search(r"-\s*Decision:\s*(.*?)(?=\n-\s*[A-Z]|\Z)", e["body"], re.DOTALL)
                    q_match = re.search(r"-\s*Consequences:\s*(.*?)(?=\n-\s*[A-Z]|\Z)", e["body"], re.DOTALL)

                    sup_by = None
                    if e["status"] == "superseded":
                        sup_m = re.search(r"superseded\s+by\s+(?:ADR-\d{4}-\d{2}-\d{2}--)?(?P<target>[A-Za-z0-9._-]+)", e["body"], re.IGNORECASE)
                        if sup_m:
                            sup_by = sup_m.group("target")

                    decisions.append({
                        "category": "decision",
                        "category_label": "ADR",
                        "slug": clean_slug,
                        "title": e["title"],
                        "date": None,
                        "status": "superseded" if e["status"] == "superseded" else "accepted",
                        "superseded_by": sup_by,
                        "context": c_match.group(1).strip() if c_match else "",
                        "decision": d_match.group(1).strip() if d_match else "",
                        "consequences": q_match.group(1).strip() if q_match else "",
                        "tags": e.get("tags", ["adr", "architecture", "decision"]),
                        "file_path": e["file_path"],
                        "abs_path": dec_path,
                        "filename": "DECISIONS.md",
                        "body": e["body"],
                        "frontmatter": {},
                    })
            except OSError:
                pass

    return decisions


#: Active ADRs the DECISIONS.md board lists (newest first); the full list is
#: docs/decisions/INDEX.md. Override: `.along/config.json` `budget.decisions_board_recent`.
#: [debt--decisions-board-sliding-window]
DECISIONS_BOARD_RECENT = 30


def decisions_board_recent(repo_root: str) -> int:
    """Window size of the DECISIONS.md board: the config override, else the default."""
    import json
    from .. import repo

    path = os.path.join(repo.state_dir(repo_root), "config.json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return DECISIONS_BOARD_RECENT
    value = (data.get("budget") or {}).get("decisions_board_recent") if isinstance(data, dict) else None
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return DECISIONS_BOARD_RECENT


def compile_decisions_board(repo_root: str) -> str:
    """Compile the .along/DECISIONS.md board: the newest active ADRs and compact retired ones.

    Bounded by `decisions_board_recent`; older active ADRs are counted and left to
    docs/decisions/INDEX.md. [debt--decisions-board-sliding-window]
    """
    from .. import repo, textio

    sdir = repo.state_dir(repo_root)
    dec_dir = os.path.join(sdir, "DECISIONS")
    if not os.path.isdir(dec_dir):
        return ""

    decisions = scan_decisions(repo_root)
    if not decisions:
        return ""

    active_adrs = []
    superseded_adrs = []

    for d in decisions:
        st = (d.get("status") or "").lower()
        if st in ("accepted", "active", "proposed"):
            active_adrs.append(d)
        else:
            superseded_adrs.append(d)

    # Filenames start with the date: newest first.
    active_adrs.sort(key=lambda x: x.get("filename", ""), reverse=True)
    superseded_adrs.sort(key=lambda x: x.get("filename", ""))

    window = decisions_board_recent(repo_root)
    shown = active_adrs[:window]
    heading = f"## Active Decisions ({len(active_adrs)})"
    if len(active_adrs) > len(shown):
        heading = f"## Active Decisions ({len(active_adrs)}, newest {len(shown)} shown)"
    lines = [
        "<!-- Generated projection from .along/DECISIONS/*.md. Do not edit by hand. Run: along decision sync -->",
        "# Decisions (ADR Projection Board)",
        "",
        heading,
        "",
    ]

    for d in shown:
        fname = d.get("filename") or f"{d['slug']}.md"
        title = d.get("title") or d["slug"]
        lines.append(f"- [{title}](DECISIONS/{fname})")
    if len(active_adrs) > len(shown):
        lines.extend(["", f"Older decisions ({len(active_adrs) - len(shown)}): docs/decisions/INDEX.md"])

    lines.extend([
        "",
        f"## Superseded & Retired Decisions ({len(superseded_adrs)})",
        "",
    ])

    for d in superseded_adrs:
        sup_by = d.get("frontmatter", {}).get("superseded_by")
        lines.append(f"- {d['slug']} -> {sup_by}" if sup_by else f"- {d['slug']} (superseded)")

    lines.append("")
    content = "\n".join(lines)
    board_path = os.path.join(sdir, "DECISIONS.md")
    textio.write_text(board_path, content)
    return board_path


def create_decision_file(repo_root: str,
                         slug: str,
                         title: str,
                         context: str,
                         decision: str,
                         consequences: str,
                         day: Optional[str] = None,
                         status: str = "accepted",
                         tags: Optional[List[str]] = None) -> str:
    """Create a new modular ADR file under .along/DECISIONS/ADR-YYYY-MM-DD--<slug>.md."""
    from .. import repo, textio

    day = day or today_iso()
    sdir = repo.state_dir(repo_root)
    dec_dir = os.path.join(sdir, "DECISIONS")
    os.makedirs(dec_dir, exist_ok=True)

    filename = f"ADR-{day}--{slug}.md"
    target_path = os.path.join(dec_dir, filename)

    tags = tags or ["adr", "architecture", "decision"]
    tags_yaml = "[" + ", ".join(tags) + "]"

    content = (
        f"---\n"
        f"protocol: along\n"
        f"slug: {slug}\n"
        f"type: decision\n"
        f"title: \"{title}\"\n"
        f"date: {day}\n"
        f"status: {status}\n"
        f"tags: {tags_yaml}\n"
        f"---\n\n"
        f"# ADR-{day}--{slug} - {title}\n\n"
        f"- Date: {day}\n"
        f"- Status: {status}\n"
        f"- Context: {context}\n"
        f"- Decision: {decision}\n"
        f"- Consequences: {consequences}\n"
    )
    textio.write_text(target_path, content)
    return target_path


def sync_constraints(repo_root: str) -> str:
    """Compile active architectural constraints into .along/CONSTRAINTS.md."""
    from .. import repo, textio

    sdir = repo.state_dir(repo_root)
    dec_dir = os.path.join(sdir, "DECISIONS")
    dec_path = os.path.join(sdir, "DECISIONS.md")
    if not os.path.isdir(dec_dir) and not os.path.isfile(dec_path):
        return ""

    decisions = scan_decisions(repo_root)
    if not decisions:
        return ""

    active_entries = [e for e in decisions if (e.get("status") or "").lower() in ("accepted", "active")]

    blocks = [
        "<!-- Generated projection from .along/DECISIONS. Do not edit by hand. Run: along decision sync -->",
        "# Active Architectural Constraints",
        "",
        "This document compiles active architectural rules and constraints from `.along/DECISIONS/`.",
        "Detailed context, history, and superseded ADRs remain in individual decision records.",
        "",
    ]

    for e in active_entries:
        m = re.search(r"-\s*Decision:\s*(.*?)(?=\n-\s*Consequences:|\n-\s*Context:|\Z)", e.get("body", ""), re.DOTALL)
        decision_text = m.group(1).strip() if m else ""
        summary = extract_decision_summary(decision_text, max_chars=160)
        t_parts = e.get("title", "").split(" - ", 1)
        short_title = t_parts[1] if len(t_parts) > 1 else t_parts[0]
        fname = e.get("filename")
        if fname and fname != "DECISIONS.md":
            link_target = f"DECISIONS/{fname}"
        else:
            link_target = e.get("file_path", "DECISIONS.md")
            if link_target.startswith(".along/"):
                link_target = link_target[len(".along/"):]
        blocks.append(f"- **[{short_title}]({link_target})**: {summary}")

    content = "\n".join(blocks).rstrip() + "\n"
    constraints_file = os.path.join(sdir, "CONSTRAINTS.md")
    textio.write_text(constraints_file, content)
    return constraints_file


def check_decision_conflicts(repo_root: str) -> List[Dict[str, Any]]:
    """Flag pairs of active (accepted) ADRs with conflicting statements."""
    decisions = scan_decisions(repo_root)
    if not decisions:
        return []
    active = [d for d in decisions if (d.get("status") or "").lower() in ACTIVE_DECISION_STATUSES]
    active.sort(key=lambda d: (d.get("date") or "", d.get("filename") or d.get("slug") or ""))

    conflicts: List[Dict[str, Any]] = []
    for i in range(len(active)):
        older = active[i]
        older_slug = older.get("slug")
        older_fname = older.get("filename", "")
        if not older_slug:
            continue
        older_tags = set(older.get("tags") or [])
        for j in range(i + 1, len(active)):
            newer = active[j]
            newer_slug = newer.get("slug")
            newer_fname = newer.get("filename", "")
            if not newer_slug or newer_slug == older_slug:
                continue
            newer_tags = set(newer.get("tags") or [])
            shared_all_tags = older_tags & newer_tags
            shared_domain_tags = shared_all_tags - GENERIC_DECISION_TAGS

            newer_body = newer.get("body", "")
            newer_fm = newer.get("frontmatter") or {}
            supersedes_list = newer_fm.get("supersedes") or []
            if isinstance(supersedes_list, str):
                supersedes_list = [supersedes_list]

            is_explicit_supersedes = older_slug in supersedes_list or bool(
                re.search(rf"\b(?:[Ss]upersedes|[Rr]eplaces):\s*.*?\b{re.escape(older_slug)}\b", newer_body)
            )

            mentions_older = (
                older_slug in newer_body
                or is_explicit_supersedes
                or (older_fname and older_fname in newer_body)
            )
            if not mentions_older:
                continue

            if "complements" in newer_body.lower() or "complementary" in newer_body.lower():
                continue

            in_replacement_context = bool(
                re.search(rf"\b(?:supersed\w+|replace\w+|previously\s+in)\b.*?\b{re.escape(older_slug)}\b",
                          newer_body, re.IGNORECASE)
                or re.search(rf"\b{re.escape(older_slug)}\b.*?\b(?:supersed\w+|replace\w+)\b",
                             newer_body, re.IGNORECASE)
            )

            if is_explicit_supersedes or shared_domain_tags or in_replacement_context:
                reported_tags = sorted(shared_domain_tags) if shared_domain_tags else sorted(shared_all_tags)
                conflicts.append({
                    "older_slug": older_slug,
                    "newer_slug": newer_slug,
                    "shared_tags": reported_tags,
                    "rel": f".along/DECISIONS/{newer_fname}" if newer_fname else f".along/DECISIONS/{newer_slug}.md",
                    "message": (
                        f"Active ADR '{newer_slug}' references '{older_slug}' "
                        f"(tags: {', '.join(reported_tags)}), but '{older_slug}' is still status: accepted. "
                        f"Mark '{older_slug}' as superseded or record explicit supersession."
                    ),
                })
    return conflicts
