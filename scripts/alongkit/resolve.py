#!/usr/bin/env python3
"""
alongkit.resolve - Semantic conflict auto-resolution engine for documentation and markdown.

When multiple branches modify the same documentation files concurrently, git 3-way
merge frequently stops on non-overlapping section additions, bullet points, checklists,
and table rows. This module provides structural reconciliation heuristics to combine
dual contributions cleanly while verifying link integrity and typography.
"""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along resolve --docs   (or: python scripts/along_resolve.py --docs)"
    )

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from . import closeout, frontmatter, markdown, merge, proc, repo, typography


@dataclass
class ConflictHunk:
    """One git conflict hunk in a file."""
    start_line: int
    end_line: int
    ours: List[str]
    theirs: List[str]
    base: Optional[List[str]] = None
    ours_label: str = ""
    theirs_label: str = ""
    base_label: str = ""


_CONFLICT_START_RE = re.compile(r"^<{7}(?: (.*))?$")
_CONFLICT_BASE_RE = re.compile(r"^\|{7}(?: (.*))?$")
_CONFLICT_SEP_RE = re.compile(r"^={7}(?: (.*))?$")
_CONFLICT_END_RE = re.compile(r"^>{7}(?: (.*))?$")

_HEADING_RE = re.compile(r"^ {0,3}(#{1,6})\s+(.+?)(?:\s+#+\s*)?$")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_DELIM_RE = re.compile(r"^\s*\|(?:\s*:?-+:?\s*\|)+\s*$")
_CHECKLIST_RE = re.compile(r"^(\s*[-*+]\s+\[)([ xX])(\]\s+)(.*)$")
_BULLET_RE = re.compile(r"^(\s*[-*+]\s+)(.*)$")
_NUMBERED_RE = re.compile(r"^(\s*\d+\.\s+)(.*)$")


def parse_conflict_hunks(text: str) -> Tuple[List[Union[str, ConflictHunk]], bool]:
    """Parse text into literal string chunks and ConflictHunk objects.

    Uses FenceTracker so that conflict marker syntax inside markdown code blocks
    is treated as verbatim code content rather than active merge markers.
    Setext heading underlines (=======) outside conflict hunks are also preserved.
    """
    chunks: List[Union[str, ConflictHunk]] = []
    lines = text.splitlines(keepends=True)
    tracker = markdown.FenceTracker()

    state = "OUTSIDE"
    start_line = 0
    ours_lines: List[str] = []
    theirs_lines: List[str] = []
    base_lines: Optional[List[str]] = None
    ours_label = ""
    theirs_label = ""
    base_label = ""
    current_plain: List[str] = []

    for idx, line in enumerate(lines, 1):
        is_fence_boundary = tracker.process_line(line)

        # Code fence lines and lines inside code fences cannot be conflict markers
        if is_fence_boundary or tracker.in_fence:
            if state == "OUTSIDE":
                current_plain.append(line)
            elif state == "OURS":
                ours_lines.append(line)
            elif state == "BASE":
                if base_lines is not None:
                    base_lines.append(line)
            elif state == "THEIRS":
                theirs_lines.append(line)
            continue

        raw = line.rstrip("\r\n")

        if state == "OUTSIDE":
            m_start = _CONFLICT_START_RE.match(raw)
            if m_start:
                if current_plain:
                    chunks.append("".join(current_plain))
                    current_plain = []
                state = "OURS"
                start_line = idx
                ours_label = (m_start.group(1) or "").strip()
                ours_lines = []
                theirs_lines = []
                base_lines = None
                base_label = ""
                theirs_label = ""
            else:
                current_plain.append(line)

        elif state == "OURS":
            m_base = _CONFLICT_BASE_RE.match(raw)
            m_sep = _CONFLICT_SEP_RE.match(raw)
            if m_base:
                state = "BASE"
                base_label = (m_base.group(1) or "").strip()
                base_lines = []
            elif m_sep:
                state = "THEIRS"
            else:
                ours_lines.append(line)

        elif state == "BASE":
            m_sep = _CONFLICT_SEP_RE.match(raw)
            if m_sep:
                state = "THEIRS"
            else:
                if base_lines is not None:
                    base_lines.append(line)

        elif state == "THEIRS":
            m_end = _CONFLICT_END_RE.match(raw)
            if m_end:
                theirs_label = (m_end.group(1) or "").strip()
                hunk = ConflictHunk(
                    start_line=start_line,
                    end_line=idx,
                    ours=ours_lines,
                    theirs=theirs_lines,
                    base=base_lines,
                    ours_label=ours_label,
                    theirs_label=theirs_label,
                    base_label=base_label,
                )
                chunks.append(hunk)
                state = "OUTSIDE"
            else:
                theirs_lines.append(line)

    if state != "OUTSIDE":
        # Unclosed conflict hunk
        if state == "OURS":
            current_plain.append(f"<<<<<<< {ours_label}\n")
            current_plain.extend(ours_lines)
        elif state == "BASE":
            current_plain.append(f"<<<<<<< {ours_label}\n")
            current_plain.extend(ours_lines)
            current_plain.append(f"||||||| {base_label}\n")
            if base_lines:
                current_plain.extend(base_lines)
        elif state == "THEIRS":
            current_plain.append(f"<<<<<<< {ours_label}\n")
            current_plain.extend(ours_lines)
            if base_lines is not None:
                current_plain.append(f"||||||| {base_label}\n")
                current_plain.extend(base_lines)
            current_plain.append("=======\n")
            current_plain.extend(theirs_lines)
        chunks.append("".join(current_plain))
        return chunks, False

    if current_plain:
        chunks.append("".join(current_plain))

    return chunks, True


def reconcile_markdown_tables(ours: List[str], theirs: List[str]) -> Optional[List[str]]:
    """Reconcile non-overlapping markdown table rows if both sides represent valid tables."""
    ours_clean = [line for line in ours if line.strip()]
    theirs_clean = [line for line in theirs if line.strip()]

    if len(ours_clean) < 2 or len(theirs_clean) < 2:
        return None

    if not all(_TABLE_ROW_RE.match(line) for line in ours_clean):
        return None
    if not all(_TABLE_ROW_RE.match(line) for line in theirs_clean):
        return None

    # Check header and delimiter row
    if not _TABLE_DELIM_RE.match(ours_clean[1]) or not _TABLE_DELIM_RE.match(theirs_clean[1]):
        return None

    def parse_cells(row: str) -> List[str]:
        stripped = row.strip().strip("|")
        return [c.strip() for c in stripped.split("|")]

    ours_cols = parse_cells(ours_clean[0])
    theirs_cols = parse_cells(theirs_clean[0])

    if len(ours_cols) != len(theirs_cols):
        return None

    header_row = ours_clean[0]
    delim_row = ours_clean[1]

    # Combine data rows preserving ours order, appending new theirs rows
    seen: Set[Tuple[str, ...]] = set()
    result_rows: List[str] = [header_row, delim_row]

    for row in ours_clean[2:]:
        key = tuple(parse_cells(row))
        if key not in seen:
            seen.add(key)
            result_rows.append(row)

    for row in theirs_clean[2:]:
        key = tuple(parse_cells(row))
        if key not in seen:
            seen.add(key)
            result_rows.append(row)

    return result_rows


def reconcile_markdown_lists(ours: List[str], theirs: List[str]) -> Optional[List[str]]:
    """Reconcile list and checklist items via set-union deduplication."""
    ours_items = [line for line in ours if line.strip()]
    theirs_items = [line for line in theirs if line.strip()]

    if not ours_items and not theirs_items:
        return []

    is_list = lambda l: bool(_CHECKLIST_RE.match(l) or _BULLET_RE.match(l) or _NUMBERED_RE.match(l))
    if ours_items and not all(is_list(l) for l in ours_items):
        return None
    if theirs_items and not all(is_list(l) for l in theirs_items):
        return None

    # Determine if checklist items are present
    has_checklists = any(_CHECKLIST_RE.match(l) for l in ours_items + theirs_items)

    result: List[str] = []
    seen: Dict[str, int] = {}  # key -> index in result

    def item_key(line: str) -> Tuple[str, str]:
        m_chk = _CHECKLIST_RE.match(line)
        if m_chk:
            return ("checklist", m_chk.group(4).strip().lower())
        m_num = _NUMBERED_RE.match(line)
        if m_num:
            return ("numbered", m_num.group(2).strip().lower())
        m_bul = _BULLET_RE.match(line)
        if m_bul:
            return ("bullet", m_bul.group(2).strip().lower())
        return ("other", line.strip().lower())

    for line in ours:
        if not line.strip():
            result.append(line)
            continue
        kind, key = item_key(line)
        seen[key] = len(result)
        result.append(line)

    for line in theirs:
        if not line.strip():
            continue
        kind, key = item_key(line)
        if key in seen:
            idx = seen[key]
            existing_line = result[idx]
            # If checklist: [x] takes priority over [ ]
            if has_checklists:
                m_existing = _CHECKLIST_RE.match(existing_line)
                m_incoming = _CHECKLIST_RE.match(line)
                if m_existing and m_incoming:
                    ex_checked = m_existing.group(2).lower() == "x"
                    in_checked = m_incoming.group(2).lower() == "x"
                    if not ex_checked and in_checked:
                        # Upgrade to checked [x]
                        prefix = m_incoming.group(1)
                        mid = m_incoming.group(3)
                        body = m_incoming.group(4)
                        result[idx] = f"{prefix}x{mid}{body}\n" if not existing_line.endswith("\n") else f"{prefix}x{mid}{body}\n"
        else:
            seen[key] = len(result)
            result.append(line)

    return result


def _split_into_sections(lines: List[str]) -> Tuple[List[str], List[Tuple[int, str, str, List[str]]]]:
    """Split lines into preamble and list of (level, title, heading_line, section_lines)."""
    preamble: List[str] = []
    sections: List[Tuple[int, str, str, List[str]]] = []
    current_section: Optional[Tuple[int, str, str, List[str]]] = None

    for line in lines:
        m = _HEADING_RE.match(line.rstrip("\r\n"))
        if m:
            if current_section is not None:
                sections.append(current_section)
            level = len(m.group(1))
            title = m.group(2).strip()
            current_section = (level, title, line, [line])
        else:
            if current_section is None:
                preamble.append(line)
            else:
                current_section[3].append(line)

    if current_section is not None:
        sections.append(current_section)

    return preamble, sections


def reconcile_markdown_sections(ours: List[str], theirs: List[str],
                                base: Optional[List[str]] = None) -> Optional[List[str]]:
    """Reconcile non-overlapping markdown section additions under common parent context."""
    pre_ours, sec_ours = _split_into_sections(ours)
    pre_theirs, sec_theirs = _split_into_sections(theirs)

    if not sec_ours and not sec_theirs:
        return None

    ours_titles = {title.lower() for _, title, _, _ in sec_ours}
    theirs_titles = {title.lower() for _, title, _, _ in sec_theirs}

    # If headings are completely disjoint, append all ours sections then all theirs sections
    if ours_titles.isdisjoint(theirs_titles):
        result: List[str] = []
        if pre_ours:
            result.extend(pre_ours)
        elif pre_theirs:
            result.extend(pre_theirs)

        for _, _, _, sec_lines in sec_ours:
            result.extend(sec_lines)
            if not sec_lines[-1].endswith("\n"):
                result.append("\n")

        for _, _, _, sec_lines in sec_theirs:
            result.extend(sec_lines)
            if not sec_lines[-1].endswith("\n"):
                result.append("\n")

        return result

    # If there is an identical single section, attempt recursive reconciliation of its body
    if len(sec_ours) == 1 and len(sec_theirs) == 1:
        lvl_o, title_o, hdr_o, lines_o = sec_ours[0]
        lvl_t, title_t, hdr_t, lines_t = sec_theirs[0]
        if lvl_o == lvl_t and title_o.lower() == title_t.lower():
            body_o = lines_o[1:]
            body_t = lines_t[1:]
            # Try list or table reconciliation on body
            sub_res = reconcile_markdown_lists(body_o, body_t)
            if sub_res is None:
                sub_res = reconcile_markdown_tables(body_o, body_t)
            if sub_res is not None:
                result = []
                if pre_ours:
                    result.extend(pre_ours)
                result.append(hdr_o)
                result.extend(sub_res)
                return result

    return None


def reconcile_hunk(hunk: ConflictHunk, repo_root: str = "") -> Tuple[str, bool, str]:
    """Attempt structural reconciliation on a conflict hunk.

    Returns (replacement_text, is_clean, resolution_method).
    """
    # Exact match on both sides
    if hunk.ours == hunk.theirs:
        return "".join(hunk.ours), True, "identical"

    # One side empty and matches base
    if hunk.base is not None:
        if hunk.ours == hunk.base and hunk.theirs != hunk.base:
            return "".join(hunk.theirs), True, "theirs_addition"
        if hunk.theirs == hunk.base and hunk.ours != hunk.base:
            return "".join(hunk.ours), True, "ours_addition"

    # Attempt markdown table reconciliation
    tbl = reconcile_markdown_tables(hunk.ours, hunk.theirs)
    if tbl is not None:
        return "".join(tbl), True, "table_union"

    # Attempt markdown list and checklist reconciliation
    lst = reconcile_markdown_lists(hunk.ours, hunk.theirs)
    if lst is not None:
        return "".join(lst), True, "list_union"

    # Attempt markdown section reconciliation
    sec = reconcile_markdown_sections(hunk.ours, hunk.theirs, hunk.base)
    if sec is not None:
        return "".join(sec), True, "section_merge"

    # Attempt standard 3-way text merge if base is available
    if hunk.base is not None:
        merged, clean = merge.text_merge("".join(hunk.base), "".join(hunk.ours), "".join(hunk.theirs))
        if clean:
            return merged, True, "text_3way"

    # Unresolved: preserve standard conflict markers for manual/agent review
    unresolved: List[str] = [f"<<<<<<< {hunk.ours_label or 'ours'}\n"]
    unresolved.extend(hunk.ours)
    if hunk.base is not None:
        unresolved.append(f"||||||| {hunk.base_label or 'base'}\n")
        unresolved.extend(hunk.base)
    unresolved.append("=======\n")
    unresolved.extend(hunk.theirs)
    unresolved.append(f">>>>>>> {hunk.theirs_label or 'theirs'}\n")

    return "".join(unresolved), False, "unresolved"


def resolve_markdown_content(text: str, file_path: str = "",
                             repo_root: str = "",
                             strict: bool = False) -> Tuple[str, bool, List[str]]:
    """Parse, reconcile, and validate a markdown document containing conflict markers.

    Returns (merged_text, clean, warnings).
    """
    warnings: List[str] = []
    chunks, valid_syntax = parse_conflict_hunks(text)

    if not valid_syntax:
        warnings.append("Malformed or unclosed conflict markers in content")
        return text, False, warnings

    reconciled_parts: List[str] = []
    all_clean = True

    for chunk in chunks:
        if isinstance(chunk, str):
            reconciled_parts.append(chunk)
        elif isinstance(chunk, ConflictHunk):
            resolved, clean, method = reconcile_hunk(chunk, repo_root=repo_root)
            reconciled_parts.append(resolved)
            if not clean:
                all_clean = False
                warnings.append(
                    f"Line {chunk.start_line}-{chunk.end_line}: unresolvable prose conflict"
                )
            else:
                warnings.append(
                    f"Line {chunk.start_line}-{chunk.end_line}: resolved via {method}"
                )

    merged_text = "".join(reconciled_parts)

    # If completely clean, verify link integrity and typography
    if all_clean and file_path and repo_root:
        # Check link integrity
        broken_links = markdown.find_broken_links(merged_text, file_path, repo_root)
        if broken_links:
            for b in broken_links:
                warnings.append(f"Broken link line {b.get('line')}: {b.get('reason')}")
            if strict:
                all_clean = False

        # Verify typography
        sanitized, changed = typography.clean(merged_text)
        if changed:
            merged_text = sanitized
            warnings.append("Sanitized non-ASCII typographic characters")

    return merged_text, all_clean, warnings


def get_unmerged_docs(repo_root: str) -> List[str]:
    """Find unmerged markdown files across the repository."""
    changes = closeout.git_changes(repo_root)
    unmerged: List[str] = []
    for path, code in changes.items():
        if code in closeout._UNMERGED_CODES:
            norm_path = path.replace("\\", "/")
            if norm_path.endswith(".md"):
                if norm_path.startswith("docs/") or norm_path in ("README.md", "AGENTS.md", "CONTRIBUTING.md"):
                    unmerged.append(norm_path)
    return sorted(unmerged)
