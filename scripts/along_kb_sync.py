#!/usr/bin/env python3
# along_kb_sync.py - Idempotent LLM-Wiki Knowledge Base synchronization, link rewriting, and link integrity gate.

import os
import re
import sys
import shutil
import hashlib
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap

# This engine reads entity front-matter, so it needs ruamel.yaml. Resolve it before
# anything imports it: an engine invoked as `python <path>/<engine>.py` may start
# under an interpreter that has no dependencies prepared, which is exactly how the
# installers and the documented skill commands invoke it.
bootstrap.ensure_deps()

from alongkit import frontmatter, markdown, repo, textio
from alongkit import proc, frontmatter, markdown, repo, textio
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

# One definition, shared with every other engine and gate.
IGNORED_DIRS = set(repo.IGNORED_DIRS) | set(repo.PROVIDER_DIRS)

ILLUSTRATIVE_PLACEHOLDERS = {
    './target.md', 'target.md', './topic--<slug>.md', './topic--<name>.md',
    './topic--architecture.md', './topic--setup-and-workflow.md'
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
                    with open(d_path, "w", encoding="utf-8") as fp:
                        fp.write(dump_frontmatter(fm, raw))
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
                    with open(dst_path, "w", encoding="utf-8") as fp:
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
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(full_text)
            print(f"   + Bootstrapped {filename}")
            created += 1
    return created

def rewrite_inbound_links(repo_root, dry_run=False):
    """
    Recursively scans all Markdown files across the entire repository tree (monorepo packages,
    subprojects, apps, root README.md, docs) and rewrites inbound links pointing to legacy
    storage locations (.along/KB/, .agents/KB/, wiki/, kb/, or legacy article names)
    to standard canonical paths in docs/.
    """
    repo_root = os.path.abspath(repo_root)
    root_docs_dir = os.path.join(repo_root, "docs")
    rewritten_files = 0
    total_rewrites = 0

    link_pattern = re.compile(r"(\[([^\]]+)\]\()([^\)]+)(\))")

    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith('.')]
        for f in files:
            if not f.endswith(".md"):
                continue
            fpath = os.path.join(root, f)
            file_dir = os.path.dirname(fpath)

            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as fp:
                    content = fp.read()
            except Exception:
                continue

            file_rewrites = 0

            def replace_link(match):
                nonlocal file_rewrites
                prefix = match.group(1)
                link_text = match.group(2)
                target = match.group(3).strip()
                suffix = match.group(4)

                if (target.startswith("http://") or target.startswith("https://") or
                    target.startswith("mailto:") or target.startswith("#") or target.startswith("data:")):
                    return match.group(0)

                is_file_uri = target.startswith("file://")
                clean_target = target[7:] if is_file_uri else target

                target_base, anchor = (clean_target.split("#", 1)[0], "#" + clean_target.split("#", 1)[1]) if "#" in clean_target else (clean_target, "")
                target_base = target_base.replace('\\', '/')

                is_legacy = False
                orig_filename = os.path.basename(target_base)

                # 1. Path contains legacy Knowledge Base directories
                has_kb_dir = any(k in target_base for k in [".along/KB", ".agents/KB", "/KB", "along/KB", "agents/KB", "/kb", "/wiki", "kb/", "wiki/"])
                
                if has_kb_dir:
                    is_legacy = True
                    if orig_filename in ("", "KB", "kb", "wiki", "INDEX.md", "INDEX"):
                        new_filename = "INDEX.md"
                    elif orig_filename in LEGACY_FILE_MAPPING:
                        new_filename = LEGACY_FILE_MAPPING[orig_filename]
                    elif re.match(r'^\d+[-_]', orig_filename):
                        clean_name = re.sub(r'^\d+[-_]', '', orig_filename)
                        if not clean_name.endswith('.md'):
                            clean_name += '.md'
                        new_filename = f"topic--{clean_name}"
                    else:
                        clean_name = orig_filename if orig_filename.endswith('.md') else f"{orig_filename}.md"
                        new_filename = clean_name if clean_name.startswith("topic--") or clean_name == "INDEX.md" else f"topic--{clean_name}"
                elif orig_filename in LEGACY_FILE_MAPPING:
                    is_legacy = True
                    new_filename = LEGACY_FILE_MAPPING[orig_filename]
                elif re.match(r'^\d{1,3}[-_]', orig_filename) and not re.match(r'^\d{4}-\d{2}-\d{2}', orig_filename):
                    # Legacy numbered filename (e.g. docs/01-architecture.md or ./01-overview.md)
                    is_legacy = True
                    clean_name = re.sub(r'^\d{1,3}[-_]', '', orig_filename)
                    if not clean_name.endswith('.md'):
                        clean_name += '.md'
                    new_filename = f"topic--{clean_name}"

                if not is_legacy:
                    return match.group(0)

                # Determine target docs directory (nearest subproject docs if present, else root docs)
                target_docs = root_docs_dir
                if os.path.exists(os.path.join(file_dir, "docs", new_filename)):
                    target_docs = os.path.join(file_dir, "docs")

                target_abs = os.path.join(target_docs, new_filename)
                try:
                    new_rel = os.path.relpath(target_abs, file_dir).replace('\\', '/')
                except Exception:
                    new_rel = target_base

                if not new_rel.startswith('.') and not new_rel.startswith('/'):
                    new_rel = f"./{new_rel}"

                new_target = f"{new_rel}{anchor}"
                if is_file_uri and target.startswith("file://."):
                    new_target = f"file://{new_rel.lstrip('./')}{anchor}"

                if new_target != target:
                    file_rewrites += 1
                    return f"{prefix}{new_target}{suffix}"
                return match.group(0)

            lines = content.splitlines(keepends=True)
            new_lines = []
            in_code_fence = False
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("```") or stripped.startswith("~~~"):
                    in_code_fence = not in_code_fence
                    new_lines.append(line)
                    continue
                if in_code_fence:
                    new_lines.append(line)
                    continue
                new_lines.append(link_pattern.sub(replace_link, line))

            new_content = "".join(new_lines)
            if file_rewrites > 0:
                if not dry_run:
                    with open(fpath, "w", encoding="utf-8") as fp:
                        fp.write(new_content)
                rel_disp = os.path.relpath(fpath, repo_root).replace('\\', '/')
                print(f"   [REWRITE] {rel_disp}: updated {file_rewrites} legacy KB link(s).")
                rewritten_files += 1
                total_rewrites += file_rewrites

    return rewritten_files, total_rewrites

def validate_repo_link_integrity(repo_root):
    """
    Recursively scans all Markdown files across the repository tree and verifies that every
    relative link [text](target) physically resolves to an existing file on disk.
    """
    repo_root = os.path.abspath(repo_root)
    broken_links = []
    total_checked = 0

    link_pattern = re.compile(r"\[([^\]]+)\]\(([^\)]+)\)")

    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith('.')]
        for f in files:
            if not f.endswith(".md"):
                continue
            fpath = os.path.join(root, f)
            file_dir = os.path.dirname(fpath)
            rel_file = os.path.relpath(fpath, repo_root).replace('\\', '/')

            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as fp:
                    lines = fp.readlines()
            except Exception:
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

                    # Ignore template variables and illustrative placeholders
                    if target.startswith("{{") or target.startswith("<") or "<" in target or ">" in target:
                        continue
                    if target in ILLUSTRATIVE_PLACEHOLDERS:
                        continue

                    clean_target = target
                    target_base = clean_target.split("#")[0].strip()
                    if not target_base:
                        continue

                    total_checked += 1

                    try:
                        if target_base.startswith("file:///"):
                            p = target_base[8:]
                            if len(p) > 2 and p[1] == ':': # Windows drive letter e.g. d:/...
                                resolved_path = os.path.normpath(p)
                            else:
                                resolved_path = os.path.normpath("/" + p)
                        elif target_base.startswith("file://"):
                            rel_p = target_base[7:].lstrip("/")
                            if len(rel_p) > 2 and rel_p[1] == ':': # Windows drive letter
                                resolved_path = os.path.normpath(rel_p)
                            else:
                                resolved_path = os.path.normpath(os.path.join(repo_root, rel_p))
                        else:
                            resolved_path = os.path.normpath(os.path.join(file_dir, target_base))

                        if not os.path.exists(resolved_path):
                            # Check if it's an external absolute repo reference that exists outside workspace
                            broken_links.append({
                                "file": rel_file,
                                "line": line_idx,
                                "text": link_text,
                                "target": target,
                                "resolved": resolved_path,
                            })
                    except Exception:
                        broken_links.append({
                            "file": rel_file,
                            "line": line_idx,
                            "text": link_text,
                            "target": target,
                            "resolved": "invalid_path",
                        })

    return broken_links, total_checked


def has_real_body(body: str) -> bool:
    """Return True only if the body contains real content beyond a bare H1 or empty stub."""
    stripped = body.strip()
    if not stripped:
        return False
    lines = [l.strip() for l in stripped.splitlines() if l.strip()]
    return len(lines) > 1


def _extract_project_meta(target_dir: str):
    """Extract project title and summary from README.md or directory name."""
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
            quote_m = re.search(r"^>\s+(.+)$", readme_text, re.MULTILINE)
            if quote_m:
                summary = f"> {quote_m.group(1).strip()}"
        except Exception:
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
            except Exception:
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
        except Exception:
            pass

    agents_path = os.path.join(target_dir, "AGENTS.md")
    if os.path.isfile(agents_path):
        try:
            agents_body = textio.read_text(agents_path).strip()
            if agents_body:
                full_parts.extend(["", "---", "", "## Document: AGENTS.md (Agent Conventions & Protocol)", "", agents_body])
        except Exception:
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
        except Exception:
            pass

    full_content = "\n".join(full_parts).rstrip() + "\n"

    for target_path in targets:
        existing = ""
        if os.path.isfile(target_path):
            try:
                existing = textio.read_text(target_path)
            except Exception:
                existing = ""

        if not dry_run:
            if not os.path.isfile(target_path) or full_content != existing:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                textio.write_text(target_path, full_content)
                rel_disp = repo.safe_relpath(target_path, target_dir)
                print(f"   -> Compiled {rel_disp} ({len(articles)} documents included).")


def sync_kb(repo_root, check_only=False, strict=False, prune_intent=None, is_subproject=False):
    repo_root = os.path.abspath(repo_root)
    docs_dir = os.path.join(repo_root, "docs")
    today = datetime.now().strftime("%Y-%m-%d")

    print(f"-> Synchronizing Knowledge Base in {docs_dir}...")
    reconcile_sources(repo_root, docs_dir, dry_run=check_only)

    if not os.path.exists(docs_dir) or not os.listdir(docs_dir):
        print("   docs/ is missing or empty. Bootstrapping standard articles...")
        bootstrapped = bootstrap_docs_if_empty(docs_dir, repo_root, dry_run=check_only)
        print(f"   Bootstrapped {bootstrapped} core Knowledge Base articles.")

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
    except Exception:
        in_git = False

    for f in sorted(os.listdir(docs_dir)):
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
                            except Exception as e:
                                print(f"   [WARN] Failed to read source '{src_rel}' for docs/{f}: {e}")

            # Check content reduction against HEAD if in git
            if in_git:
                try:
                    rel_to_repo = os.path.relpath(file_path, repo_root).replace("\\", "/")
                    head_res = proc.run_capture(["git", "show", f"HEAD:{rel_to_repo}"], cwd=repo_root)
                    if head_res.ok:
                        head_lines = len(head_res.stdout.splitlines())
                        cur_lines = len(raw_content.splitlines())
                        delta = head_lines - cur_lines
                        if head_lines >= 15 and delta >= 10 and (delta / head_lines) > 0.25:
                            pct = round((delta / head_lines) * 100)
                            shrunk_articles.append((f, delta, pct))
                except Exception:
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
            if not fm.get('protocol_version'):
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
        except Exception as e:
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
    index_body_lines.append("- [AGENTS.md](../AGENTS.md): Active protocol conventions and rules.")
    index_body_lines.append("- [.along/DECISIONS.md](../.along/DECISIONS.md): Architectural Decision Records.")
    index_body_lines.append("- [.along/ISSUES.md](../.along/ISSUES.md): Active issue tracking board.")
    index_body_lines.append("- [.along/HISTORY.md](../.along/HISTORY.md): Append-only project history log.")

    if not check_only:
        full_index = dump_frontmatter(index_fm, "\n".join(index_body_lines))
        with open(index_path, "w", encoding="utf-8") as fp:
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
                sync_kb(ctx, check_only=check_only, strict=strict, prune_intent=prune_intent, is_subproject=True)

    if not is_subproject:
        # Step: Inbound Link Rewriting across the entire repository
        print("-> Scanning repository for inbound legacy links (Link Rewriting Engine)...")
        rewritten_files, total_rewrites = rewrite_inbound_links(repo_root, dry_run=check_only)
        if total_rewrites > 0:
            print(f"   [OK] Rewrote {total_rewrites} legacy link(s) across {rewritten_files} file(s).")
        else:
            print("   [OK] Inbound links are clean and up to date.")

        # Cleanup obsolete files/dirs only after rewriting inbound links
        if not check_only:
            for old_kb in [os.path.join(repo_root, ".along", "KB"), os.path.join(repo_root, ".agents", "KB")]:
                if os.path.exists(old_kb):
                    shutil.rmtree(old_kb, ignore_errors=True)

    # Step: Repository-wide Link Integrity Gate
    print("-> Executing Global Link Integrity Gate across all repository Markdown files...")
    broken_links, total_checked = validate_repo_link_integrity(repo_root)
    if broken_links:
        print(f"   [WARN] Link Integrity Gate detected {len(broken_links)} broken relative link(s) (checked {total_checked}):")
        for bl in broken_links:
            print(f"      - {bl['file']}:{bl['line']} -> [{bl['text']}]({bl['target']}) (target missing on disk)")
        if strict:
            print("   [FAIL] Link Integrity Gate failed in strict mode.")
            sys.exit(1)
    else:
        print(f"   [OK] All {total_checked} relative Markdown link(s) verified on disk.")
        broken_links = []

    print(f"-> Knowledge Base sync complete. Total active articles: {len(articles) + (1 if os.path.exists(index_path) else 0)}\n")
    return len(articles), len(broken_links)

def main():
    parser = argparse.ArgumentParser(description="Along Knowledge Base Compiler, Link Rewriter & Integrity Gate")
    parser.add_argument("repo_root", nargs="?", default=".", help="Target repository root directory")
    parser.add_argument("--check", action="store_true", help="Check links and structure without modifying files")
    parser.add_argument("--strict", action="store_true", help="Fail with non-zero exit code if broken links are found")
    parser.add_argument("--prune-intent", dest="prune_intent", nargs="?", const="Intentional content pruning", default=None, help="Acknowledge and allow content reduction with an optional intent rationale")
    parser.add_argument("--allow-shrink", dest="prune_intent", action="store_const", const="Allow shrink", help="Alias for --prune-intent")
    args = parser.parse_args()

    sync_kb(args.repo_root, check_only=args.check, strict=args.strict, prune_intent=args.prune_intent)

if __name__ == "__main__":
    main()
