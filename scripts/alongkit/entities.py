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
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along issue list   (or: python scripts/along_exec.py issue list)"
    )


import os
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


# ---------------------------------------------------------------------------
# Board Projection Helpers (REQ-5)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Issue Discovery and Active Issue Resolution (REQ-1..4)
# ---------------------------------------------------------------------------

def scan_issues(repo_root: str, include_done: bool = False) -> List[Dict[str, Any]]:
    """List issues from the SSOT entity files (.along/ISSUES/*.md).

    Reads front-matter via frontmatter.try_parse() so callers get typed metadata
    (slug, type, status, priority, milestone, etc.).
    """
    from . import frontmatter, repo, textio

    sdir = repo.state_dir(repo_root)
    issues_dir = os.path.join(sdir, "ISSUES")
    if not os.path.isdir(issues_dir):
        return []

    dirs_to_scan = [(issues_dir, False)]
    if include_done:
        done_dir = os.path.join(issues_dir, "done")
        if os.path.isdir(done_dir):
            dirs_to_scan.append((done_dir, True))

    issues = []
    for directory, is_done in dirs_to_scan:
        for fname in sorted(os.listdir(directory)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(directory, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                content = textio.read_text(fpath)
            except OSError:
                continue
            fm, _, _ = frontmatter.try_parse(content, path=fpath)
            ftype, fslug = parse_key(fname[:-3])
            itype = fm.get("type") or ftype or "task"
            islug = fm.get("slug") or fslug
            status = fm.get("status") or ("done" if is_done else "open")

            issues.append({
                "slug": islug,
                "type": itype,
                "status": status,
                "priority": fm.get("priority", "medium"),
                "file_path": fpath,
                "done": is_done or status == "done",
                "frontmatter": fm,
            })
    return issues


def find_issue_by_slug(repo_root: str, slug: str) -> Optional[Dict[str, Any]]:
    """Search .along/ISSUES/ and .along/ISSUES/done/ for an issue matching `slug`."""
    clean_type, clean_slug = parse_key(slug)
    all_issues = scan_issues(repo_root, include_done=True)
    for iss in all_issues:
        if iss["slug"] == clean_slug or iss["slug"] == slug:
            if clean_type and iss["type"] != clean_type:
                continue
            return iss
        if canonical_key(iss["type"], iss["slug"]) == slug:
            return iss
    return None


def resolve_active_issue(repo_root: str,
                         explicit_slug: Optional[str] = None,
                         branch_name: Optional[str] = None,
                         strict: bool = False) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Infer or validate the active issue for a commit deterministically.

    Priority order (REQ-2):
    1. Explicit slug (--issue / -i): validated against SSOT files; unknown slug is rejected.
    2. Git branch matching an in-progress issue slug.
    3. Exactly one issue with status: in-progress.
    4. Refuse to guess: returns None with warning messages (or raises ValueError if strict).
    """
    from . import proc

    warnings: List[str] = []

    # 1. Explicit slug
    if explicit_slug:
        found = find_issue_by_slug(repo_root, explicit_slug)
        if not found:
            msg = f"Unknown issue slug: '{explicit_slug}' does not exist in .along/ISSUES/."
            if strict:
                raise ValueError(msg)
            warnings.append(msg)
            return None, warnings
        return found, warnings

    active_issues = scan_issues(repo_root, include_done=False)
    in_progress = [iss for iss in active_issues if iss["status"] == "in-progress"]

    # 2. Branch name check
    branch = branch_name
    if branch is None:
        res = proc.git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
        if res.ok:
            branch = res.stdout.strip()

    if branch and branch not in ("HEAD", "main", "master"):
        branch_lower = branch.lower()
        branch_matches = []
        for iss in in_progress:
            islug = iss["slug"].lower()
            if (islug == branch_lower or
                    f"/{islug}" in branch_lower or
                    f"--{islug}" in branch_lower or
                    branch_lower.endswith(islug)):
                branch_matches.append(iss)
        if len(branch_matches) == 1:
            return branch_matches[0], warnings

    # 3. Single in-progress issue
    if len(in_progress) == 1:
        return in_progress[0], warnings

    # 4. Refuse to guess
    if len(in_progress) == 0:
        msg = "No in-progress issue found in .along/ISSUES/. Commit will have no issue binding."
        if strict:
            raise ValueError("Strict mode: no in-progress issue found in .along/ISSUES/.")
        warnings.append(msg)
        return None, warnings
    else:
        slugs = [iss["slug"] for iss in in_progress]
        msg = (
            f"Multiple in-progress issues found ({', '.join(slugs)}). "
            "Cannot determine active issue unambiguously without --issue <slug>."
        )
        if strict:
            raise ValueError(f"Strict mode: multiple in-progress issues found ({', '.join(slugs)}).")
        warnings.append(msg)
        return None, warnings

