#!/usr/bin/env python3
# along_kb_search.py - Unified Multi-Scope Knowledge Retrieval Engine across docs/ and .along/ artifacts.

import os
import re
import sys
import argparse
import math
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap

# This engine reads entity front-matter, so it needs ruamel.yaml. Resolve it before
# anything imports it: an engine invoked as `python <path>/<engine>.py` may start
# under an interpreter that has no dependencies prepared, which is exactly how the
# installers and the documented skill commands invoke it.
bootstrap.ensure_deps()

from alongkit import entities, frontmatter, markdown, repo
from alongkit.diagnostics import try_record_incident

# The ADR header formats, the heading-anchor algorithm, and the front-matter reader
# live in the shared package. This engine was the reader that missed the v2.2.0 header
# change, which is why ADR search returned zero results in every released version:
# see [bug--adr-retrieval-blind-to-slug-headers].
ADR_SPLIT_RE = entities.ADR_SPLIT_RE
ADR_HEADER_RE = entities.ADR_HEADER_RE
github_heading_anchor = markdown.github_heading_anchor
parse_decision_entries = entities.parse_decision_entries


# Strict reader so malformed files raise FrontmatterError and are counted in skipped
parse_frontmatter = frontmatter.parse

ARCHIVED_ISSUE_STATUSES = {"done", "superseded", "cancelled", "canceled", "duplicate"}
ARCHIVED_DECISION_STATUSES = {"superseded", "retired", "deprecated", "rejected"}


def is_archived_entry(e: Dict[str, Any]) -> bool:
    """Check if an entity represents an archived or historical record."""
    cat = (e.get("category") or "").lower()
    if cat == "session":
        return True
    if cat == "issue":
        status = str(e.get("status") or "").lower()
        fpath = str(e.get("file_path") or "").replace("\\", "/").lower()
        if status in ARCHIVED_ISSUE_STATUSES:
            return True
        if "/done/" in fpath or fpath.startswith("done/") or "done" in fpath.split("/"):
            return True
        return False
    if cat == "decision":
        status = str(e.get("status") or "").lower()
        if status in ARCHIVED_DECISION_STATUSES:
            return True
        return False
    return False


def collect_all_entries(repo_root, verbose=False):
    entries = []
    skipped = []
    repo_root = os.path.abspath(repo_root)
    docs_dir = os.path.join(repo_root, "docs")
    along_dir = os.path.join(repo_root, ".along")
    if not os.path.exists(along_dir):
        along_dir = os.path.join(repo_root, ".agents")

    def _record_skip(rel_file: str, exc: Exception) -> None:
        skipped.append((rel_file, str(exc)))
        try_record_incident(
            component="along_kb_search",
            error_message=f"collector skipped {rel_file}: {exc}",
            event_type="collector_skip",
            extra_metadata={"file": rel_file, "error": str(exc)},
        )
        if verbose:
            print(f"   [WARN] skipped {rel_file}: {exc}", file=sys.stderr)

    # 1. Curated Knowledge Base (docs/*.md, excluding generated mirrors like docs/decisions/)
    if os.path.exists(docs_dir):
        for f in sorted(os.listdir(docs_dir)):
            if not f.endswith(".md") or f == "INDEX.md" or f == "decisions":
                continue
            fp = os.path.join(docs_dir, f)
            if not os.path.isfile(fp):
                continue
            rel_path = f"docs/{f}"
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
                    "file_path": rel_path,
                    "abs_path": fp,
                    "raw": raw,
                    "body": body
                })
            except (OSError, ValueError, AttributeError, TypeError, frontmatter.FrontmatterError) as exc:
                _record_skip(rel_path, exc)

    # 2. Issues & Backlog (.along/ISSUES/**/*.md)
    issues_dir = os.path.join(along_dir, "ISSUES")
    if os.path.exists(issues_dir):
        for root, _, files in os.walk(issues_dir):
            for f in files:
                if not f.endswith(".md"):
                    continue
                fp = os.path.join(root, f)
                rel_path = os.path.relpath(fp, repo_root).replace("\\", "/")
                try:
                    with open(fp, "r", encoding="utf-8", errors="replace") as p:
                        raw = p.read()
                    fm, body = parse_frontmatter(raw)
                    slug = fm.get("slug", f.replace(".md", ""))
                    status = fm.get("status", "done" if "done" in rel_path else "open")
                    iss_type = fm.get("type", "task")
                    entries.append({
                        "category": "issue",
                        "category_label": "Issue",
                        "title": f"[{iss_type.upper()}] {slug.replace('-', ' ').title()}",
                        "slug": slug,
                        "type": iss_type,
                        "tags": fm.get("tags", []) if isinstance(fm.get("tags", []), list) else ([fm.get("tags")] if fm.get("tags") else []),
                        "status": status,
                        "priority": fm.get("priority", "medium"),
                        "file_path": rel_path,
                        "abs_path": fp,
                        "raw": raw,
                        "body": body
                    })
                except (OSError, ValueError, AttributeError, TypeError, frontmatter.FrontmatterError) as exc:
                    _record_skip(rel_path, exc)

    # 3. Architectural Decision Records (.along/DECISIONS/*.md or .along/DECISIONS.md)
    dec_dir = os.path.join(along_dir, "DECISIONS")
    dec_files = [f for f in os.listdir(dec_dir) if f.endswith(".md")] if os.path.isdir(dec_dir) else []
    if dec_files:
        for f in sorted(dec_files):
            fp = os.path.join(dec_dir, f)
            rel_path = os.path.relpath(fp, repo_root).replace("\\", "/")
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as p:
                    raw = p.read()
                fm, body = parse_frontmatter(raw)
                fslug = f[:-3]
                slug_match = re.match(r"^ADR-\d{4}-\d{2}-\d{2}--(?P<slug>.+)$", fslug)
                inferred_slug = slug_match.group("slug") if slug_match else fslug
                dslug = fm.get("slug") or inferred_slug
                title = fm.get("title")
                if not title:
                    first_line = body.strip().splitlines()[0] if body.strip() else ""
                    h_match = re.match(r"^#+\s+(?:ADR-[^-\s]+--[^\s]+\s+-\s+)?(.*)$", first_line)
                    title = h_match.group(1).strip() if h_match and h_match.group(1) else dslug.replace("-", " ").title()
                entries.append({
                    "category": "decision",
                    "category_label": "ADR",
                    "title": f"ADR - {title}",
                    "slug": dslug,
                    "type": "adr",
                    "tags": fm.get("tags") or ["adr", "architecture", "decision"],
                    "status": fm.get("status") or ("superseded" if re.search(r"superseded\s+by", body, re.IGNORECASE) else "active"),
                    "file_path": rel_path,
                    "abs_path": fp,
                    "raw": raw,
                    "body": body,
                })
            except (OSError, ValueError, AttributeError, TypeError, frontmatter.FrontmatterError) as exc:
                _record_skip(rel_path, exc)
    else:
        decisions_path = os.path.join(along_dir, "DECISIONS.md")
        if os.path.exists(decisions_path):
            dec_rel = os.path.relpath(decisions_path, repo_root).replace("\\", "/")
            try:
                with open(decisions_path, "r", encoding="utf-8", errors="replace") as p:
                    dec_raw = p.read()
                parsed_adrs = parse_decision_entries(dec_raw, rel_path=dec_rel)
                for pa in parsed_adrs:
                    pa["abs_path"] = decisions_path
                    pa["raw"] = dec_raw
                entries.extend(parsed_adrs)
            except (OSError, ValueError, AttributeError, TypeError) as exc:
                _record_skip(dec_rel, exc)

    # 4. Milestones & Sprints (.along/MILESTONES/*.md)
    ms_dir = os.path.join(along_dir, "MILESTONES")
    if os.path.exists(ms_dir):
        for f in os.listdir(ms_dir):
            if not f.endswith(".md"):
                continue
            fp = os.path.join(ms_dir, f)
            rel_path = os.path.relpath(fp, repo_root).replace("\\", "/")
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as p:
                    raw = p.read()
                fm, body = parse_frontmatter(raw)
                entries.append({
                    "category": "milestone",
                    "category_label": "Milestone",
                    "title": fm.get("title", f.replace(".md", "").title()),
                    "slug": fm.get("slug", f.replace(".md", "")),
                    "type": "milestone",
                    "tags": ["milestone", "sprint"],
                    "status": fm.get("status", "open"),
                    "file_path": rel_path,
                    "abs_path": fp,
                    "raw": raw,
                    "body": body
                })
            except (OSError, ValueError, AttributeError, TypeError, frontmatter.FrontmatterError) as exc:
                _record_skip(rel_path, exc)

    # 5. Risks & Blockers (.along/RISKS/*.md)
    risks_dir = os.path.join(along_dir, "RISKS")
    if os.path.exists(risks_dir):
        for f in os.listdir(risks_dir):
            if not f.endswith(".md"):
                continue
            fp = os.path.join(risks_dir, f)
            rel_path = os.path.relpath(fp, repo_root).replace("\\", "/")
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as p:
                    raw = p.read()
                fm, body = parse_frontmatter(raw)
                entries.append({
                    "category": "risk",
                    "category_label": f"Risk ({fm.get('severity', 'medium')})",
                    "title": fm.get("title", f.replace(".md", "").title()),
                    "slug": fm.get("slug", f.replace(".md", "")),
                    "type": "risk",
                    "tags": ["risk", "blocker", fm.get("severity", "medium")],
                    "status": fm.get("status", "active"),
                    "file_path": rel_path,
                    "abs_path": fp,
                    "raw": raw,
                    "body": body
                })
            except (OSError, ValueError, AttributeError, TypeError, frontmatter.FrontmatterError) as exc:
                _record_skip(rel_path, exc)

    # 6. Spikes & R&D (.along/SPIKES/*.md)
    spikes_dir = os.path.join(along_dir, "SPIKES")
    if os.path.exists(spikes_dir):
        for f in os.listdir(spikes_dir):
            if not f.endswith(".md"):
                continue
            fp = os.path.join(spikes_dir, f)
            rel_path = os.path.relpath(fp, repo_root).replace("\\", "/")
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as p:
                    raw = p.read()
                fm, body = parse_frontmatter(raw)
                entries.append({
                    "category": "spike",
                    "category_label": "Spike R&D",
                    "title": fm.get("title", f.replace(".md", "").title()),
                    "slug": fm.get("slug", f.replace(".md", "")),
                    "type": "spike",
                    "tags": ["spike", "experiment"],
                    "status": fm.get("status", "evaluating"),
                    "file_path": rel_path,
                    "abs_path": fp,
                    "raw": raw,
                    "body": body
                })
            except (OSError, ValueError, AttributeError, TypeError, frontmatter.FrontmatterError) as exc:
                _record_skip(rel_path, exc)

    # 7. Session Logs (.along/SESSIONS/**/*.md)
    sess_dir = os.path.join(along_dir, "SESSIONS")
    if os.path.exists(sess_dir):
        for root, _, files in os.walk(sess_dir):
            for f in files:
                if not f.endswith(".md"):
                    continue
                fp = os.path.join(root, f)
                rel_p = os.path.relpath(fp, repo_root).replace("\\", "/")
                try:
                    with open(fp, "r", encoding="utf-8", errors="replace") as p:
                        raw = p.read()
                    fm, body = parse_frontmatter(raw)
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
                        "abs_path": fp,
                        "raw": raw,
                        "body": body
                    })
                except (OSError, ValueError, AttributeError, TypeError, frontmatter.FrontmatterError) as exc:
                    _record_skip(rel_p, exc)

    if skipped:
        print(f"[Warning] {len(skipped)} malformed or unreadable file(s) skipped during KB search.", file=sys.stderr)

    return entries

def parse_query(raw_query: str) -> Tuple[List[str], List[str]]:
    """Parse search query into quoted phrases and individual words."""
    if not raw_query:
        return [], []
    phrases = []
    for m in re.finditer(r'"([^"]+)"', raw_query):
        p = m.group(1).strip().lower()
        if p:
            phrases.append(p)
    remainder = re.sub(r'"[^"]+"', ' ', raw_query)
    terms = [t.lower().strip() for t in re.findall(r'[\w\-]+', remainder) if t.strip()]
    return phrases, terms


def light_stem(word: str) -> str:
    """Lightweight suffix stemmer for English search terms without external dependencies."""
    w = word.lower()
    if len(w) <= 3:
        return w
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 4 and w[-3] in "shxz":
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    if w.endswith("ing") and len(w) > 5:
        base = w[:-3]
        if len(base) >= 3 and base[-1] == base[-2] and base[-1] not in "aeiouy":
            return base[:-1]
        return base
    if w.endswith("ed") and len(w) > 4:
        base = w[:-2]
        if len(base) >= 3 and base[-1] == base[-2] and base[-1] not in "aeiouy":
            return base[:-1]
        return base
    return w


def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase word tokens."""
    return [t.lower() for t in re.findall(r'[\w\-]+', text) if t]


def compute_idf(entries: List[Dict[str, Any]]) -> Dict[str, float]:
    """Compute smoothed inverse document frequency across the corpus."""
    n = max(1, len(entries))
    df: Dict[str, int] = {}
    for e in entries:
        seen: Set[str] = set()
        tokens = tokenize(e.get("title", "")) + tokenize(e.get("slug", ""))
        for t in e.get("tags", []):
            tokens.extend(tokenize(str(t)))
        tokens.extend(tokenize(e.get("body", "")))
        for tok in tokens:
            if tok not in seen:
                seen.add(tok)
                df[tok] = df.get(tok, 0) + 1
            st = light_stem(tok)
            if st != tok and st not in seen:
                seen.add(st)
                df[st] = df.get(st, 0) + 1

    idf: Dict[str, float] = {}
    for tok, freq in df.items():
        idf[tok] = math.log((n + 1.0) / (freq + 1.0)) + 1.0
    return idf


def extract_passage_snippet(
    body: str, query_terms: Sequence[str], phrases: Sequence[str], max_chars: int = 240
) -> str:
    """Extract a word-boundary-aligned passage containing query terms."""
    if not body or not body.strip():
        return ""

    clean_body = body.replace("\r\n", "\n")
    candidates = [p.strip() for p in re.split(r'\n{2,}|\n(?=[#\-\*])|(?<=[.!?])\s+', clean_body) if p.strip()]
    if not candidates:
        candidates = [clean_body.strip()]

    best_candidate = ""
    best_score = -1

    for cand in candidates:
        cand_lower = cand.lower()
        cand_tokens = set(tokenize(cand_lower))
        cand_stems = {light_stem(t) for t in cand_tokens}

        score = 0
        for phrase in phrases:
            if phrase in cand_lower:
                score += 12
        for term in query_terms:
            if term in cand_tokens:
                score += 5
            elif light_stem(term) in cand_stems:
                score += 3

        if score > best_score:
            best_score = score
            best_candidate = cand

    if not best_candidate:
        best_candidate = candidates[0]

    # Clean markdown headers and bullet prefixes
    text = re.sub(r'^[#\-*>]+\s*', '', best_candidate).strip()
    text = re.sub(r'\s+', ' ', text)

    if len(text) <= max_chars:
        return text

    # Locate the best term position to center the snippet
    text_lower = text.lower()
    first_match_pos = -1
    matched_term_len = 0

    for phrase in phrases:
        p_pos = text_lower.find(phrase.lower())
        if p_pos != -1:
            first_match_pos = p_pos
            matched_term_len = len(phrase)
            break

    if first_match_pos == -1:
        for term in query_terms:
            t_pos = text_lower.find(term.lower())
            if t_pos != -1:
                first_match_pos = t_pos
                matched_term_len = len(term)
                break
            st = light_stem(term)
            st_pos = text_lower.find(st)
            if st_pos != -1:
                first_match_pos = st_pos
                matched_term_len = len(st)
                break

    if first_match_pos != -1:
        lead_budget = max(0, (max_chars - matched_term_len) // 3)
        raw_start = max(0, first_match_pos - lead_budget)
        raw_end = min(len(text), raw_start + max_chars)

        start = raw_start
        if raw_start > 0:
            sp = text.find(' ', raw_start)
            if sp != -1 and sp < first_match_pos:
                start = sp + 1

        end = raw_end
        if raw_end < len(text):
            sp = text.rfind(' ', start, raw_end)
            if sp != -1 and sp > first_match_pos:
                end = sp

        snippet = text[start:end].strip()
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(text) else ""
        return f"{prefix}{snippet}{suffix}"

    # Fallback: start of text with word boundary
    truncated = text[:max_chars]
    last_space = truncated.rfind(' ')
    if last_space > max_chars // 2:
        truncated = truncated[:last_space]
    return truncated.strip() + "..."


def extract_passage_location_and_snippet(
    entry: Dict[str, Any],
    query_terms: Sequence[str],
    phrases: Sequence[str],
    max_words: int = 150,
) -> Tuple[str, str, int, int]:
    """Extract bounded snippet (<= 150 words), enclosing section heading, and 1-indexed line range."""
    full_text = entry.get("raw")
    if not full_text:
        abs_p = entry.get("abs_path")
        if abs_p and os.path.isfile(abs_p):
            try:
                with open(abs_p, "r", encoding="utf-8", errors="replace") as fp:
                    full_text = fp.read()
            except OSError:
                full_text = entry.get("body", "")
        else:
            full_text = entry.get("body", "")

    lines = full_text.splitlines() if full_text else []
    if not lines:
        return ("", entry.get("title", ""), 1, 1)

    blocks: List[Dict[str, Any]] = []
    current_section = entry.get("title", "")
    in_fence = False
    in_fm = False
    cur_block_lines: List[Tuple[int, str]] = []

    def _flush_block():
        nonlocal cur_block_lines
        if cur_block_lines:
            b_text = "\n".join(txt for _, txt in cur_block_lines).strip()
            if b_text:
                blocks.append({
                    "start_line": cur_block_lines[0][0],
                    "end_line": cur_block_lines[-1][0],
                    "section": current_section,
                    "text": b_text,
                })
            cur_block_lines = []

    for idx, line in enumerate(lines):
        line_num = idx + 1
        stripped = line.strip()

        if idx == 0 and stripped == "---":
            in_fm = True
            continue
        if in_fm:
            if stripped == "---":
                in_fm = False
            continue

        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
            cur_block_lines.append((line_num, line))
            continue

        if not in_fence and stripped.startswith("#"):
            _flush_block()
            current_section = stripped
            cur_block_lines.append((line_num, line))
            continue

        if not stripped and not in_fence:
            _flush_block()
            continue

        cur_block_lines.append((line_num, line))

    _flush_block()

    if not blocks:
        blocks.append({
            "start_line": 1,
            "end_line": len(lines),
            "section": entry.get("title", ""),
            "text": full_text[:400].strip(),
        })

    best_block = blocks[0]
    best_score = -1.0

    for b in blocks:
        b_lower = b["text"].lower()
        b_tokens = tokenize(b_lower)
        b_stems = {light_stem(t) for t in b_tokens}
        score = 0.0

        for phrase in phrases:
            if phrase.lower() in b_lower:
                score += 15.0

        for term in query_terms:
            t_low = term.lower()
            if t_low in b_tokens:
                score += 6.0
            elif light_stem(t_low) in b_stems:
                score += 3.0

        if score > best_score:
            best_score = score
            best_block = b

    text = re.sub(r'^[#\-*>]+\s*', '', best_block["text"]).strip()
    text = re.sub(r'\s+', ' ', text)
    words = text.split()
    if len(words) > max_words:
        snippet = " ".join(words[:max_words]) + "..."
    else:
        snippet = text

    return (
        snippet,
        best_block["section"],
        best_block["start_line"],
        best_block["end_line"],
    )


def generate_knowledge_catalog(repo_root: str = ".", max_tokens: int = 200) -> str:
    """Generate a compact hierarchical text catalog (< 200 tokens) across knowledge scopes."""
    entries = collect_all_entries(repo_root)

    docs = sorted([e for e in entries if e["category"] == "kb"], key=lambda x: x["slug"])
    adrs = sorted([e for e in entries if e["category"] == "decision" and not is_archived_entry(e)], key=lambda x: x["slug"])
    milestones = sorted([e for e in entries if e["category"] == "milestone" and e.get("status") in ("open", "in-progress")], key=lambda x: x["slug"])

    lines = ["=== Along Knowledge Catalog & Project Map ==="]

    max_chars = max_tokens * 4
    docs_char_budget = int(max_chars * 0.35)
    ms_char_budget = int(max_chars * 0.60)
    adr_char_budget = int(max_chars * 0.88)

    # 1. Curated Docs
    lines.append(f"Docs Topics ({len(docs)}):")
    added_docs = 0
    for d in docs:
        slug = d["slug"].replace("topic--", "")
        title = d.get("title") or slug
        if len(title) > 32:
            title = title[:29] + "..."
        line = f"  - {slug}: {title}"
        if sum(len(l) + 1 for l in lines) + len(line) > docs_char_budget and added_docs >= 2:
            rem = len(docs) - added_docs
            if rem > 0:
                lines.append(f"  ... ({rem} more docs)")
            break
        lines.append(line)
        added_docs += 1

    # 2. Active Milestones
    lines.append(f"Active Milestones ({len(milestones)}):")
    added_ms = 0
    for m in milestones:
        status = m.get("status", "open")
        line = f"  - {m['slug']} [{status}]"
        if sum(len(l) + 1 for l in lines) + len(line) > ms_char_budget and added_ms >= 1:
            rem = len(milestones) - added_ms
            if rem > 0:
                lines.append(f"  ... ({rem} more milestones)")
            break
        lines.append(line)
        added_ms += 1

    # 3. Active ADRs
    lines.append(f"Active ADRs ({len(adrs)}):")
    added_adrs = 0
    for a in adrs:
        slug = a["slug"].replace("adr-", "")
        title = a.get("title", slug)
        if title.startswith("ADR - "):
            title = title[6:]
        if len(title) > 32:
            title = title[:29] + "..."
        line = f"  - {slug}: {title}"
        if sum(len(l) + 1 for l in lines) + len(line) > adr_char_budget and added_adrs >= 2:
            rem = len(adrs) - added_adrs
            if rem > 0:
                lines.append(f"  ... ({rem} more active ADRs; query via 'along kb-search -c decision')")
            break
        lines.append(line)
        added_adrs += 1

    return "\n".join(lines)


def calculate_search_stats(entries: List[Dict[str, Any]], results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute corpus and result token estimates for search measurement."""
    total_corpus_chars = sum(len(e.get("body", "")) + len(e.get("title", "")) for e in entries)
    corpus_tokens_est = max(1, total_corpus_chars // 4)

    returned_chars = sum(len(r.get("snippet", "")) + len(r.get("title", "")) for r in results)
    returned_tokens_est = max(1, returned_chars // 4)

    savings_pct = round((1.0 - (returned_tokens_est / corpus_tokens_est)) * 100, 1)

    return {
        "corpus_entries": len(entries),
        "corpus_chars": total_corpus_chars,
        "corpus_tokens_est": corpus_tokens_est,
        "matched_count": len(results),
        "returned_chars": returned_chars,
        "returned_tokens_est": returned_tokens_est,
        "savings_pct": savings_pct,
    }


def search_knowledge_base(
    query: str,
    repo_root: str = ".",
    limit: int = 5,
    category: Optional[str] = None,
    filter_tag: Optional[str] = None,
    match_any: bool = False,
    prefix: bool = False,
    verbose: bool = False,
    return_stats: bool = False,
    include_archive: bool = False,
) -> Any:
    repo_root = os.path.abspath(repo_root)
    phrases, query_terms = parse_query(query)
    entries = collect_all_entries(repo_root, verbose=verbose)
    idf_map = compute_idf(entries) if (query_terms or phrases) else {}

    results = []
    for e in entries:
        if category and category.lower() != "all" and e["category"].lower() != category.lower():
            continue
        if filter_tag and filter_tag.lower() not in [t.lower() for t in e["tags"]]:
            continue

        # Archive filtering: exclude archived entities by default when category is all or not specified
        if (not category or category.lower() == "all") and not include_archive:
            if is_archived_entry(e):
                continue

        title_lower = e["title"].lower()
        slug_lower = e["slug"].lower()
        body_lower = e["body"].lower()

        title_tokens = tokenize(title_lower)
        title_stems = [light_stem(t) for t in title_tokens]
        slug_tokens = tokenize(slug_lower)
        slug_stems = [light_stem(t) for t in slug_tokens]
        tags_tokens = [t.lower() for t in e["tags"]]
        body_tokens = tokenize(body_lower)
        body_stems = [light_stem(t) for t in body_tokens]

        # Check phrase matches
        phrase_matches: Dict[str, bool] = {}
        for phrase in phrases:
            matched = (phrase in title_lower) or (phrase in slug_lower) or (phrase in body_lower)
            phrase_matches[phrase] = matched

        # Check term matches
        term_matches: Dict[str, bool] = {}
        for term in query_terms:
            t_stem = light_stem(term)
            matched = False
            if prefix:
                matched = (
                    any(tok.startswith(term) for tok in title_tokens)
                    or any(tok.startswith(term) for tok in slug_tokens)
                    or any(tok.startswith(term) for tok in tags_tokens)
                    or any(tok.startswith(term) for tok in body_tokens)
                )
            else:
                matched = (
                    (term in title_tokens or t_stem in title_stems)
                    or (term in slug_tokens or t_stem in slug_stems)
                    or (term in tags_tokens)
                    or (term in body_tokens or t_stem in body_stems)
                )
            term_matches[term] = matched

        all_query_items = len(phrases) + len(query_terms)
        if all_query_items > 0:
            if match_any:
                # OR semantics: at least one phrase or term must match
                if not any(phrase_matches.values()) and not any(term_matches.values()):
                    continue
            else:
                # AND semantics: all phrases and all terms must match
                if not all(phrase_matches.values()) or not all(term_matches.values()):
                    continue

        # Compute ranking score
        score = 0.0
        for phrase in phrases:
            if phrase_matches.get(phrase):
                if phrase in title_lower:
                    score += 30.0
                if phrase in slug_lower:
                    score += 20.0
                p_count = body_lower.count(phrase)
                if p_count > 0:
                    score += min(p_count * 15.0, 30.0)

        for term in query_terms:
            t_stem = light_stem(term)
            term_idf = idf_map.get(term, idf_map.get(t_stem, 1.0))

            if term in title_tokens:
                score += 15.0 * term_idf
            elif t_stem in title_stems:
                score += 7.5 * term_idf
            elif prefix and any(tok.startswith(term) for tok in title_tokens):
                score += 6.0 * term_idf

            if term in slug_tokens:
                score += 12.0 * term_idf
            elif t_stem in slug_stems:
                score += 6.0 * term_idf
            elif prefix and any(tok.startswith(term) for tok in slug_tokens):
                score += 5.0 * term_idf

            if term in tags_tokens:
                score += 10.0 * term_idf

            body_tf = body_tokens.count(term) + body_stems.count(t_stem)
            if prefix and body_tf == 0:
                body_tf = sum(1 for tok in body_tokens if tok.startswith(term))
            if body_tf > 0:
                score += min(body_tf * term_idf, 25.0)

        # Status boost for active / in-progress entities
        if e.get("status") in ["open", "in-progress", "active", "accepted"]:
            score += 2.0

        # Curated documentation boost (docs/topic--*.md)
        if e.get("category") == "kb":
            score += 20.0

        # Ranking penalty for archived entities when included
        if is_archived_entry(e):
            score -= 10.0

        snippet, section, line_start, line_end = extract_passage_location_and_snippet(
            e, query_terms, phrases, max_words=150
        )
        base_path = e["file_path"].split("#")[0]
        anchored_path = f"{base_path}#L{line_start}-L{line_end}"

        results.append({
            "category": e["category"],
            "category_label": e["category_label"],
            "title": e["title"],
            "slug": e["slug"],
            "status": e.get("status", "active"),
            "file_path": anchored_path,
            "section": section,
            "line_start": line_start,
            "line_end": line_end,
            "tags": e["tags"],
            "score": score,
            "snippet": snippet
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    top_results = results[:limit]

    if return_stats:
        stats = calculate_search_stats(entries, top_results)
        return top_results, stats
    return top_results


def main():
    parser = argparse.ArgumentParser(description="Along Unified Knowledge & Memory Retrieval Engine")
    parser.add_argument("query", nargs="?", default="", help="Search query terms or \"quoted phrases\"")
    parser.add_argument("--repo", default=".", help="Target repository root")
    parser.add_argument("--limit", type=int, default=8, help="Maximum results to return")
    parser.add_argument("--category", choices=["all", "kb", "issue", "decision", "milestone", "risk", "spike", "session"], default="all", help="Filter by knowledge category")
    parser.add_argument("--tag", default=None, help="Filter by specific tag")
    parser.add_argument("--any", action="store_true", help="Match ANY query term (OR semantics, default is AND)")
    parser.add_argument("--prefix", action="store_true", help="Match word prefixes in addition to whole words")
    parser.add_argument("-a", "--archive", action="store_true", help="Include archived entities (done issues, session logs, superseded ADRs)")
    parser.add_argument("--stats", action="store_true", help="Show retrieval token efficiency metrics and corpus stats")
    parser.add_argument("--toc", "--catalog", action="store_true", help="Generate compact hierarchical knowledge catalog (< 200 tokens)")
    parser.add_argument("-v", "--verbose", "--debug", action="store_true", help="Show verbose collector details and errors")
    args = parser.parse_args()

    if args.toc:
        catalog = generate_knowledge_catalog(repo_root=args.repo)
        print(catalog)
        sys.exit(0)

    if args.stats:
        results, stats = search_knowledge_base(
            args.query,
            repo_root=args.repo,
            limit=args.limit,
            category=args.category,
            filter_tag=args.tag,
            match_any=args.any,
            prefix=args.prefix,
            verbose=args.verbose,
            return_stats=True,
            include_archive=args.archive,
        )
    else:
        results = search_knowledge_base(
            args.query,
            repo_root=args.repo,
            limit=args.limit,
            category=args.category,
            filter_tag=args.tag,
            match_any=args.any,
            prefix=args.prefix,
            verbose=args.verbose,
            return_stats=False,
            include_archive=args.archive,
        )
        stats = None

    print(f"=== Along Unified Knowledge Search: '{args.query}' ({len(results)} matches) ===")
    if stats:
        print(f"   [Stats] Corpus: {stats['corpus_entries']} entries (~{stats['corpus_tokens_est']} tokens). "
              f"Returned: {len(results)} matches (~{stats['returned_tokens_est']} tokens). "
              f"Token savings: {stats['savings_pct']}%\n")

    for i, r in enumerate(results, 1):
        sec_disp = f" > {r['section']}" if r.get("section") else ""
        print(f"{i}. [{r['category_label']}] [{r['status']}] {r['title']}{sec_disp} (./{r['file_path']})")
        print(f"   \"{r['snippet']}\"\n")


if __name__ == "__main__":
    main()
