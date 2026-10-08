#!/usr/bin/env python3
"""
alongkit.scaffold - Agent-context scaffolding shared by `along init`, `along update`
and the migration engine.

One definition of:
- the managed protocol block in `AGENTS.md`, FULL at an architecture root and a short
  REF in nested folders of the same git working tree;
- how a hand-written `AGENTS.md` without markers is adopted (block on top, the
  original text unchanged below under `## Project specifics`);
- how a folder's own root `VISION.md` is reconciled with `.along/VISION.md` so the
  two never coexist (moved, deduplicated, or merged under a `needs-restructure`
  marker that the agent resolves and `along doctor` reports);
- which root-level project notes the agent must route into the Knowledge Base.

Every mutation goes through `alongkit.migration.Migration`, so dry runs, backups and
the operation summary behave the same in all three callers.
"""


from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )


import os
import re
import shutil
from datetime import date
from typing import Dict, List, Optional

from alongkit import frontmatter, markdown, repo, textio

PROTOCOL_MARKER = "ALONG-PROTOCOL"
LEGACY_PROTOCOL_MARKER = "ACTDIM-AGENTS-PROTOCOL"
MANAGED_SUFFIX = "(managed by along-init - do not edit by hand)"
END_MARKER = f"<!-- END {PROTOCOL_MARKER} -->"

#: A managed block, including stacked duplicate markers left by older engines.
MANAGED_BLOCK_RE = re.compile(
    r"(?:<!-- BEGIN (?:ALONG-PROTOCOL|ACTDIM-AGENTS-PROTOCOL).*?-->\s*)+.*?"
    r"(?:<!-- END (?:ALONG-PROTOCOL|ACTDIM-AGENTS-PROTOCOL) -->)(?:\s*<!-- END "
    r"(?:ALONG-PROTOCOL|ACTDIM-AGENTS-PROTOCOL) -->)*",
    re.DOTALL,
)
FULL_BLOCK_RE = re.compile(r"<!-- BEGIN (?:ALONG-PROTOCOL|ACTDIM-AGENTS-PROTOCOL) root\b")
_WRAPPER_BEGIN_RE = re.compile(r"^<!-- BEGIN (?:ALONG-PROTOCOL|ACTDIM-AGENTS-PROTOCOL).*?-->\r?\n?")
_WRAPPER_END_RE = re.compile(r"\r?\n?<!-- END (?:ALONG-PROTOCOL|ACTDIM-AGENTS-PROTOCOL) -->$")
_SPECIFICS_HEADING_RE = re.compile(r"^#{1,6}[ \t]+Project specifics[ \t]*$", re.MULTILINE)

CLAUDE_IMPORT_LINE = "See @AGENTS.md for project instructions and guidance."

VISION_FILENAME = "VISION.md"
IMPORTED_VISION_BEGIN = "<!-- along:imported-vision needs-restructure"
IMPORTED_VISION_END = "<!-- /along:imported-vision -->"

#: Root-level notes that duplicate the Knowledge Base when left in place. Deliberately
#: narrow: CHANGELOG, CONTRIBUTING, SECURITY and LICENSE belong at the root.
ROOT_NOTE_NAMES = ("ROADMAP.md", "ARCHITECTURE.md", "SPEC.md", "TODO.md", "DESIGN.md")

_HEADING_RE = re.compile(r"^(#{1,6})([ \t]+.*)$")
_ITALIC_LINE_RE = re.compile(r"^(?:_[^_].*_|\*[^*].*\*)$")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


# ---------------------------------------------------------------------------
# Managed protocol block
# ---------------------------------------------------------------------------

def strip_protocol_wrapper(protocol_text: str) -> str:
    """Protocol text without its own BEGIN/END marker lines (as shipped in protocol.md)."""
    text = _WRAPPER_BEGIN_RE.sub("", protocol_text.strip())
    return _WRAPPER_END_RE.sub("", text.strip()).strip()


def render_protocol_block(protocol_text: str, ref_path: Optional[str] = None) -> str:
    """The FULL managed block, or a short REF block pointing at `ref_path`."""
    if not ref_path:
        begin = f"<!-- BEGIN {PROTOCOL_MARKER} root {MANAGED_SUFFIX} -->"
        return f"{begin}\n{strip_protocol_wrapper(protocol_text)}\n{END_MARKER}"
    begin = f"<!-- BEGIN {PROTOCOL_MARKER} ref={ref_path} {MANAGED_SUFFIX} -->"
    return (
        f"{begin}\n"
        "This folder belongs to a repository that uses the ALONG structure. The full working\n"
        f"guidance + agent-context protocol live once in the nearest ancestor `AGENTS.md` (`{ref_path}`) -\n"
        "read it there. This folder keeps its OWN `.along/` state; use the nearest one.\n"
        "Only this folder's specifics follow.\n"
        f"{END_MARKER}"
    )


def is_git_boundary(path: str) -> bool:
    """True when `path` is the top of a git working tree (repository or submodule)."""
    return os.path.exists(os.path.join(path, ".git"))


def find_full_protocol_ancestor(root: str) -> Optional[str]:
    """Nearest ancestor of `root` whose `AGENTS.md` carries a FULL protocol block.

    The walk stays inside one git working tree: a repository or submodule root is
    always its own architecture root, because a REF into a parent repository breaks
    the moment the submodule is cloned on its own.
    """
    root = os.path.abspath(root)
    if is_git_boundary(root):
        return None
    current = os.path.dirname(root)
    while True:
        agents_md = os.path.join(current, "AGENTS.md")
        if os.path.isfile(agents_md):
            if FULL_BLOCK_RE.search(textio.read_text(agents_md, strict=False)):
                return current
        if is_git_boundary(current):
            return None
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def protocol_block_for(ctx_dir: str, protocol_text: str) -> Dict[str, str]:
    """The block `ctx_dir` should carry, with its variant (`FULL` or `REF`)."""
    ancestor = find_full_protocol_ancestor(ctx_dir)
    if ancestor is None:
        return {"variant": "FULL", "block": render_protocol_block(protocol_text), "ref": ""}
    ref = repo.normalize_posix(repo.safe_relpath(os.path.join(ancestor, "AGENTS.md"), ctx_dir))
    return {"variant": "REF", "block": render_protocol_block(protocol_text, ref), "ref": ref}


def merge_protocol_block(existing: str, block: str) -> str:
    """`existing` AGENTS.md text with its managed block replaced by `block`.

    A file without markers was written by hand: the block goes on top and the original
    text follows unchanged, under `## Project specifics` unless it already has one.
    """
    match = MANAGED_BLOCK_RE.search(existing)
    if match:
        before = existing[:match.start()]
        after = existing[match.end():].lstrip("\r\n")
        return before + block + ("\n\n" + after if after.strip() else "\n")
    body = existing.lstrip("\r\n")
    if not body.strip():
        return block + "\n\n## Project specifics\n\n- Add project conventions here.\n"
    if not _SPECIFICS_HEADING_RE.search(body):
        body = "## Project specifics\n\n" + body
    return block + "\n\n" + body


def new_agents_md(block: str) -> str:
    """A fresh AGENTS.md: the managed block and an empty specifics section."""
    return block + "\n\n## Project specifics\n\n- Add project conventions here.\n"


def ensure_claude_import(existing: Optional[str]) -> str:
    """CLAUDE.md text that imports AGENTS.md; prepends the line when it is missing."""
    if existing is None or not existing.strip():
        return CLAUDE_IMPORT_LINE + "\n"
    if "@AGENTS.md" in existing:
        return existing
    return CLAUDE_IMPORT_LINE + "\n\n" + existing


# ---------------------------------------------------------------------------
# VISION reconciliation
# ---------------------------------------------------------------------------

def vision_template() -> str:
    """The skeleton `.along/VISION.md` written when no vision exists yet."""
    return (
        "# Vision\n\n"
        "_North star: scope, boundaries, non-goals, roadmap. Evolves slowly; slims as features ship._\n\n"
        "## Scope\n\n"
        "## Non-goals\n\n"
        "## Roadmap\n"
    )


def _body_without_frontmatter(text: str) -> str:
    block = frontmatter.split(text)
    return block.body if block else text


def is_vision_skeleton(text: str) -> bool:
    """True when a VISION file holds no content of its own.

    Structural, not textual: only headings, blank lines, italic placeholder lines and
    HTML comments. Any skeleton from any Along version qualifies.
    """
    body = _HTML_COMMENT_RE.sub("", _body_without_frontmatter(text))
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or _ITALIC_LINE_RE.match(stripped):
            continue
        return False
    return True


def _normalized(text: str) -> str:
    lines = [line.rstrip() for line in _body_without_frontmatter(text).replace("\r\n", "\n").split("\n")]
    return "\n".join(lines).strip()


def find_root_file(ctx_dir: str, name: str) -> Optional[str]:
    """`ctx_dir/<name>` matched case-insensitively, or None."""
    try:
        entries = os.listdir(ctx_dir)
    except OSError:
        return None
    for entry in sorted(entries):
        if entry.lower() == name.lower() and os.path.isfile(os.path.join(ctx_dir, entry)):
            return os.path.join(ctx_dir, entry)
    return None


def rebase_relative_links(text: str, from_dir: str, to_dir: str) -> str:
    """Rewrite relative links in `text` so they still resolve after moving it to `to_dir`."""
    def transform(link: markdown.Link) -> Optional[str]:
        path_part = link.path_part
        if (not path_part or markdown.is_external(link.target) or markdown.is_placeholder(link.target)
                or link.target.startswith(("file://", "/"))):
            return None
        absolute = os.path.normpath(os.path.join(from_dir, path_part))
        return repo.canonical_relpath(absolute, to_dir) + link.anchor

    rebased, _ = markdown.rewrite_links(text, transform)
    return rebased


def _demote_headings(text: str) -> str:
    """Drop the leading H1 and push every other heading one level down (outside fences)."""
    out: List[str] = []
    tracker = markdown.FenceTracker()
    dropped_title = False
    for line in text.splitlines(keepends=True):
        if tracker.process_line(line) or tracker.in_fence:
            out.append(line)
            continue
        match = _HEADING_RE.match(line.rstrip("\r\n"))
        if match:
            hashes = match.group(1)
            if len(hashes) == 1 and not dropped_title:
                dropped_title = True
                continue
            ending = line[len(line.rstrip("\r\n")):]
            out.append("#" * min(len(hashes) + 1, 6) + match.group(2) + ending)
            continue
        out.append(line)
    return "".join(out).strip("\r\n")


def _iter_markdown_files(ctx_dir: str):
    """Markdown files of one context, not descending into other git working trees."""
    ignored = set(repo.IGNORED_DIRS) | set(repo.PROVIDER_DIRS)
    for current, dirs, files in os.walk(ctx_dir):
        dirs[:] = [d for d in dirs
                   if d not in ignored and not is_git_boundary(os.path.join(current, d))]
        for name in sorted(files):
            if name.lower().endswith(".md"):
                yield os.path.join(current, name)


def minimal_docs_index(today: str) -> str:
    return (
        "---\n"
        "protocol: along\n"
        "slug: INDEX\n"
        "title: Knowledge Base Index\n"
        "type: index\n"
        f"created: {today}\n"
        f"updated: {today}\n"
        "tags: [index, kb]\n"
        "---\n\n"
        "# Knowledge Base Index\n\n"
        "_Topic map of `docs/topic--*.md`. Rebuilt by `/along-kb-sync`._\n"
    )


def rewrite_vision_links(ctx_dir: str, root_vision: str, along_vision: str, mig,
                         today: str) -> List[str]:
    """Repoint links aimed at the root VISION.md; return the files changed.

    Public files (README.md, docs/) may not link into `.along/` (stable-entry-point),
    so they are routed to `docs/INDEX.md`. Files inside `.along/` link to the new
    `.along/VISION.md` directly.
    """
    root_vision = os.path.normcase(os.path.abspath(root_vision))
    along_dir = os.path.join(ctx_dir, repo.STATE_DIR)
    docs_index = os.path.join(ctx_dir, "docs", "INDEX.md")
    changed: List[str] = []
    for path in _iter_markdown_files(ctx_dir):
        if os.path.normcase(os.path.abspath(path)) == root_vision:
            continue
        try:
            content = textio.read_text(path)
        except (OSError, UnicodeDecodeError):
            continue
        file_dir = os.path.dirname(path)
        inside_state = os.path.normcase(os.path.abspath(path)).startswith(
            os.path.normcase(os.path.abspath(along_dir)) + os.sep)

        def transform(link: markdown.Link) -> Optional[str]:
            resolved = markdown.resolve_target(link.target, path, ctx_dir)
            if resolved is None or os.path.normcase(resolved) != root_vision:
                return None
            if inside_state:
                return repo.canonical_relpath(along_vision, file_dir) + link.anchor
            return repo.canonical_relpath(docs_index, file_dir)

        updated, count = markdown.rewrite_links(content, transform)
        if count:
            if not inside_state and not os.path.isfile(docs_index):
                mig.makedirs(os.path.dirname(docs_index))
                mig.write(docs_index, minimal_docs_index(today),
                          detail="created as the public target of former VISION.md links")
            mig.write(path, updated, detail=f"{count} VISION.md link(s) repointed", announce=True)
            changed.append(path)
    return changed


def _backup_root_file(mig, path: str) -> None:
    """Keep a copy of a root file the reconciliation removes, next to the state backup."""
    backup_dir = mig.ensure_backup()
    if mig.dry_run or not backup_dir:
        return
    target_dir = os.path.join(backup_dir, "root")
    os.makedirs(target_dir, exist_ok=True)
    shutil.copy2(path, os.path.join(target_dir, os.path.basename(path)))


def reconcile_root_vision(ctx_dir: str, mig, today: Optional[str] = None) -> Dict[str, object]:
    """Make `.along/VISION.md` the only VISION of `ctx_dir`.

    Outcomes (`action`):
    - `none`: no root VISION.md, or no `.along/` to receive it.
    - `moved`: `.along/VISION.md` was missing; the root content now lives there.
    - `replaced-skeleton`: `.along/VISION.md` was an empty skeleton; replaced.
    - `removed-duplicate`: both files said the same thing; the root copy is gone.
    - `merged-needs-restructure`: both had content; the root content is appended to
      `.along/VISION.md` inside an `along:imported-vision` marker the agent resolves.
    A VISION.md in a subfolder is never touched: it belongs to that subproject.
    """
    today = today or date.today().isoformat()
    result: Dict[str, object] = {"action": "none", "source": "", "links": []}
    root_vision = find_root_file(ctx_dir, VISION_FILENAME)
    along_dir = os.path.join(ctx_dir, repo.STATE_DIR)
    if root_vision is None or not os.path.isdir(along_dir):
        return result
    along_vision = os.path.join(along_dir, VISION_FILENAME)
    result["source"] = root_vision

    try:
        root_text = textio.read_text(root_vision)
    except UnicodeDecodeError as exc:
        mig.note_skipped(root_vision, f"not valid UTF-8 ({exc.reason})")
        mig.record_error(f"{mig.rel(root_vision)} is not valid UTF-8; reconcile VISION by hand.")
        result["action"] = "skipped"
        return result
    rebased = rebase_relative_links(root_text, ctx_dir, along_dir)

    if not os.path.isfile(along_vision):
        mig.write(along_vision, rebased, detail=f"moved from {mig.rel(root_vision)}", announce=True)
        result["action"] = "moved"
    else:
        along_text = textio.read_text(along_vision)
        if is_vision_skeleton(along_text):
            block = frontmatter.split(along_text)
            prefix = along_text[:len(along_text) - len(block.body)] if block and not frontmatter.has_frontmatter(rebased) else ""
            mig.write(along_vision, prefix + rebased,
                      detail=f"skeleton replaced by {mig.rel(root_vision)}", announce=True)
            result["action"] = "replaced-skeleton"
        elif _normalized(along_text) == _normalized(root_text) or _normalized(along_text) == _normalized(rebased):
            result["action"] = "removed-duplicate"
        else:
            imported = _demote_headings(_body_without_frontmatter(rebased))
            section = (
                f"{IMPORTED_VISION_BEGIN} source={mig.rel(root_vision)} date={today} -->\n"
                f"## Imported from root VISION.md ({today})\n\n"
                "_Agent: decompose this section (scope / non-goals / roadmap stay above; "
                "architecture -> docs/topic--architecture.md; backlog -> ISSUES / MILESTONES), "
                "then delete it together with its markers._\n\n"
                f"{imported}\n"
                f"{IMPORTED_VISION_END}\n"
            )
            mig.write(along_vision, along_text.rstrip() + "\n\n" + section,
                      detail=f"merged from {mig.rel(root_vision)}; needs restructure", announce=True)
            result["action"] = "merged-needs-restructure"

    result["links"] = rewrite_vision_links(ctx_dir, root_vision, along_vision, mig, today)
    _backup_root_file(mig, root_vision)
    mig.discard(root_vision, f"now lives in {mig.rel(along_vision)} ({result['action']})")
    return result


def find_imported_vision_markers(ctx_dir: str) -> List[str]:
    """`.along/VISION.md` paths that still carry an unresolved imported-vision section."""
    path = os.path.join(ctx_dir, repo.STATE_DIR, VISION_FILENAME)
    if os.path.isfile(path) and IMPORTED_VISION_BEGIN in textio.read_text(path, strict=False):
        return [path]
    return []


def find_root_notes(ctx_dir: str) -> List[str]:
    """Root-level project notes the agent must route into docs/, VISION or entities."""
    found = []
    for name in ROOT_NOTE_NAMES:
        path = find_root_file(ctx_dir, name)
        if path:
            found.append(path)
    return found
