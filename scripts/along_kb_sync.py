#!/usr/bin/env python3
# along_kb_sync.py - Idempotent LLM-Wiki Knowledge Base synchronization, link rewriting, and link integrity gate.

import os
import re
import sys
import shutil
import hashlib
import argparse
from datetime import datetime
from typing import Optional, List, Dict, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap

# This engine reads entity front-matter, so it needs ruamel.yaml. Resolve it before
# anything imports it: an engine invoked as `python <path>/<engine>.py` may start
# under an interpreter that has no dependencies prepared, which is exactly how the
# installers and the documented skill commands invoke it.
bootstrap.ensure_deps()

from alongkit import frontmatter, markdown, proc, repo, textio
from alongkit.version import CURRENT_PROTOCOL_VERSION


def compute_content_hash(text: str) -> str:
    """Computes deterministic SHA-256 hash of text normalized to LF line endings."""
    normalized = text.replace("\r\n", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


STANDARD_ARTICLES = [
    ("topic--architecture.md", "System Architecture & Flow", "architecture", ["architecture", "boundaries", "providers", "mcp", "dashboard"]),
    ("topic--domain-model.md", "Domain Model & Entity Ecosystem", "domain-model", ["domain-model", "entities", "schemas", "dag", "metadata"]),
    ("topic--setup-and-workflow.md", "Setup, Installation & Agent Workflows", "setup-workflow", ["setup", "workflow", "installation", "lifecycle", "quality-gates"]),
]

LEGACY_FILE_MAPPING = {
    "01-architecture.md": "topic--architecture.md",
    "02-domain-model.md": "topic--domain-model.md",
    "03-setup-and-workflow.md": "topic--setup-and-workflow.md",
    "04-frontend-frameworks.md": "topic--frontend-frameworks.md",
    "dependencies.md": "topic--dependencies.md",
    "MIGRATIONS.md": "topic--migrations.md",
}

#: Configured legacy KB storage directory roots (REQ-1).
LEGACY_KB_ROOTS = (
    (".along", "KB"),
    (".agents", "KB"),
    ("along", "KB"),
    ("agents", "KB"),
)


def matches_legacy_kb_root(path_str: str) -> bool:
    """Exact path-segment matching against configured legacy KB storage roots (REQ-1)."""
    norm = path_str.replace("\\", "/")
    segments = [s for s in norm.split("/") if s and s != "."]
    for i in range(len(segments)):
        for root_tuple in LEGACY_KB_ROOTS:
            if segments[i : i + len(root_tuple)] == list(root_tuple):
                return True
    return False

# One definition, shared with every other engine and gate.
IGNORED_DIRS = set(repo.IGNORED_DIRS) | set(repo.PROVIDER_DIRS)

ILLUSTRATIVE_PLACEHOLDERS = {
    './target.md', 'target.md', './topic--<slug>.md', './topic--<name>.md'
}

# One tolerant reader, shared: a malformed entity is reported, never silently
# reinterpreted. Engines that write use frontmatter.update, which refuses.
parse_frontmatter = frontmatter.parse_tolerant


def dump_frontmatter(fm, body):
    """Render a NEW article. On an existing file use frontmatter.update instead, which
    preserves comments, key order, and line endings.
    """
    fields = {'protocol': 'along',
              'protocol_version': fm.get('protocol_version', frontmatter.quoted(CURRENT_PROTOCOL_VERSION))}
    fields.update({k: v for k, v in fm.items()
                   if k not in ('protocol', 'protocol_version')})
    return frontmatter.render(fields, body)


def is_along_wiki_article(content):
    """Checks if a file is already a compiled Along Wiki article (has protocol: along)."""
    fm, _ = parse_frontmatter(content)
    return fm.get("protocol") == "along"

def reconcile_sources(repo_root, docs_dir, dry_run=False):
    """
    Inspects allowed source locations: docs/, wiki/, kb/, and legacy .along/KB/, .agents/KB/.
    - If file is already a compiled Wiki article (protocol: along): standardizes topic-- naming in docs/.
    - If file is an external raw note in wiki/ or kb/: synthesizes a topic article in docs/ with provenance sources, preserving raw note in-place.
    - If file is a raw note in docs/: normalizes it in-place to topic--<name>.md with front-matter.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    normalized = 0

    if not dry_run:
        os.makedirs(docs_dir, exist_ok=True)

    # 1. Ingest external source directories: wiki/, kb/, .along/KB/, .agents/KB/
    external_sources = [
        os.path.join(repo_root, "wiki"),
        os.path.join(repo_root, "kb"),
        os.path.join(repo_root, ".along", "KB"),
        os.path.join(repo_root, ".agents", "KB"),
    ]

    for src_dir in external_sources:
        if not os.path.exists(src_dir):
            continue
        for item in list(os.listdir(src_dir)):
            if item == "INDEX.md" or not item.endswith(".md"):
                continue
            s_path = os.path.join(src_dir, item)
            if not os.path.isfile(s_path):
                continue
            with open(s_path, "r", encoding="utf-8", errors="replace") as fp:
                raw = fp.read()

            target_name = LEGACY_FILE_MAPPING.get(item, item)
            if not target_name.startswith("topic--"):
                target_name = f"topic--{target_name}"
            d_path = os.path.join(docs_dir, target_name)

            if is_along_wiki_article(raw):
                # Already a compiled wiki article -> move directly to docs/
                if not dry_run:
                    fields, _ = parse_frontmatter(raw, path=s_path)
                    slug = target_name.replace(".md", "")
                    updates = {"slug": slug}
                    if not fields.get("protocol_version"):
                        updates["protocol_version"] = frontmatter.quoted(CURRENT_PROTOCOL_VERSION)
                    textio.write_text(d_path, frontmatter.update(
                        raw, updates, path=s_path,
                        place_after={"protocol_version": "protocol"}))
                print(f"   Migrated article: {src_dir}/{item} -> docs/{target_name}")
                normalized += 1
            else:
                # External raw note -> synthesize topic article in docs/ with provenance sources, WITHOUT .archive/
                if os.path.exists(d_path):
                    # Existing compiled article must not be overwritten by raw note (preserves hand edits)
                    continue
                if not dry_run:
                    h1_m = re.search(r"^#\s+(.*)$", raw, re.MULTILINE)
                    title = h1_m.group(1).strip() if h1_m else item.replace(".md", "").replace("-", " ").title()
                    slug = target_name.replace(".md", "")
                    rel_src = os.path.relpath(s_path, repo_root).replace(chr(92), "/")
                    content_hash = compute_content_hash(raw)
                    fm = {
                        "protocol": "along",
                        "protocol_version": frontmatter.quoted(CURRENT_PROTOCOL_VERSION),
                        "slug": slug,
                        "title": title,
                        "type": "topic",
                        "curated": True,
                        "sources": [{"path": rel_src, "hash": content_hash}],
                        "created": today,
                        "updated": today,
                        "tags": [slug.replace("topic--", "")],
                    }
                    textio.write_text(d_path, dump_frontmatter(fm, raw))
                print(f"   Compiled raw source with provenance: {src_dir}/{item} -> docs/{target_name} (original preserved in-place)")
                normalized += 1

    # 2. Inspect docs/ for raw documents vs compiled articles
    if os.path.exists(docs_dir):
        for item in list(os.listdir(docs_dir)):
            if item == "INDEX.md" or not item.endswith(".md"):
                continue
            f_path = os.path.join(docs_dir, item)
            if not os.path.isfile(f_path):
                continue
            with open(f_path, "r", encoding="utf-8", errors="replace") as fp:
                raw = fp.read()

            target_name = LEGACY_FILE_MAPPING.get(item, item)
            if not target_name.startswith("topic--"):
                target_name = f"topic--{target_name}"

            if is_along_wiki_article(raw):
                # It is an Along Wiki article: ensure standardized topic-- filename
                if target_name != item and not dry_run:
                    dst_path = os.path.join(docs_dir, target_name)
                    fields, _ = parse_frontmatter(raw, path=f_path)
                    updates = {"slug": target_name.replace(".md", "")}
                    if not fields.get("protocol_version"):
                        updates["protocol_version"] = frontmatter.quoted(CURRENT_PROTOCOL_VERSION)
                    textio.write_text(dst_path, frontmatter.update(
                        raw, updates, path=f_path,
                        place_after={"protocol_version": "protocol"}))
                    os.remove(f_path)
                    print(f"   Normalized wiki article name: docs/{item} -> docs/{target_name}")
                    normalized += 1
            else:
                # Raw document in docs/ -> normalize in-place with frontmatter, without .archive/
                if not dry_run:
                    h1_m = re.search(r"^#\s+(.*)$", raw, re.MULTILINE)
                    title = h1_m.group(1).strip() if h1_m else item.replace(".md", "").replace("-", " ").title()
                    slug = target_name.replace(".md", "")
                    fm = {
                        "protocol": "along",
                        "protocol_version": frontmatter.quoted(CURRENT_PROTOCOL_VERSION),
                        "slug": slug,
                        "title": title,
                        "type": "topic",
                        "curated": True,
                        "created": today,
                        "updated": today,
                        "tags": [slug.replace("topic--", "")],
                    }
                    dst_path = os.path.join(docs_dir, target_name)
                    with open(dst_path, "w", encoding="utf-8", newline="\n") as fp:
                        fp.write(dump_frontmatter(fm, raw))
                    if target_name != item:
                        os.remove(f_path)
                print(f"   Normalized raw document in-place: docs/{item} -> docs/{target_name}")
                normalized += 1

    return normalized

def bootstrap_docs_if_empty(docs_dir, repo_root, dry_run=False):
    today = datetime.now().strftime("%Y-%m-%d")
    repo_name = os.path.basename(os.path.abspath(repo_root))
    created = 0
    if not dry_run:
        os.makedirs(docs_dir, exist_ok=True)
    for filename, title, art_type, tags in STANDARD_ARTICLES:
        target_path = os.path.join(docs_dir, filename)
        if not os.path.exists(target_path):
            slug = filename.replace(".md", "")
            fm = {
                "protocol": "along",
                "protocol_version": frontmatter.quoted(CURRENT_PROTOCOL_VERSION),
                "slug": slug,
                "title": title,
                "type": art_type,
                "created": today,
                "updated": today,
                "tags": tags,
            }
            body = f"# {title}\n\nCore technical specification and documentation for {repo_name}.\n\n## Overview\nDocument system components and engineering guidelines here.\n"
            full_text = dump_frontmatter(fm, body)
            if not dry_run:
                with open(target_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(full_text)
            print(f"   + Bootstrapped {filename}")
            created += 1
    return created


def _repair_or_drop_anchor(target_abs: str, anchor: str) -> str:
    """Repair numbered ADR anchors (#011) or drop unresolvable ADR fragments (REQ-8)."""
    if not anchor:
        return ""
    clean_anchor = anchor.lstrip("#").strip()
    if not clean_anchor:
        return ""
    if not os.path.isfile(target_abs) or not target_abs.endswith(".md"):
        return anchor

    is_adr_target = (
        os.path.basename(target_abs).upper() in ("DECISIONS.MD", "DECISIONS") or
        "ADR" in os.path.basename(target_abs).upper()
    )

    try:
        with open(target_abs, "r", encoding="utf-8", errors="replace") as tf:
            target_text = tf.read()
        anchors_found = set()
        adr_headings = []
        for line in target_text.splitlines():
            m_h = re.match(r"^#{1,6}\s+(.*)", line.strip())
            if m_h:
                htext = m_h.group(1).strip()
                anchors_found.add(markdown.github_heading_anchor(htext))
                m_adr = re.match(r"^ADR-\d{4}-\d{2}-\d{2}--([a-z0-9-]+)", htext, re.IGNORECASE)
                if m_adr:
                    full_adr_id = htext.split(" - ")[0].strip().lower()
                    anchors_found.add(full_adr_id)
                    anchors_found.add(m_adr.group(1).lower())
                    adr_headings.append(full_adr_id)

        # Check if already valid in headings
        if clean_anchor.lower() in anchors_found:
            return f"#{clean_anchor}"

        # Numbered ADR anchors (#011, #11, etc.)
        if re.match(r"^\d+$", clean_anchor):
            num = int(clean_anchor)
            if adr_headings and 1 <= num <= len(adr_headings):
                return f"#{adr_headings[num - 1]}"
            return ""

        # Stale ADR anchor in DECISIONS.md not found in headings (REQ-8)
        if is_adr_target or adr_headings:
            return ""

        # For regular documents, preserve existing non-numbered anchor
        return anchor
    except (OSError, UnicodeDecodeError, ValueError):
        return anchor


def rewrite_inbound_links(repo_root, dry_run=False, migrate_numbered=False, explicit_mapping=None):
    """
    Recursively scans all Markdown files across the entire repository tree (monorepo packages,
    subprojects, apps, root README.md, docs) and rewrites inbound links pointing to legacy
    storage locations (.along/KB/, .agents/KB/, or legacy article names)
    to standard canonical paths in docs/.
    Recursively scans Markdown files across the repository and rewrites:
    - Legacy KB paths (.along/KB/ or .agents/KB/) to docs/topic--*.md
    - Obsolete file:// and file:/// pseudo-schemes to standard relative links (REQ-2, REQ-3)
    - Stale or numbered ADR anchors (#011) to slug headers or drops them (REQ-8)
    - Unrelated numbered links are preserved unless migrate_numbered is True
    - Skips links inside fenced code blocks
    - Preserves exact link text, punctuation, and capitalization
    - Skips rewriting if the computed destination file does not exist on disk (REQ-3)
    """
    repo_root = os.path.abspath(repo_root)
    root_docs_dir = os.path.join(repo_root, "docs")
    rewritten_files = 0
    total_rewrites = 0

    active_mapping = dict(LEGACY_FILE_MAPPING)
    if explicit_mapping:
        active_mapping.update(explicit_mapping)

    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for f in files:
            if not f.endswith(".md"):
                continue
            fpath = os.path.join(root, f)
            file_dir = os.path.dirname(fpath)

            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as fp:
                    content = fp.read()
            except (OSError, UnicodeDecodeError):
                continue

            file_rewrites = 0

            def transform(link: markdown.Link) -> Optional[str]:
                nonlocal file_rewrites
                target = link.target.strip()
                if not target or target.startswith("#") or target.startswith(("http://", "https://", "mailto:", "ftp://", "ftps://", "data:", "tel:", "//")):
                    return None

                is_file_uri = target.startswith("file://")
                clean_target = target[7:] if is_file_uri else target

                target_base, anchor = (clean_target.split("#", 1)[0], "#" + clean_target.split("#", 1)[1]) if "#" in clean_target else (clean_target, "")
                target_base = target_base.replace('\\', '/')
                orig_filename = os.path.basename(target_base)

                # Check for subproject LICENSE references needing relative path resolution
                if orig_filename.upper() in ("LICENSE", "LICENSE.MD", "LICENSE.TXT"):
                    local_target = os.path.normpath(os.path.join(file_dir, target_base))
                    if not os.path.exists(local_target):
                        root_lic = None
                        for lic_name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "License.txt"):
                            cand = os.path.join(repo_root, lic_name)
                            if os.path.isfile(cand):
                                root_lic = cand
                                break
                        if root_lic:
                            new_rel = repo.safe_relpath(root_lic, file_dir).replace('\\', '/')
                            if not new_rel.startswith('.'):
                                new_rel = f"./{new_rel}"
                            new_target = f"{new_rel}{anchor}"
                            if new_target != target:
                                file_rewrites += 1
                                if dry_run:
                                    rel_disp = repo.safe_relpath(fpath, repo_root).replace('\\', '/')
                                    print(f"   [DRY-RUN] {rel_disp}:{link.line}: [{link.text}]({target}) -> ({new_target})")
                                return new_target
                    return None

                is_legacy = False
                new_filename = None

                has_kb_dir = matches_legacy_kb_root(target_base)

                if has_kb_dir:
                    if orig_filename in ("", "KB", "kb", "INDEX.md", "INDEX"):
                        is_legacy = True
                        new_filename = "INDEX.md"
                    elif orig_filename in active_mapping:
                        is_legacy = True
                        new_filename = active_mapping[orig_filename]
                    elif re.match(r'^\d+[-_]', orig_filename):
                        is_legacy = True
                        clean_name = re.sub(r'^\d+[-_]', '', orig_filename)
                        if not clean_name.endswith('.md'):
                            clean_name += '.md'
                        new_filename = f"topic--{clean_name}"
                    elif orig_filename.endswith('.md') or '.' not in orig_filename:
                        is_legacy = True
                        clean_name = orig_filename if orig_filename.endswith('.md') else f"{orig_filename}.md"
                        new_filename = clean_name if clean_name.startswith("topic--") or clean_name == "INDEX.md" else f"topic--{clean_name}"
                elif orig_filename in active_mapping:
                    is_legacy = True
                    new_filename = active_mapping[orig_filename]
                elif migrate_numbered and re.match(r'^\d{1,3}[-_]', orig_filename) and not re.match(r'^\d{4}-\d{2}-\d{2}', orig_filename):
                    is_legacy = True
                    clean_name = re.sub(r'^\d{1,3}[-_]', '', orig_filename)
                    if not clean_name.endswith('.md'):
                        clean_name += '.md'
                    new_filename = f"topic--{clean_name}"

                # Case A: Legacy KB reference that maps to docs/
                if is_legacy and new_filename:
                    target_docs = root_docs_dir
                    sub_docs = os.path.join(file_dir, "docs")
                    if os.path.exists(os.path.join(sub_docs, new_filename)):
                        target_docs = sub_docs
                    target_abs = os.path.join(target_docs, new_filename)

                    # REQ-3: Never rewrite a legacy link unless the computed target exists on disk.
                    if not os.path.isfile(target_abs):
                        rel_f = repo.safe_relpath(fpath, repo_root).replace('\\', '/')
                        rel_t = repo.safe_relpath(target_abs, repo_root).replace('\\', '/')
                        print(f"   [WARN] Legacy target does not exist on disk: {rel_t} (referenced in {rel_f}:{link.line} -> '{target}'). Link left untouched.")
                        return None

                    repaired_anchor = _repair_or_drop_anchor(target_abs, anchor)
                    try:
                        new_rel = os.path.relpath(target_abs, file_dir).replace('\\', '/')
                    except ValueError:
                        new_rel = target_base

                    if not new_rel.startswith('.') and not new_rel.startswith('/'):
                        new_rel = f"./{new_rel}"

                    new_target = f"{new_rel}{repaired_anchor}"
                    if new_target != target:
                        file_rewrites += 1
                        if dry_run:
                            rel_disp = repo.safe_relpath(fpath, repo_root).replace('\\', '/')
                            print(f"   [DRY-RUN] {rel_disp}:{link.line}: [{link.text}]({target}) -> ({new_target})")
                        return new_target
                    return None

                # Case B: file:// pseudo-scheme link (REQ-2, REQ-3)
                if is_file_uri:
                    raw_target = clean_target.split("#", 1)[0].strip().replace('\\', '/')
                    p = raw_target.lstrip("/")
                    if len(p) > 2 and p[1] == ':':
                        cand = os.path.normpath(p)
                    else:
                        cand = os.path.normpath(os.path.join(repo_root, p))

                    # Check if target is an issue moved between ISSUES/ and ISSUES/done/
                    if not os.path.exists(cand):
                        p_dir, f_name = os.path.split(cand)
                        if os.path.basename(p_dir) == "ISSUES":
                            done_cand = os.path.join(p_dir, "done", f_name)
                            if os.path.exists(done_cand):
                                cand = done_cand
                        elif os.path.basename(p_dir) == "done" and os.path.basename(os.path.dirname(p_dir)) == "ISSUES":
                            open_cand = os.path.join(os.path.dirname(p_dir), f_name)
                            if os.path.exists(open_cand):
                                cand = open_cand

                    target_abs = cand
                    repaired_anchor = _repair_or_drop_anchor(target_abs, anchor)
                    try:
                        new_rel = os.path.relpath(target_abs, file_dir).replace('\\', '/')
                    except ValueError:
                        new_rel = raw_target

                    if not new_rel.startswith('.') and not new_rel.startswith('/'):
                        new_rel = f"./{new_rel}"

                    new_target = f"{new_rel}{repaired_anchor}"
                    if new_target != target:
                        file_rewrites += 1
                        if dry_run:
                            rel_disp = repo.safe_relpath(fpath, repo_root).replace('\\', '/')
                            print(f"   [DRY-RUN] {rel_disp}:{link.line}: [{link.text}]({target}) -> ({new_target})")
                        return new_target
                    return None

                # Case C: Relative link with stale or numbered anchor repair (REQ-8)
                if anchor:
                    target_abs = os.path.normpath(os.path.join(file_dir, target_base))
                    if os.path.isfile(target_abs):
                        repaired_anchor = _repair_or_drop_anchor(target_abs, anchor)
                        if repaired_anchor != anchor:
                            new_target = f"{target_base}{repaired_anchor}"
                            if new_target != target:
                                file_rewrites += 1
                                if dry_run:
                                    rel_disp = repo.safe_relpath(fpath, repo_root).replace('\\', '/')
                                    print(f"   [DRY-RUN] {rel_disp}:{link.line}: [{link.text}]({target}) -> ({new_target})")
                                return new_target

                return None

            new_content, _ = markdown.rewrite_links(content, transform)

            if file_rewrites > 0:
                if not dry_run:
                    with open(fpath, "w", encoding="utf-8", newline="\n") as fp:
                        fp.write(new_content)
                rel_disp = repo.safe_relpath(fpath, repo_root).replace('\\', '/')
                action_tag = "[DRY-RUN]" if dry_run else "[REWRITE]"
                print(f"   {action_tag} {rel_disp}: updated {file_rewrites} link(s).")
                rewritten_files += 1
                total_rewrites += file_rewrites

    return rewritten_files, total_rewrites

class LinkIntegrityResult(tuple):
    """Backwards-compatible 2-tuple (broken_links, total_checked) with extra attributes."""
    broken_links: list
    total_checked: int
    entry_point_violations: list
    legacy_kb_references: list

    def __new__(cls, broken_links, total_checked, entry_point_violations=None, legacy_kb_references=None):
        inst = super().__new__(cls, (broken_links, total_checked))
        inst.broken_links = broken_links
        inst.total_checked = total_checked
        inst.entry_point_violations = entry_point_violations or []
        inst.legacy_kb_references = legacy_kb_references or []
        return inst


class LinkIntegrityTriple(tuple):
    """Backwards-compatible 3-tuple (broken_links, total_checked, entry_point_violations) with legacy_kb_references."""
    broken_links: list
    total_checked: int
    entry_point_violations: list
    legacy_kb_references: list

    def __new__(cls, broken_links, total_checked, entry_point_violations, legacy_kb_references=None):
        inst = super().__new__(cls, (broken_links, total_checked, entry_point_violations))
        inst.broken_links = broken_links
        inst.total_checked = total_checked
        inst.entry_point_violations = entry_point_violations
        inst.legacy_kb_references = legacy_kb_references or []
        return inst


def validate_repo_link_integrity(repo_root, return_violations=False):
    """
    Recursively scans all Markdown files across the repository tree and verifies that every
    relative link [text](target) physically resolves to an existing file on disk.
    Also validates the Stable Entry Point Rule: relative links in files outside .along/
    must not target internal .along/ service files directly.
    """
    repo_root = os.path.abspath(repo_root)
    broken_links = []
    entry_point_violations = []
    legacy_kb_references = []
    total_checked = 0

    link_pattern = re.compile(r"\[([^\]]+)\]\(([^\)]+)\)")

    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for f in files:
            if not f.endswith(".md"):
                continue
            fpath = os.path.join(root, f)
            file_dir = os.path.dirname(fpath)
            rel_file = repo.safe_relpath(fpath, repo_root).replace('\\', '/')

            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as fp:
                    lines = fp.readlines()
            except (OSError, UnicodeDecodeError):
                continue

            in_code_fence = False
            for line_idx, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("```") or stripped.startswith("~~~"):
                    in_code_fence = not in_code_fence
                    continue
                if in_code_fence:
                    continue

                for match in link_pattern.finditer(line):
                    link_text = match.group(1)
                    target = match.group(2).strip()

                    # Ignore web URLs, emails, anchors, data URIs
                    if (target.startswith("http://") or target.startswith("https://") or
                        target.startswith("mailto:") or target.startswith("ftp://") or
                        target.startswith("data:") or target.startswith("#")):
                        continue

                    # Ignore template variables and illustrative placeholders (e.g. <slug>, {{var}}, target.md)
                    if markdown.is_placeholder(target) or target in ILLUSTRATIVE_PLACEHOLDERS:
                        continue

                    clean_target = target
                    target_base = clean_target.split("#")[0].strip()
                    if not target_base:
                        continue

                    total_checked += 1

                    if target_base.startswith("file://"):
                        broken_links.append({
                            "file": rel_file,
                            "line": line_idx,
                            "text": link_text,
                            "target": target,
                            "resolved": None,
                            "reason": "file:// pseudo-scheme forbidden (use standard relative links)",
                        })
                        continue

                    try:
                        resolved_path = os.path.normpath(os.path.join(file_dir, target_base))

                        is_legacy_ref = (
                            os.path.normpath(resolved_path).startswith(os.path.normpath(os.path.join(repo_root, ".along", "KB"))) or
                            os.path.normpath(resolved_path).startswith(os.path.normpath(os.path.join(repo_root, ".agents", "KB"))) or
                            any(p in target for p in [".along/KB", ".agents/KB", "along/KB", "agents/KB"])
                        )
                        if is_legacy_ref:
                            legacy_kb_references.append({
                                "file": rel_file,
                                "line": line_idx,
                                "text": link_text,
                                "target": target,
                                "resolved": resolved_path,
                            })

                        if not os.path.exists(resolved_path):
                            broken_links.append({
                                "file": rel_file,
                                "line": line_idx,
                                "text": link_text,
                                "target": target,
                                "resolved": resolved_path,
                            })
                        else:
                            # Enforce Stable Entry Point Rule (REQ-7):
                            # Inbound links from outside .along/ into .along/ are violations
                            is_file_outside = not rel_file.startswith(".along/") and rel_file != ".along"
                            rel_resolved = repo.safe_relpath(resolved_path, repo_root).replace('\\', '/')
                            is_target_inside = rel_resolved.startswith(".along/") or rel_resolved == ".along"
                            if is_file_outside and is_target_inside:
                                entry_point_violations.append({
                                    "file": rel_file,
                                    "line": line_idx,
                                    "text": link_text,
                                    "target": target,
                                    "resolved": rel_resolved,
                                    "canonical_alternative": "docs/INDEX.md",
                                    })
                    except (OSError, ValueError):
                        if any(p in target for p in [".along/KB", ".agents/KB", "along/KB", "agents/KB"]):
                            legacy_kb_references.append({
                                "file": rel_file,
                                "line": line_idx,
                                "text": link_text,
                                "target": target,
                                "resolved": "invalid_path",
                            })
                        broken_links.append({
                            "file": rel_file,
                            "line": line_idx,
                            "text": link_text,
                            "target": target,
                            "resolved": "invalid_path",
                        })

    if return_violations:
        return LinkIntegrityTriple(broken_links, total_checked, entry_point_violations, legacy_kb_references)
    return LinkIntegrityResult(broken_links, total_checked, entry_point_violations, legacy_kb_references)



def has_real_body(body: str) -> bool:
    """Return True only if the body contains real content beyond a bare H1 or empty stub."""
    stripped = body.strip()
    if not stripped:
        return False
    lines = [l.strip() for l in stripped.splitlines() if l.strip()]
    return len(lines) > 1


def _extract_project_meta(target_dir: str):
    """Extract project title and summary from README.md or directory name.

    Extracts title from the first H1 header, and summary from the first valid
    blockquote or prose paragraph following H1, ignoring HTML comments,
    badges, and GitHub alert callouts (> [!NOTE], > [!WARNING], etc.).
    """
    repo_name = os.path.basename(os.path.abspath(target_dir))
    title = repo_name
    summary = f"> Knowledge Base and documentation index for {repo_name}."

    readme_path = os.path.join(target_dir, "README.md")
    if os.path.isfile(readme_path):
        try:
            readme_text = textio.read_text(readme_path)
            h1_m = re.search(r"^#\s+(.+)$", readme_text, re.MULTILINE)
            if h1_m:
                title = h1_m.group(1).strip()
                candidate_text = readme_text[h1_m.end():]
            else:
                candidate_text = readme_text

            blocks = re.split(r"\n\s*\n", candidate_text)
            for block in blocks:
                stripped = block.strip()
                if not stripped:
                    continue

                # Strip HTML comments
                stripped_no_comment = re.sub(r"<!--.*?-->", "", stripped, flags=re.DOTALL).strip()
                if not stripped_no_comment:
                    continue

                # Skip GitHub alert callouts (e.g. > [!NOTE], > [!WARNING], > [!TIP], etc.)
                if re.match(r"^>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]", stripped_no_comment, re.IGNORECASE):
                    continue

                # Skip badge-only blocks and raw HTML containers without text
                no_badges = re.sub(r"\[!\[.*?\]\(.*?\)\](\(.*?\))?", "", stripped_no_comment)
                no_badges = re.sub(r"!\[.*?\]\(.*?\)", "", no_badges)
                no_badges = re.sub(r"\[.*?\]\(.*?\)", "", no_badges)
                no_badges = re.sub(r"<[^>]+>", "", no_badges)
                if not re.search(r"\w{2,}", no_badges):
                    continue

                lines = [l.strip() for l in stripped_no_comment.splitlines() if l.strip()]
                if not lines:
                    continue

                # Check for blockquote (> ...)
                if lines[0].startswith(">"):
                    quote_lines = [re.sub(r"^>\s*", "", l).strip() for l in lines]
                    clean_quote = " ".join(l for l in quote_lines if l)
                    clean_quote = re.sub(r"<[^>]+>", "", clean_quote).strip()
                    clean_quote = " ".join(clean_quote.split())
                    if clean_quote:
                        summary = f"> {clean_quote}"
                        break

                # Check for prose paragraph (not a heading, list, table, fence, or rule)
                first_line = lines[0]
                if not re.match(r"^(#|[-*+]\s|\d+\.\s|\||```|~~~|---|===|\*\*\*)", first_line):
                    para = " ".join(lines)
                    clean_para = re.sub(r"<[^>]+>", "", para).strip()
                    clean_para = " ".join(clean_para.split())
                    if clean_para:
                        summary = f"> {clean_para}"
                        break
        except (OSError, UnicodeDecodeError):
            pass

    return title, summary


def sync_llms_txt(target_dir, articles, dry_run=False):
    """
    Non-destructively synchronizes llms.txt across resolved target locations (.well-known/ and/or root).
    Preserves all custom sections, titles, summaries, and external links.
    Updates or inserts the ## Documentation Links section to reflect active docs/topic--*.md articles.
    """
    targets = repo.resolve_llm_targets(target_dir, "llms.txt")
    title, default_summary = _extract_project_meta(target_dir)

    doc_links_header = "## Documentation Links"
    doc_links = [doc_links_header]
    if os.path.isfile(os.path.join(target_dir, "README.md")):
        doc_links.append("- [README.md](README.md): Overview, quick installation, and full skill list.")
    if os.path.isfile(os.path.join(target_dir, "AGENTS.md")):
        doc_links.append("- [AGENTS.md](AGENTS.md): Active ALONG-PROTOCOL conventions and instructions.")
    if os.path.isfile(os.path.join(target_dir, "docs", "INDEX.md")):
        doc_links.append("- [docs/INDEX.md](docs/INDEX.md): Central Knowledge Base topic catalog.")

    for art in articles:
        if art["filename"] == "INDEX.md":
            continue
        clean_title = art["title"].replace("\n", " ").strip()
        doc_links.append(f"- [docs/{art['filename']}](docs/{art['filename']}): {clean_title}.")

    doc_links_block = "\n".join(doc_links)

    for target_path in targets:
        existing = ""
        if os.path.isfile(target_path):
            try:
                existing = textio.read_text(target_path)
            except (OSError, UnicodeDecodeError):
                existing = ""

        if existing:
            pattern = r"(## Documentation(?: Links)?\s*\n)(.*?)(?=(\n## |\Z))"
            match = re.search(pattern, existing, re.DOTALL)
            if match:
                custom_external = []
                old_section = match.group(2)
                for line in old_section.splitlines():
                    ls = line.strip()
                    if ls.startswith("- [") and ("http://" in ls or "https://" in ls):
                        custom_external.append(ls)

                if custom_external:
                    replacement_text = doc_links_block + "\n" + "\n".join(custom_external) + "\n"
                else:
                    replacement_text = doc_links_block + "\n"

                new_content = existing[:match.start()] + replacement_text + existing[match.end():]
            else:
                new_content = existing.rstrip() + "\n\n" + doc_links_block + "\n"
        else:
            new_content = f"# {title}\n\n{default_summary}\n\n{doc_links_block}\n"

        if not dry_run:
            if not os.path.isfile(target_path) or new_content != existing:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                textio.write_text(target_path, new_content)
                rel_disp = repo.safe_relpath(target_path, target_dir)
                print(f"   -> Synchronized {rel_disp} ({len(articles)} topic links).")


def sync_llms_full_txt(target_dir, articles, dry_run=False):
    """
    Deterministically compiles llms-full.txt across resolved target locations (.well-known/ and/or root).
    Aggregates README.md, AGENTS.md, and all docs/topic--*.md articles into a single context document.
    """
    targets = repo.resolve_llm_targets(target_dir, "llms-full.txt")
    title, default_summary = _extract_project_meta(target_dir)

    full_parts = [
        f"# {title} - Full Documentation Context",
        "",
        default_summary,
    ]

    readme_path = os.path.join(target_dir, "README.md")
    if os.path.isfile(readme_path):
        try:
            readme_body = textio.read_text(readme_path).strip()
            if readme_body:
                full_parts.extend(["", "---", "", "## Document: README.md (Overview)", "", readme_body])
        except (OSError, UnicodeDecodeError):
            pass

    agents_path = os.path.join(target_dir, "AGENTS.md")
    if os.path.isfile(agents_path):
        try:
            agents_body = textio.read_text(agents_path).strip()
            if agents_body:
                full_parts.extend(["", "---", "", "## Document: AGENTS.md (Agent Conventions & Protocol)", "", agents_body])
        except (OSError, UnicodeDecodeError):
            pass

    docs_dir = os.path.join(target_dir, "docs")
    for art in articles:
        if art["filename"] == "INDEX.md":
            continue
        art_path = os.path.join(docs_dir, art["filename"])
        if not os.path.isfile(art_path):
            continue
        try:
            content = textio.read_text(art_path)
            _, body = parse_frontmatter(content)
            body_clean = body.strip()
            if body_clean:
                clean_title = art["title"].replace("\n", " ").strip()
                full_parts.extend([
                    "", "---", "",
                    f"## Document: docs/{art['filename']} ({clean_title})",
                    "",
                    body_clean,
                ])
        except (OSError, UnicodeDecodeError, ValueError, frontmatter.FrontmatterError):
            pass

    full_content = "\n".join(full_parts).rstrip() + "\n"

    for target_path in targets:
        existing = ""
        if os.path.isfile(target_path):
            try:
                existing = textio.read_text(target_path)
            except (OSError, UnicodeDecodeError):
                existing = ""

        if not dry_run:
            if not os.path.isfile(target_path) or full_content != existing:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                textio.write_text(target_path, full_content)
                rel_disp = repo.safe_relpath(target_path, target_dir)
                print(f"   -> Compiled {rel_disp} ({len(articles)} documents included).")


def sync_kb(repo_root, check_only=False, strict=False, prune_intent=None, is_subproject=False, output_json=False, migrate_numbered=False, explicit_mapping=None):
    repo_root = os.path.abspath(repo_root)
    docs_dir = os.path.join(repo_root, "docs")
    today = datetime.now().strftime("%Y-%m-%d")

    print(f"-> Synchronizing Knowledge Base in {docs_dir}...")
    reconcile_sources(repo_root, docs_dir, dry_run=check_only)

    if not os.path.exists(docs_dir) or not os.listdir(docs_dir):
        print("   docs/ is missing or empty. Bootstrapping standard articles...")
        bootstrapped = bootstrap_docs_if_empty(docs_dir, repo_root, dry_run=check_only)
        print(f"   Bootstrapped {bootstrapped} core Knowledge Base articles.")

    if not os.path.exists(docs_dir):
        if not check_only:
            os.makedirs(docs_dir, exist_ok=True)
        else:
            print("   docs/ does not exist (check-only mode; zero modifications made).")

    articles = []
    doc_cross_links = {}
    orphaned_sources = []
    drifted_sources = []
    shrunk_articles = []

    # Check for git repository to inspect content reduction against HEAD
    in_git = False
    try:
        git_check = proc.run_capture(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_root)
        in_git = git_check.ok and git_check.stdout.strip() == "true"
    except OSError:
        in_git = False

    file_list = sorted(os.listdir(docs_dir)) if os.path.exists(docs_dir) else []
    for f in file_list:
        if not f.endswith(".md") or f == "INDEX.md":
            continue
        file_path = os.path.join(docs_dir, f)
        if not os.path.isfile(file_path):
            continue

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as fp:
                raw_content = fp.read()
            fm, body = parse_frontmatter(raw_content)

            if not has_real_body(body):
                print(f"   [WARN] Skipping stub (empty body): {f}")
                continue

            # Validate sources provenance & drift
            sources = fm.get("sources")
            if sources and isinstance(sources, list):
                for src_item in sources:
                    if isinstance(src_item, dict):
                        src_rel = src_item.get("path")
                        rec_hash = src_item.get("hash")
                    elif isinstance(src_item, str):
                        src_rel = src_item
                        rec_hash = None
                    else:
                        continue
                    if not src_rel:
                        continue
                    src_full = os.path.normpath(os.path.join(repo_root, src_rel))
                    if not os.path.exists(src_full) or not os.path.isfile(src_full):
                        orphaned_sources.append((f, src_rel))
                        print(f"   [ORPHANED SOURCE] docs/{f}: Source '{src_rel}' does not exist on disk.")
                    else:
                        if rec_hash:
                            try:
                                with open(src_full, "r", encoding="utf-8", errors="replace") as s_fp:
                                    src_text = s_fp.read()
                                cur_hash = compute_content_hash(src_text)
                                if cur_hash != rec_hash:
                                    drifted_sources.append((f, src_rel, rec_hash, cur_hash))
                                    print(f"   [DRIFT] docs/{f}: Source '{src_rel}' has changed (expected {rec_hash[:8]}, got {cur_hash[:8]}). Agent review required.")
                            except (OSError, UnicodeDecodeError) as e:
                                print(f"   [WARN] Failed to read source '{src_rel}' for docs/{f}: {e}")

            # Check content reduction against HEAD if in git
            if in_git:
                try:
                    rel_to_repo = os.path.relpath(file_path, repo_root).replace("\\", "/")
                    git_rel = rel_to_repo if rel_to_repo.startswith("./") else f"./{rel_to_repo}"
                    head_res = proc.run_capture(["git", "show", f"HEAD:{git_rel}"], cwd=repo_root)
                    if head_res.ok:
                        head_lines = len(head_res.stdout.splitlines())
                        cur_lines = len(raw_content.splitlines())
                        delta = head_lines - cur_lines
                        if head_lines >= 15 and delta >= 10 and (delta / head_lines) > 0.25:
                            pct = round((delta / head_lines) * 100)
                            shrunk_articles.append((f, delta, pct))
                except (OSError, ValueError):
                    pass

            updates = {}
            slug = fm.get('slug') or f.replace('.md', '')
            # A4: normalize slug - strip accidental topic-- prefix written into front-matter
            if slug.startswith('topic--'):
                clean_slug = slug[len('topic--'):]
                if fm.get('slug') == slug:
                    updates['slug'] = clean_slug
                slug = clean_slug
            title = fm.get('title')
            if not title:
                h1_m = re.search(r'^#\s+(.*)$', body, re.MULTILINE)
                title = (h1_m.group(1).strip() if h1_m
                         else slug.replace('topic--', '').replace('-', ' ').title())
                updates['title'] = title
            if fm.get('protocol') != 'along':
                updates['protocol'] = 'along'
            if str(fm.get('protocol_version', '')).strip() != CURRENT_PROTOCOL_VERSION:
                updates['protocol_version'] = frontmatter.quoted(CURRENT_PROTOCOL_VERSION)
            if not fm.get('slug'):
                updates['slug'] = slug
            if not fm.get('type'):
                updates['type'] = 'topic'
            if not fm.get('created'):
                updates['created'] = today
            if not fm.get('tags'):
                updates['tags'] = [slug.replace('topic--', '')]

            if updates and not check_only:
                updates['updated'] = today
                new_content = frontmatter.update(
                    raw_content, updates, path=file_path,
                    place_after={'protocol_version': 'protocol', 'updated': 'created'})
                if new_content != raw_content:
                    textio.write_text(file_path, new_content)

            rel_links = re.findall(r"\[([^\]]+)\]\(([^\)]+)\)", body)
            doc_cross_links[f] = []
            for link_text, link_target in rel_links:
                if link_target.startswith("http://") or link_target.startswith("https://") or link_target.startswith("#") or link_target.startswith("file://"):
                    continue
                target_no_hash = link_target.split("#")[0]
                if not target_no_hash:
                    continue
                target_full = os.path.normpath(os.path.join(docs_dir, target_no_hash))
                if os.path.exists(target_full):
                    if target_full.startswith(docs_dir) and target_no_hash.endswith(".md"):
                        doc_cross_links[f].append(os.path.basename(target_full))

            articles.append({
                "filename": f,
                "slug": slug,
                "title": title,
                "type": fm.get("type", "topic"),
                "tags": fm.get("tags", []),
                "curated": fm.get("curated", True),
                "sources": sources or [],
            })
        except (OSError, ValueError, frontmatter.FrontmatterError) as e:
            print(f"   [WARN] Failed to process {f}: {e}")

    # Intent Gate: Check if any article shrank significantly without --prune-intent
    if shrunk_articles:
        if not prune_intent:
            print("\n[WARNING] Detected significant content reduction in Knowledge Base:")
            for s_name, s_delta, s_pct in shrunk_articles:
                print(f"   - docs/{s_name}: -{s_delta} lines (-{s_pct}%)")
            print("\nOperation halted to prevent accidental data loss.")
            print("If this deletion was intentional, re-run with:")
            print("   python scripts/along_kb_sync.py --prune-intent [REASON]\n")
            sys.exit(2)
        else:
            print(f"   [PRUNE-INTENT] Acknowledged content reduction: {prune_intent}")

    index_path = os.path.join(docs_dir, "INDEX.md")
    index_fm = {
        "protocol": "along",
        "protocol_version": frontmatter.quoted(CURRENT_PROTOCOL_VERSION),
        "slug": "INDEX",
        "title": "Knowledge Base Topic Index",
        "type": "index",
        "created": today,
        "updated": today,
        "tags": ["index", "kb", "topics", "map"],
    }

    # Build Mermaid Knowledge Graph
    mermaid_lines = [
        "## Knowledge Graph & Topic Map\n",
        "```mermaid",
        "flowchart TD",
        "    INDEX[\"Knowledge Base (INDEX)\"]",
    ]
    
    node_ids = {}
    for i, art in enumerate(articles, 1):
        clean_nid = "T_" + re.sub(r"[^A-Z0-9_]", "_", art['slug'].replace('topic--', '').upper())
        node_ids[art['filename']] = clean_nid
        safe_title = art['title'].replace('"', "'")
        mermaid_lines.append(f'    {clean_nid}["{safe_title}"]')
        mermaid_lines.append(f'    INDEX --> {clean_nid}')

    # A2: deduplicate graph edges - a file may reference another multiple times
    seen_edges: set[tuple[str, str]] = set()
    for f_name, cross_targets in doc_cross_links.items():
        src_id = node_ids.get(f_name)
        if not src_id:
            continue
        for tgt in cross_targets:
            tgt_id = node_ids.get(tgt)
            if tgt_id and tgt_id != src_id:
                edge = (src_id, tgt_id)
                if edge not in seen_edges:
                    seen_edges.add(edge)
                    mermaid_lines.append(f'    {src_id} -.->{"|references|"} {tgt_id}')

    mermaid_lines.append("```\n")
    mermaid_lines.append("---\n")
    mermaid_lines.append("## Articles\n")

    index_body_lines = [
        "# Knowledge Base Topic Index\n",
        "Central entry point and cross-linked topic catalog for project documentation:\n",
        "\n".join(mermaid_lines),
    ]

    for art in articles:
        tags_str = ", ".join(f"`{t}`" for t in art["tags"]) if art["tags"] else ""
        index_body_lines.append(f"- **[{art['title']}](./{art['filename']})** ({art['type']}) {tags_str}")

    index_body_lines.append("\n---\n\n## Related Context\n")
    agents_cand = os.path.join(repo_root, "AGENTS.md")
    if os.path.exists(agents_cand):
        rel_agents = repo.safe_relpath(agents_cand, docs_dir).replace('\\', '/')
        index_body_lines.append(f"- [AGENTS.md]({rel_agents}): Active protocol conventions and rules.")

    decisions_cand = os.path.join(repo_root, ".along", "DECISIONS.md")
    if os.path.exists(decisions_cand):
        rel_decisions = repo.safe_relpath(decisions_cand, docs_dir).replace('\\', '/')
        index_body_lines.append(f"- [.along/DECISIONS.md]({rel_decisions}): Architectural Decision Records.")

    issues_cand = os.path.join(repo_root, ".along", "ISSUES.md")
    if os.path.exists(issues_cand):
        rel_issues = repo.safe_relpath(issues_cand, docs_dir).replace('\\', '/')
        index_body_lines.append(f"- [.along/ISSUES.md]({rel_issues}): Active issue tracking board.")

    history_cand = os.path.join(repo_root, ".along", "HISTORY.md")
    if os.path.exists(history_cand):
        rel_history = repo.safe_relpath(history_cand, docs_dir).replace('\\', '/')
        index_body_lines.append(f"- [.along/HISTORY.md]({rel_history}): Append-only project history log.")

    if not check_only and os.path.exists(docs_dir):
        full_index = dump_frontmatter(index_fm, "\n".join(index_body_lines))
        with open(index_path, "w", encoding="utf-8", newline="\n") as fp:
            fp.write(full_index)
        print(f"   -> Rebuilt docs/INDEX.md ({len(articles)} articles indexed).")

    # Step: Smart non-destructive synchronization of llms.txt and deterministic llms-full.txt
    sync_llms_txt(repo_root, articles, dry_run=check_only)
    sync_llms_full_txt(repo_root, articles, dry_run=check_only)

    # Step: Cascading subproject synchronization for Along contexts
    if not is_subproject:
        all_contexts = repo.find_agent_contexts(repo_root)
        abs_root = os.path.abspath(repo_root)
        for ctx in all_contexts:
            if os.path.abspath(ctx) == abs_root:
                continue
            ctx_docs = os.path.join(ctx, "docs")
            has_docs = os.path.isdir(ctx_docs)
            has_llms = (
                os.path.isfile(os.path.join(ctx, "llms.txt")) or
                os.path.isfile(os.path.join(ctx, ".well-known", "llms.txt"))
            )
            if has_docs or has_llms:
                rel_ctx = repo.safe_relpath(ctx, repo_root)
                print(f"-> Cascading Knowledge Base sync to subproject: {rel_ctx}")
                sync_kb(ctx, check_only=check_only, strict=strict, prune_intent=prune_intent,
                        is_subproject=True, migrate_numbered=migrate_numbered,
                        explicit_mapping=explicit_mapping)

    rewritten_files = 0
    total_rewrites = 0
    if not is_subproject:
        # Step: Inbound Link Rewriting across the entire repository
        print("-> Scanning repository for inbound legacy links (Link Rewriting Engine)...")
        rewritten_files, total_rewrites = rewrite_inbound_links(
            repo_root, dry_run=check_only, migrate_numbered=migrate_numbered,
            explicit_mapping=explicit_mapping
        )
        if total_rewrites > 0:
            verb = "Would rewrite" if check_only else "Rewrote"
            print(f"   [OK] {verb} {total_rewrites} legacy link(s) across {rewritten_files} file(s).")
        else:
            print("   [OK] Inbound links are clean and up to date.")

    # Step: Repository-wide Link Integrity Gate (runs BEFORE legacy directory deletion, REQ-5)
    print("-> Executing Global Link Integrity Gate across all repository Markdown files...")
    integrity_res = validate_repo_link_integrity(repo_root, return_violations=True)
    broken_links, total_checked, entry_point_violations = integrity_res
    legacy_kb_references = getattr(integrity_res, "legacy_kb_references", [])

    # Step: Safe legacy directory cleanup (REQ-5)
    # The rewrite pass must complete and be verified before any legacy directory deletion,
    # and deletion must be skipped if unresolved references to that directory remain.
    if not is_subproject and not check_only:
        legacy_dirs = [os.path.join(repo_root, ".along", "KB"), os.path.join(repo_root, ".agents", "KB")]
        for old_kb in legacy_dirs:
            if os.path.exists(old_kb):
                old_kb_norm = os.path.normpath(old_kb)
                has_unresolved_refs = any(
                    (isinstance(ref, dict) and (
                        os.path.normpath(ref.get("resolved", "")).startswith(old_kb_norm) or
                        any(p in ref.get("target", "") for p in [".along/KB", ".agents/KB", "along/KB", "agents/KB"])
                    ))
                    for ref in (legacy_kb_references + [bl for bl in broken_links if isinstance(bl, dict)])
                )
                if has_unresolved_refs:
                    print(f"   [WARN] Legacy directory deletion blocked: unresolved references to {repo.safe_relpath(old_kb, repo_root)} remain.")
                else:
                    shutil.rmtree(old_kb, ignore_errors=True)

    if broken_links:
        print(f"   [WARN] Link Integrity Gate detected {len(broken_links)} broken relative link(s) (checked {total_checked}):")
        for bl in broken_links:
            print(f"      - {bl['file']}:{bl['line']} -> [{bl['text']}]({bl['target']}) (target missing on disk)")
    else:
        print(f"   [OK] All {total_checked} relative Markdown link(s) verified on disk.")

    if entry_point_violations:
        print(f"   [WARN] Stable Entry Point Rule: {len(entry_point_violations)} inbound link(s) from outside .along/ point directly into .along/:")
        for ep in entry_point_violations:
            print(f"      - {ep['file']}:{ep['line']} -> [{ep['text']}]({ep['target']}) (route through canonical {ep['canonical_alternative']} instead)")

    total_articles = len(articles) + (1 if os.path.exists(index_path) else 0)
    print(f"-> Knowledge Base sync complete. Total active articles: {total_articles}\n")

    if output_json:
        import json
        report = {
            "total_checked": total_checked,
            "broken_links": broken_links,
            "entry_point_violations": entry_point_violations,
            "rewritten_files": rewritten_files,
            "total_rewrites": total_rewrites,
            "articles_count": total_articles,
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))

    if strict and broken_links:
        print("   [FAIL] Link Integrity Gate failed in strict mode.")
        sys.exit(1)

    return total_articles, len(broken_links)

def main():
    parser = argparse.ArgumentParser(description="Along Knowledge Base Compiler, Link Rewriter & Integrity Gate")
    parser.add_argument("repo_root", nargs="?", default=".", help="Target repository root directory")
    parser.add_argument("--check", action="store_true", help="Check links and structure without modifying files")
    parser.add_argument("--dry-run", action="store_true", help="List intended link rewrites without modifying files")
    parser.add_argument("--migrate-numbered", action="store_true", help="Migrate numbered documentation links (e.g. 01-intro.md) to topic--intro.md")
    parser.add_argument("--strict", action="store_true", help="Fail with non-zero exit code if broken links are found")
    parser.add_argument("--json", action="store_true", help="Output report in JSON format")
    parser.add_argument("--prune-intent", dest="prune_intent", nargs="?", const="Intentional content pruning", default=None, help="Acknowledge and allow content reduction with an optional intent rationale")
    parser.add_argument("--allow-shrink", dest="prune_intent", action="store_const", const="Allow shrink", help="Alias for --prune-intent")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--debug", action="store_true", help="Debug output with full tracebacks")
    args = parser.parse_args()

    check_mode = args.check or args.dry_run
    sync_kb(args.repo_root, check_only=check_mode, strict=args.strict, prune_intent=args.prune_intent,
            output_json=args.json, migrate_numbered=args.migrate_numbered)

if __name__ == "__main__":
    main()
