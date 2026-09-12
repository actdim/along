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
ISSUE_STATUSES: tuple = (
    "open",
    "in-progress",
    "blocked",
    "done",
    "superseded",
    "cancelled",
    "duplicate",
)
CLOSED_ISSUE_STATUSES: tuple = ("done", "superseded", "cancelled", "duplicate")
DELIVERED_ISSUE_STATUSES: tuple = ("done",)
PRIORITIES: tuple = ("critical", "high", "medium", "low")

MILESTONE_STATUSES: tuple = ("open", "in-progress", "completed")
RISK_SEVERITIES: tuple = ("critical", "high", "medium", "low")
RISK_STATUSES: tuple = ("active", "mitigated", "resolved")
SPIKE_STATUSES: tuple = ("hypothesis", "evaluating", "concluded")
CHECKLIST_CATEGORIES: tuple = ("pre-commit", "stage-completion", "release", "security")
DECISION_STATUSES: tuple = ("accepted", "superseded", "retired", "proposed", "rejected", "active")
ACTIVE_DECISION_STATUSES: tuple = ("accepted", "active")

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
    "decision": "DECISIONS",
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


def is_valid_slug(slug: str, min_words: int = 2, max_words: int = 5) -> bool:
    """True when slug is lowercase kebab-case within word count bounds [min_words, max_words].

    The protocol specifies: lowercase kebab-case slug (2-5 words).
    Double hyphens ('--') are forbidden as '--' separates type from slug in canonical keys.
    """
    if not isinstance(slug, str) or not slug:
        return False
    slug = slug.strip()
    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", slug):
        return False
    words = slug.split("-")
    if min_words is not None and len(words) < min_words:
        return False
    if max_words is not None and len(words) > max_words:
        return False
    return True


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
# Issue Type Inference Heuristics (REQ-5)
# ---------------------------------------------------------------------------

BUG_KEYWORDS: tuple = (
    "fix", "bug", "issue", "leak", "crash", "error", "fail", "failure",
    "broken", "regression", "hang", "deadlock", "race", "flaky",
)
DEBT_KEYWORDS: tuple = (
    "debt", "refactor", "cleanup", "clean", "audit", "tidy", "deprecate",
    "prune", "dedup", "unify", "reorganize", "sanitize", "migrate", "parity",
)
DOCS_KEYWORDS: tuple = (
    "doc", "docs", "readme", "guide", "manual", "documentation",
)


def infer_issue_type(text: str) -> str:
    """Infer the most appropriate issue type from title, slug, or description."""
    words = set(re.findall(r"[a-z0-9]+", str(text).lower()))
    if any(k in words for k in BUG_KEYWORDS):
        return "bug"
    if any(k in words for k in DEBT_KEYWORDS):
        return "debt"
    if any(k in words for k in DOCS_KEYWORDS):
        return "docs"
    return "feat"


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
    """True when DECISIONS.md uses the decentralized `ADR-YYYY-MM-DD--<slug>` headers."""
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
    """List decisions from .along/DECISIONS/*.md (with fallback to .along/DECISIONS.md).

    Reads front-matter via frontmatter.try_parse() returning typed metadata:
    slug, title, date, status, tags, file_path, abs_path, filename, body, frontmatter.
    """
    from . import frontmatter, repo, textio

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

            rel_path = os.path.relpath(fpath, repo_root).replace("\\", "/")
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


def compile_decisions_board(repo_root: str) -> str:
    """Compile lightweight .along/DECISIONS.md projection board from .along/DECISIONS/*.md."""
    from . import repo, textio

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

    active_adrs.sort(key=lambda x: x.get("filename", ""))
    superseded_adrs.sort(key=lambda x: x.get("filename", ""))

    lines = [
        "<!-- Generated projection from .along/DECISIONS/*.md. Do not edit by hand. Run: along decision sync -->",
        "# Decisions (ADR Projection Board)",
        "",
        "Compiled index of Architectural Decision Records stored in `.along/DECISIONS/`.",
        "",
        f"## Active Decisions ({len(active_adrs)})",
        "",
    ]

    for d in active_adrs:
        fname = d.get("filename") or f"{d['slug']}.md"
        title = d.get("title") or d["slug"]
        lines.append(f"- [{title}](DECISIONS/{fname})")

    lines.extend([
        "",
        f"## Superseded & Retired Decisions ({len(superseded_adrs)})",
        "",
    ])

    for d in superseded_adrs:
        fname = d.get("filename") or f"{d['slug']}.md"
        title = d.get("title") or d["slug"]
        sup_by = d.get("frontmatter", {}).get("superseded_by")
        note = f" *(superseded by {sup_by})*" if sup_by else " *(superseded)*"
        lines.append(f"- [{title}](DECISIONS/{fname}){note}")

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
    from . import repo, textio

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
    from . import repo, textio

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


RECENT_DONE_LIMIT: int = 5


def compile_issues_board(repo_root: str, recent_done_limit: int = RECENT_DONE_LIMIT) -> str:
    """Compile active issues and recent completed issues into ISSUES.md content."""
    from . import repo
    issues_dir = os.path.join(repo.state_dir(repo_root), "ISSUES")
    done_dir = os.path.join(issues_dir, "done")
    active_items = []
    done_items = []

    if os.path.exists(issues_dir):
        for f in sorted(os.listdir(issues_dir)):
            if f.endswith(".md") and os.path.isfile(os.path.join(issues_dir, f)):
                parts = f[:-3].split("--", 1)
                itype = parts[0]
                islug = parts[1] if len(parts) > 1 else f[:-3]
                active_items.append(f"- [ ] `({itype})` [{islug}](ISSUES/{f})")

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
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as handle:
                        head = handle.read(500)
                    m_stat = re.search(r"^status:\s*[\"']?([a-z-]+)[\"']?", head, re.MULTILINE)
                    if m_stat:
                        istatus = m_stat.group(1).lower()
                    m_comp = re.search(r"^completed:\s*[\"']?([0-9-]+)[\"']?", head, re.MULTILINE)
                    if m_comp:
                        comp_date = m_comp.group(1)
                    else:
                        m_creat = re.search(r"^created:\s*[\"']?([0-9-]+)[\"']?", head, re.MULTILINE)
                        if m_creat:
                            comp_date = m_creat.group(1)
                except OSError:
                    pass
                if not comp_date:
                    try:
                        from datetime import datetime
                        comp_date = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d")
                    except OSError:
                        comp_date = "1970-01-01"
                done_records.append((comp_date, f, itype, islug, istatus))

        # Sort descending by completion date, then filename
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
<!-- Planned or deferred issues -->

## Done (recent)
{chr(10).join(done_items) if done_items else "<!-- No completed issues -->"}
"""


def sync_issues_board(repo_root: str, recent_done_limit: int = RECENT_DONE_LIMIT) -> str:
    """Compile and write the .along/ISSUES.md projection board."""
    from . import repo, textio
    board_path = os.path.join(repo.state_dir(repo_root), "ISSUES.md")
    content = compile_issues_board(repo_root, recent_done_limit=recent_done_limit)
    textio.write_text(board_path, content, newline="\n")
    return content


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
                "done": is_done or status in CLOSED_ISSUE_STATUSES,
                "delivered": status in DELIVERED_ISSUE_STATUSES,
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


# ---------------------------------------------------------------------------
# Agent Detection (REQ-1)
# ---------------------------------------------------------------------------

def detect_agent(explicit: Optional[str] = None) -> str:
    """Infer the executing agent tool/model name at runtime.

    Order of priority:
    1. Explicit value passed by caller (--agent <name>).
    2. ALONG_AGENT environment variable.
    3. Provider-specific runtime environment markers:
       - Claude Code: CLAUDE_CODE, CLAUDE_PROJECT_DIR, CLAUDE_CONVERSATION_ID, ANTHROPIC_CLI -> 'claude-code'
       - Antigravity: ANTIGRAVITY_AGENT, ANTIGRAVITY_CONVERSATION_ID, ANTIGRAVITY_PROJECT_ID -> 'antigravity'
       - Codex: CODEX_CLI, OPENAI_CODEX -> 'codex'
       - OpenCode: OPENCODE_CLI, OPENCODE_AGENT -> 'opencode'
    4. Fall back to 'unknown' rather than a hardcoded provider name.
    """
    if explicit:
        return explicit.strip()

    env = os.environ
    if env.get("ALONG_AGENT"):
        return env["ALONG_AGENT"].strip()
    if env.get("AGENT"):
        val = env["AGENT"].strip()
        if val:
            return val

    # Claude Code
    if any(k in env for k in ("CLAUDE_CODE", "CLAUDE_PROJECT_DIR", "CLAUDE_CONVERSATION_ID", "ANTHROPIC_CLI")):
        return "claude-code"

    # Antigravity
    if any(k in env for k in ("ANTIGRAVITY_AGENT", "ANTIGRAVITY_CONVERSATION_ID", "ANTIGRAVITY_PROJECT_ID")):
        return "antigravity"

    # Codex
    if any(k in env for k in ("CODEX_CLI", "OPENAI_CODEX")):
        return "codex"

    # OpenCode
    if any(k in env for k in ("OPENCODE_CLI", "OPENCODE_AGENT")):
        return "opencode"

    return "unknown"


# ---------------------------------------------------------------------------
# Milestone Discovery (REQ-2)
# ---------------------------------------------------------------------------

def scan_milestones(repo_root: str) -> List[Dict[str, Any]]:
    """List milestones from .along/MILESTONES/*.md.

    Reads front-matter via frontmatter.try_parse() returning typed metadata:
    slug, title, status, due_date, target_issues, file_path, frontmatter.
    """
    from . import frontmatter, repo, textio

    sdir = repo.state_dir(repo_root)
    m_dir = os.path.join(sdir, "MILESTONES")
    if not os.path.isdir(m_dir):
        return []

    milestones = []
    for fname in sorted(os.listdir(m_dir)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(m_dir, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            content = textio.read_text(fpath)
        except OSError:
            continue
        fm, _, _ = frontmatter.try_parse(content, path=fpath)
        fslug = fname[:-3]
        mslug = fm.get("slug") or fslug
        status = fm.get("status") or "open"
        milestones.append({
            "slug": mslug,
            "title": fm.get("title", mslug),
            "status": status,
            "target_issues": fm.get("target_issues", []),
            "file_path": fpath,
            "frontmatter": fm,
        })
    return milestones


def resolve_in_progress_milestone(repo_root: str) -> Optional[str]:
    """Return the milestone slug if exactly one milestone has status: in-progress.

    Returns None if zero or multiple milestones are in-progress.
    """
    milestones = scan_milestones(repo_root)
    in_progress = [m for m in milestones if m["status"] == "in-progress"]
    if len(in_progress) == 1:
        return in_progress[0]["slug"]
    return None


# ---------------------------------------------------------------------------
# Entity Schema & Graph Validation (REQ-6)
# ---------------------------------------------------------------------------

def _resolve_ref(ref: Any, known: set) -> bool:
    if not ref:
        return False
    clean = str(ref).strip().strip("[]")
    if ":" in clean:
        clean = clean.split(":", 1)[1]
    if clean in known:
        return True
    _, slug = parse_key(clean)
    return slug in known


def validate_entities(repo_root: str) -> Dict[str, Any]:
    """Validate entity schemas, enums, mandatory fields, and graph references.

    Checks:
    1. Issues: valid type, status, priority enums; mandatory dates; completed on done;
       dangling milestone, parent, blocked_by, related references.
    2. Milestones: mandatory fields, status enum, dangling target_issues.
    3. Risks, spikes, checklists: mandatory fields and enums.
    4. Sessions: mandatory fields, milestone resolution, issue resolutions.
    """
    from . import frontmatter, repo, textio

    sdir = repo.state_dir(repo_root)
    errors: List[Tuple[str, str]] = []
    warnings: List[Tuple[str, str]] = []
    scanned = 0

    all_issues = scan_issues(repo_root, include_done=True)
    known_issue_slugs = {iss["slug"] for iss in all_issues}
    known_issue_keys = {canonical_key(iss["type"], iss["slug"]) for iss in all_issues} | known_issue_slugs

    all_milestones = scan_milestones(repo_root)
    known_milestone_slugs = (
        {m["slug"] for m in all_milestones} |
        {os.path.basename(m["file_path"])[:-3] for m in all_milestones}
    )

    known_entity_keys = set(known_issue_keys)
    for m in all_milestones:
        known_entity_keys.add(m["slug"])
        known_entity_keys.add(f"milestone--{m['slug']}")

    # Scan auxiliary entities to build full reference registry
    for kind, dirname in (("risk", "RISKS"), ("spike", "SPIKES"), ("checklist", "CHECKLISTS"), ("decision", "DECISIONS")):
        edir = os.path.join(sdir, dirname)
        if os.path.isdir(edir):
            for fname in os.listdir(edir):
                if fname.endswith(".md"):
                    slug = fname[:-3]
                    known_entity_keys.add(slug)
                    known_entity_keys.add(f"{kind}--{slug}")
                    if slug.startswith("ADR-") and "--" in slug:
                        bare = slug.split("--", 1)[1]
                        known_entity_keys.add(bare)
                        known_entity_keys.add(f"decision--{bare}")

    # 1. Validate Issues
    for iss in all_issues:
        scanned += 1
        fm = iss["frontmatter"]
        fpath = iss["file_path"]
        rel = os.path.relpath(fpath, repo_root)

        if not fm:
            errors.append((rel, "missing or unparseable YAML front-matter"))
            continue

        if fm.get("protocol") != "along":
            errors.append((rel, f"missing or invalid protocol: '{fm.get('protocol')}' (expected 'along')"))

        islug = fm.get("slug")
        if not islug:
            errors.append((rel, "missing mandatory field: 'slug'"))
        else:
            fname = os.path.basename(fpath)
            expected_key = canonical_key(iss["type"], islug)
            if fname[:-3] != expected_key and fname[:-3] != islug and not fname.endswith(f"--{islug}.md"):
                errors.append((rel, f"slug '{islug}' does not match filename '{fname}'"))

        itype = fm.get("type")
        if not itype or itype not in ISSUE_TYPES:
            errors.append((rel, f"invalid type: '{itype}' (allowed: {', '.join(ISSUE_TYPES)})"))

        istatus = fm.get("status")
        if not istatus or istatus not in ISSUE_STATUSES:
            errors.append((rel, f"invalid status: '{istatus}' (allowed: {', '.join(ISSUE_STATUSES)})"))

        priority = fm.get("priority")
        if not priority or priority not in PRIORITIES:
            errors.append((rel, f"invalid priority: '{priority}' (allowed: {', '.join(PRIORITIES)})"))

        created = fm.get("created")
        if not created or not is_iso_date(created):
            errors.append((rel, f"missing or invalid created date: '{created}' (expected YYYY-MM-DD)"))

        updated = fm.get("updated")
        if not updated or not is_iso_date(updated):
            errors.append((rel, f"missing or invalid updated date: '{updated}' (expected YYYY-MM-DD)"))

        if iss["done"] or istatus in CLOSED_ISSUE_STATUSES:
            completed = fm.get("completed")
            if not completed or not is_iso_date(completed):
                errors.append((rel, f"missing or invalid completed date on closed issue: '{completed}' (expected YYYY-MM-DD)"))

        # References
        mslug = fm.get("milestone")
        if mslug and str(mslug).strip() and str(mslug).strip() not in known_milestone_slugs:
            errors.append((rel, f"dangling milestone reference: '{mslug}'"))

        parent = fm.get("parent")
        if parent and str(parent).strip() and not _resolve_ref(parent, known_entity_keys):
            errors.append((rel, f"dangling parent reference: '{parent}'"))

        blocked_by = fm.get("blocked_by")
        if isinstance(blocked_by, list):
            for b in blocked_by:
                if b and not _resolve_ref(b, known_entity_keys):
                    errors.append((rel, f"dangling blocked_by reference: '{b}'"))

        related = fm.get("related")
        if isinstance(related, list):
            for r in related:
                if r and not _resolve_ref(r, known_entity_keys):
                    errors.append((rel, f"dangling related reference: '{r}'"))

        superseded_by = fm.get("superseded_by")
        if superseded_by and str(superseded_by).strip():
            if not _resolve_ref(superseded_by, known_entity_keys):
                errors.append((rel, f"dangling superseded_by reference: '{superseded_by}'"))

        duplicate_of = fm.get("duplicate_of")
        if duplicate_of and str(duplicate_of).strip():
            if not _resolve_ref(duplicate_of, known_entity_keys):
                errors.append((rel, f"dangling duplicate_of reference: '{duplicate_of}'"))

    # 2. Validate Milestones
    for m in all_milestones:
        scanned += 1
        fm = m["frontmatter"]
        fpath = m["file_path"]
        rel = os.path.relpath(fpath, repo_root)

        if not fm:
            errors.append((rel, "missing or unparseable YAML front-matter"))
            continue

        if fm.get("protocol") != "along":
            errors.append((rel, f"missing or invalid protocol: '{fm.get('protocol')}' (expected 'along')"))

        if not fm.get("slug"):
            errors.append((rel, "missing mandatory field: 'slug'"))

        if not fm.get("title"):
            errors.append((rel, "missing mandatory field: 'title'"))

        mstatus = fm.get("status")
        if not mstatus or mstatus not in MILESTONE_STATUSES:
            errors.append((rel, f"invalid status: '{mstatus}' (allowed: {', '.join(MILESTONE_STATUSES)})"))

        target_issues = fm.get("target_issues")
        if isinstance(target_issues, list):
            for t in target_issues:
                if t and not _resolve_ref(t, known_issue_keys):
                    errors.append((rel, f"dangling target_issues reference: '{t}'"))

    # 3. Validate Auxiliary Entities (RISKS, SPIKES, CHECKLISTS)
    checklists_dir = os.path.join(sdir, "CHECKLISTS")
    if os.path.isdir(checklists_dir):
        for fname in os.listdir(checklists_dir):
            if not fname.endswith(".md"):
                continue
            scanned += 1
            fpath = os.path.join(checklists_dir, fname)
            rel = os.path.relpath(fpath, repo_root)
            try:
                c = textio.read_text(fpath)
                fm, _, _ = frontmatter.try_parse(c, path=fpath)
            except OSError:
                continue
            if not fm:
                errors.append((rel, "missing or unparseable YAML front-matter"))
                continue
            if fm.get("protocol") != "along":
                errors.append((rel, f"missing or invalid protocol: '{fm.get('protocol')}' (expected 'along')"))
            if not fm.get("slug"):
                errors.append((rel, "missing mandatory field: 'slug'"))
            if not fm.get("title"):
                errors.append((rel, "missing mandatory field: 'title'"))
            cat = fm.get("category")
            if cat and cat not in CHECKLIST_CATEGORIES:
                errors.append((rel, f"invalid category: '{cat}' (allowed: {', '.join(CHECKLIST_CATEGORIES)})"))

    risks_dir = os.path.join(sdir, "RISKS")
    if os.path.isdir(risks_dir):
        for fname in os.listdir(risks_dir):
            if not fname.endswith(".md"):
                continue
            scanned += 1
            fpath = os.path.join(risks_dir, fname)
            rel = os.path.relpath(fpath, repo_root)
            try:
                c = textio.read_text(fpath)
                fm, _, _ = frontmatter.try_parse(c, path=fpath)
            except OSError:
                continue
            if not fm:
                errors.append((rel, "missing or unparseable YAML front-matter"))
                continue
            if fm.get("protocol") != "along":
                errors.append((rel, f"missing or invalid protocol: '{fm.get('protocol')}' (expected 'along')"))
            if not fm.get("slug"):
                errors.append((rel, "missing mandatory field: 'slug'"))
            if not fm.get("title"):
                errors.append((rel, "missing mandatory field: 'title'"))
            sev = fm.get("severity")
            if sev and sev not in RISK_SEVERITIES:
                errors.append((rel, f"invalid severity: '{sev}' (allowed: {', '.join(RISK_SEVERITIES)})"))
            rstatus = fm.get("status")
            if rstatus and rstatus not in RISK_STATUSES:
                errors.append((rel, f"invalid status: '{rstatus}' (allowed: {', '.join(RISK_STATUSES)})"))

    spikes_dir = os.path.join(sdir, "SPIKES")
    if os.path.isdir(spikes_dir):
        for fname in os.listdir(spikes_dir):
            if not fname.endswith(".md"):
                continue
            scanned += 1
            fpath = os.path.join(spikes_dir, fname)
            rel = os.path.relpath(fpath, repo_root)
            try:
                c = textio.read_text(fpath)
                fm, _, _ = frontmatter.try_parse(c, path=fpath)
            except OSError:
                continue
            if not fm:
                errors.append((rel, "missing or unparseable YAML front-matter"))
                continue
            if fm.get("protocol") != "along":
                errors.append((rel, f"missing or invalid protocol: '{fm.get('protocol')}' (expected 'along')"))
            if not fm.get("slug"):
                errors.append((rel, "missing mandatory field: 'slug'"))
            if not fm.get("title"):
                errors.append((rel, "missing mandatory field: 'title'"))
            sstatus = fm.get("status")
            if sstatus and sstatus not in SPIKE_STATUSES:
                errors.append((rel, f"invalid status: '{sstatus}' (allowed: {', '.join(SPIKE_STATUSES)})"))

    # 4. Validate Sessions
    sessions_dir = os.path.join(sdir, "SESSIONS")
    if os.path.isdir(sessions_dir):
        for root, _, files in os.walk(sessions_dir):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                scanned += 1
                fpath = os.path.join(root, fname)
                rel = os.path.relpath(fpath, repo_root)
                try:
                    c = textio.read_text(fpath)
                    fm, _, _ = frontmatter.try_parse(c, path=fpath)
                except OSError:
                    continue
                if not fm:
                    errors.append((rel, "missing or unparseable YAML front-matter"))
                    continue
                if fm.get("protocol") != "along":
                    errors.append((rel, f"missing or invalid protocol: '{fm.get('protocol')}' (expected 'along')"))
                if not fm.get("slug"):
                    errors.append((rel, "missing mandatory field: 'slug'"))
                sdate = fm.get("date")
                if sdate and not is_iso_date(sdate):
                    errors.append((rel, f"invalid session date: '{sdate}' (expected YYYY-MM-DD)"))
                mslug = fm.get("milestone")
                if mslug and str(mslug).strip() and str(mslug).strip() not in known_milestone_slugs:
                    errors.append((rel, f"dangling milestone reference: '{mslug}'"))
                for key in ("issues_advanced", "issues_completed"):
                    items = fm.get(key)
                    if isinstance(items, list):
                        for item in items:
                            if item and not _resolve_ref(item, known_issue_keys):
                                errors.append((rel, f"dangling {key} reference: '{item}'"))

    # 5. Validate Decisions (.along/DECISIONS/*.md)
    dec_dir = os.path.join(sdir, "DECISIONS")
    if os.path.isdir(dec_dir):
        for fname in sorted(os.listdir(dec_dir)):
            if not fname.endswith(".md"):
                continue
            scanned += 1
            fpath = os.path.join(dec_dir, fname)
            rel = os.path.relpath(fpath, repo_root)
            try:
                c = textio.read_text(fpath)
                fm, _, _ = frontmatter.try_parse(c, path=fpath)
            except OSError:
                continue
            if not fm:
                errors.append((rel, "missing or unparseable YAML front-matter"))
                continue
            if fm.get("protocol") != "along":
                errors.append((rel, f"missing or invalid protocol: '{fm.get('protocol')}' (expected 'along')"))
            dslug = fm.get("slug")
            if not dslug:
                errors.append((rel, "missing mandatory field: 'slug'"))
            if not fm.get("title"):
                errors.append((rel, "missing mandatory field: 'title'"))
            ddate = fm.get("date")
            if not ddate or not is_iso_date(ddate):
                errors.append((rel, f"missing or invalid date: '{ddate}' (expected YYYY-MM-DD)"))
            dstatus = fm.get("status")
            if not dstatus:
                errors.append((rel, "missing mandatory field: 'status'"))
            elif dstatus not in DECISION_STATUSES and not str(dstatus).startswith("superseded"):
                errors.append((rel, f"invalid status: '{dstatus}' (allowed: {', '.join(DECISION_STATUSES)})"))

            sup_by = fm.get("superseded_by")
            if sup_by and str(sup_by).strip():
                if not _resolve_ref(sup_by, known_entity_keys):
                    errors.append((rel, f"dangling superseded_by reference: '{sup_by}'"))

    return {
        "clean": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "scanned": scanned,
    }


