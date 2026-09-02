#!/usr/bin/env python3
"""
alongkit.entities - Entity vocabulary, canonical keys, and ADR record parsing.

The protocol's entity schema (issues, sessions, decisions, milestones, risks, spikes,
checklists) was previously expressed as string literals repeated across engines. The
demonstrated cost is `[bug--adr-retrieval-blind-to-slug-headers]`: the ADR header format
changed in protocol v2.2.0, was updated where ADRs are written (`along_exec.py`) and
validated (`along_exec.py` doctor), and was missed in the reader
(`along_kb_search.py`). ADR search therefore returned zero results in every released
version. The header format is now declared exactly once, below.
"""


from __future__ import annotations
if __name__ == "__main__":
    raise SystemExit(
        f"{__name__} is a library module, not a command.\n"
        "Run: along kb-sync   (or: python scripts/along_exec.py kb-sync)"
    )


import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from .markdown import github_heading_anchor

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

ISSUE_TYPES: tuple = ("feat", "bug", "debt", "task", "docs")
ISSUE_STATUSES: tuple = ("open", "in-progress", "blocked", "done")
PRIORITIES: tuple = ("critical", "high", "medium", "low")

MILESTONE_STATUSES: tuple = ("open", "in-progress", "completed")
RISK_SEVERITIES: tuple = ("critical", "high", "medium", "low")
RISK_STATUSES: tuple = ("active", "mitigated", "resolved")
SPIKE_STATUSES: tuple = ("hypothesis", "evaluating", "concluded")
CHECKLIST_CATEGORIES: tuple = ("pre-commit", "stage-completion", "release", "security")

#: Front-matter keys that must be present on a closed issue.
DONE_REQUIRED_FIELDS: tuple = ("status", "completed")

#: Directory names under the state directory, keyed by entity kind.
ENTITY_DIRS: Dict[str, str] = {
    "issue": "ISSUES",
    "session": "SESSIONS",
    "milestone": "MILESTONES",
    "risk": "RISKS",
    "spike": "SPIKES",
    "checklist": "CHECKLISTS",
}


# ---------------------------------------------------------------------------
# Dates, slugs, keys
# ---------------------------------------------------------------------------

def today_iso() -> str:
    """Today as `YYYY-MM-DD`. Windows-safe in filenames, sortable, and unambiguous."""
    return date.today().strftime("%Y-%m-%d")


def is_iso_date(value: str) -> bool:
    """True when `value` is a `YYYY-MM-DD` calendar date."""
    try:
        datetime.strptime(str(value).strip(), "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


def slugify(text: str, max_words: int = 5) -> str:
    """Lowercase kebab-case slug, as the protocol requires for every entity."""
    lowered = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    if not lowered:
        return "untitled"
    words = [word for word in lowered.split("-") if word]
    return "-".join(words[:max_words]) if max_words else "-".join(words)


def canonical_key(entity_type: Optional[str], slug: str) -> str:
    """`<type>--<slug>` when a type is known, otherwise the bare slug.

    Entities reference each other by this key and never by file path, so a link
    survives the move into `ISSUES/done/`.
    """
    slug = slug.strip()
    if not entity_type:
        return slug
    prefix = f"{entity_type}--"
    return slug if slug.startswith(prefix) else prefix + slug


def parse_key(key: str) -> Tuple[Optional[str], str]:
    """Split a canonical key into `(type, slug)`; type is None for a bare slug."""
    cleaned = key.strip().strip("[]")
    if "--" in cleaned:
        head, tail = cleaned.split("--", 1)
        if head in ISSUE_TYPES:
            return head, tail
    return None, cleaned


def issue_filename(entity_type: str, slug: str) -> str:
    """File name of an issue entity: `<type>--<slug>.md`."""
    return f"{canonical_key(entity_type, slug)}.md"


def session_filename(day: str, slug: str) -> str:
    """File name of a session log: date first, so a directory listing sorts by time."""
    return f"{day}--{slug}.md"


# ---------------------------------------------------------------------------
# Architectural Decision Records
# ---------------------------------------------------------------------------

#: Current header format (protocol >= v2.2.0): `## ADR-YYYY-MM-DD--<slug> - <Title>`.
#: Legacy format (protocol < v2.2.0): `## <NNN> - <Title>` or `## <NNN>: <Title>`.
#: A bare ISO date heading (`## 2026-08-15 ...`) is explicitly not an ADR.
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


def adr_key(day: str, slug: str) -> str:
    """Canonical ADR key: `ADR-YYYY-MM-DD--<slug>`."""
    return f"ADR-{day}--{slug}"


def format_adr(slug: str, title: str, context: str, decision: str, consequences: str,
               day: Optional[str] = None, status: str = "accepted") -> str:
    """Render one append-only ADR entry.

    Slug-based headers are what let parallel branches append decisions without merge
    collisions, which is why the numeric format was retired in v2.2.0.
    """
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
    """Split an append-only DECISIONS.md into individual searchable ADR entries.

    Supports both header formats. The schema template placeholder (a literal `<slug>`
    or `YYYY-MM-DD` header) is skipped so it never surfaces as a search result.
    """
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

        # An ADR block ends at the next level-2 heading of any kind, so unrelated
        # sections appended to the log never bleed into an ADR body or snippet.
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
    return entries


def uses_slug_adr_format(dec_raw: str) -> bool:
    """True when DECISIONS.md uses the decentralized `ADR-YYYY-MM-DD--<slug>` headers."""
    return bool(re.search(r"^##\s+ADR-\d{4}-\d{2}-\d{2}--", dec_raw, re.MULTILINE))
