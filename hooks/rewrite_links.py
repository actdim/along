"""MkDocs hook: universal link resolver for Along documentation.

Classifies every relative Markdown link into one of three spatial zones:
1. Inside `docs/`: internal site page (preserves relative doc link; applies PAGE_ALIASES).
2. Inside repo root: repository file (maps to GitHub blob URL for this repo).
   - If inside `node_modules/@<org>/<pkg>`, maps to that package's GitHub repo.
3. Sibling directory in workspace: maps to `https://github.com/<org>/<sibling>/blob/main/...`.
"""

import os
from pathlib import Path
import re

from mkdocs.structure.files import File

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"

GITHUB_ORG = "actdim"
DEFAULT_BRANCH = "main"

# Explicit alias map for file names that differ between repo and docs site
PAGE_ALIASES = {
    "LICENSE": "topic--license.md",
    "license.md": "topic--license.md",
}


def on_files(files, config):
    """Inject repo root README.md as virtual root index.md."""
    readme_path = REPO_ROOT / "README.md"
    if readme_path.is_file():
        readme_file = File(
            path="index.md",
            src_dir=str(REPO_ROOT),
            dest_dir=config.site_dir,
            use_directory_urls=config.use_directory_urls,
        )
        readme_file.abs_src_path = str(readme_path)
        files.append(readme_file)
    return files


def resolve_link(target: str, src_path: str) -> str:
    """Universally resolve any markdown link target given the source file path."""
    clean_target = target.strip()

    # 1. Ignore web URLs, anchors, mailto, etc.
    if clean_target.startswith(("#", "http://", "https://", "mailto:", "javascript:")):
        return target

    # Separate target file and anchor (#section)
    path_part, hash_char, anchor = clean_target.partition("#")
    if not path_part:
        return target

    current_dir = os.path.dirname(os.path.join(str(DOCS_DIR), src_path))

    # Normalize path syntactically without resolving symlinks
    if path_part.startswith(("./docs/", "docs/")):
        rel_from_root = path_part[7:] if path_part.startswith("./docs/") else path_part[5:]
        norm_full = os.path.normpath(os.path.join(str(DOCS_DIR), rel_from_root))
    else:
        norm_full = os.path.normpath(os.path.join(current_dir, path_part))

    norm_path = Path(norm_full)

    # Zone 1: Inside docs/ directory (internal documentation site)
    try:
        rel_to_docs = norm_path.relative_to(DOCS_DIR)

        # Check explicit filename alias (e.g. LICENSE -> topic--license.md)
        filename = norm_path.name
        if filename in PAGE_ALIASES:
            aliased = PAGE_ALIASES[filename]
            target_path = norm_path.parent / aliased
        else:
            target_path = norm_path

        # Relative link from current document to target document
        rel_to_current = os.path.relpath(str(target_path), current_dir)
        rel_str = rel_to_current.replace("\\", "/")
        if not rel_str.startswith((".", "/")):
            rel_str = f"./{rel_str}"

        res = rel_str
        if hash_char:
            res += f"#{anchor}"
        return res
    except ValueError:
        pass

    # Zone 2: Inside this repository (non-doc files: scripts, tests, config, .along)
    try:
        rel_to_repo = norm_path.relative_to(REPO_ROOT)
        parts = rel_to_repo.parts

        # Check if target is a file in node_modules/@org/package/...
        if "node_modules" in parts:
            nm_idx = parts.index("node_modules")
            rest = parts[nm_idx + 1:]
            if rest and rest[0].startswith("@"):
                org_name = rest[0][1:]
                pkg_name = rest[1]
                subpath = "/".join(rest[2:])
                res = f"https://github.com/{org_name}/{pkg_name}/blob/{DEFAULT_BRANCH}/{subpath}"
                if hash_char:
                    res += f"#{anchor}"
                return res

        # Check if target is LICENSE at repo root
        if rel_to_repo.name in PAGE_ALIASES:
            target_page = DOCS_DIR / PAGE_ALIASES[rel_to_repo.name]
            rel_to_current = os.path.relpath(str(target_page), current_dir).replace("\\", "/")
            if not rel_to_current.startswith((".", "/")):
                rel_to_current = f"./{rel_to_current}"
            if hash_char:
                rel_to_current += f"#{anchor}"
            return rel_to_current

        # Standard file inside this repository
        repo_rel_str = "/".join(parts)
        res = f"https://github.com/{GITHUB_ORG}/along/blob/{DEFAULT_BRANCH}/{repo_rel_str}"
        if hash_char:
            res += f"#{anchor}"
        return res
    except ValueError:
        pass

    # Zone 3: Sibling repository in workspace (e.g. ../../dynstruct/...)
    try:
        rel_to_workspace = norm_path.relative_to(REPO_ROOT.parent)
        parts = rel_to_workspace.parts
        sibling_repo = parts[0]
        sibling_subpath = "/".join(parts[1:])
        res = f"https://github.com/{GITHUB_ORG}/{sibling_repo}/blob/{DEFAULT_BRANCH}/{sibling_subpath}"
        if hash_char:
            res += f"#{anchor}"
        return res
    except ValueError:
        pass

    # Fallback: leave as-is
    return target


def on_page_markdown(markdown: str, page, config, files) -> str:
    """Pre-process markdown before MkDocs builds HTML and navigation."""
    src_path = page.file.src_path

    def _replace_link(match: re.Match) -> str:
        text = match.group(1)
        target = match.group(2)
        resolved = resolve_link(target, src_path)
        return f"[{text}]({resolved})"

    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _replace_link, markdown)
