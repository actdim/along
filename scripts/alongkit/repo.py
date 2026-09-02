#!/usr/bin/env python3
"""
alongkit.repo - Repository and tool-path resolution.

Single definition of what an Along repository root is, where the nearest `.along/`
state directory lives, and how one engine locates a sibling engine. Before this
module the codebase carried five divergent copies of `find_repo_root`, which could
resolve different roots from the same working directory.
"""


from __future__ import annotations
if __name__ == "__main__":
    raise SystemExit(
        f"{__name__} is a library module, not a command.\n"
        "Run: along kb-sync   (or: python scripts/along_exec.py kb-sync)"
    )


import os
from typing import Iterable, Iterator, List, Optional

# A directory is a repository root when it carries any of these markers.
# The union of what the five former copies checked, so no caller loses a root it
# used to find. `.along` first: an Along-initialized subproject wins over an
# enclosing plain git repository, which is what the nearest-context-boundary rule
# in AGENTS.md requires.
ROOT_MARKERS: tuple = (".along", ".git", "AGENTS.md")

# Legacy state directory name, still readable for repositories initialized before v2.0.0.
STATE_DIR = ".along"
LEGACY_STATE_DIR = ".agents"

# Where a globally installed copy of the engines may live. Kept in one place so
# `resolve_tool_script` and the installers agree.
GLOBAL_TOOL_DIRS: tuple = (
    "~/.along/bin",
    "~/.config/opencode/actdim-along",
    "~/.gemini/config/scripts",
    "~/.claude/scripts",
    "~/.codex/scripts",
)

#: Legacy per-skill script locations, from before the engines were centralized in
#: . Searched only when a caller names the owning skill folder.
SKILL_TOOL_DIRS: tuple = (
    "~/.gemini/config/skills/{skill}",
    "~/.gemini/antigravity/skills/{skill}",
    "~/.claude/skills/{skill}",
    "~/.codex/skills/{skill}",
    "~/.config/opencode/skills/{skill}",
)


def engines_dir() -> str:
    """Absolute directory holding the Along engine scripts (the package parent).

    Works both in the source repository (`<repo>/scripts`) and in a flat global
    install (`~/.along/bin`), because the package is always copied next to the
    engines it serves.
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_repo_root(start_dir: Optional[str] = None,
                   markers: Iterable[str] = ROOT_MARKERS) -> str:
    """Walk upwards from `start_dir` to the nearest directory carrying a root marker.

    Falls back to `start_dir` itself (absolute) when no marker is found, so callers
    always receive a usable path instead of None.
    """
    origin = os.path.abspath(start_dir or os.getcwd())
    cur = origin
    markers = tuple(markers)
    while True:
        for marker in markers:
            if os.path.exists(os.path.join(cur, marker)):
                return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return origin
        cur = parent


def find_state_dir(start_dir: Optional[str] = None) -> Optional[str]:
    """Nearest existing `.along/` (or legacy `.agents/`) directory, or None.

    This is the nearest-context-boundary lookup: entities belong to the closest
    state directory, not to the outermost repository.
    """
    cur = os.path.abspath(start_dir or os.getcwd())
    while True:
        for name in (STATE_DIR, LEGACY_STATE_DIR):
            candidate = os.path.join(cur, name)
            if os.path.isdir(candidate):
                return candidate
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def state_dir(repo_root: str) -> str:
    """Path of the state directory for `repo_root`, preferring an existing legacy one."""
    primary = os.path.join(repo_root, STATE_DIR)
    if os.path.isdir(primary):
        return primary
    legacy = os.path.join(repo_root, LEGACY_STATE_DIR)
    if os.path.isdir(legacy):
        return legacy
    return primary


def bundled_engines_dir() -> str:
    """Directory of engines shipped inside an installed wheel (`alongkit/engines/`).

    Empty in a source checkout, where the engines live next to the package instead.
    """
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "engines")


def tool_search_path(repo_root: Optional[str] = None,
                     skill_folder: Optional[str] = None) -> List[str]:
    """Ordered directories searched for an Along engine script."""
    candidates = [engines_dir(), bundled_engines_dir()]
    if repo_root:
        candidates.append(os.path.join(repo_root, "scripts"))
    candidates.extend(os.path.expanduser(p) for p in GLOBAL_TOOL_DIRS)
    if skill_folder:
        candidates.extend(os.path.expanduser(p.format(skill=skill_folder))
                          for p in SKILL_TOOL_DIRS)
    seen = set()
    ordered = []
    for path in candidates:
        key = os.path.normcase(os.path.abspath(path))
        if key not in seen:
            seen.add(key)
            ordered.append(path)
    return ordered


def resolve_tool_script(script_name: str, repo_root: Optional[str] = None,
                        skill_folder: Optional[str] = None) -> Optional[str]:
    """Locate a sibling engine script by name, or None when it is not installed.

    Engines must never hardcode `<repo_root>/scripts/<name>`: a consumer repository
    has no `scripts/` directory, and the engines are installed to `~/.along/bin`.
    """
    for directory in tool_search_path(repo_root, skill_folder):
        candidate = os.path.join(directory, script_name)
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


def safe_relpath(path: str, start: str) -> str:
    """`os.path.relpath` that degrades to the absolute path instead of raising.

    On Windows, `relpath` raises ValueError across drives (C: versus D:), which is
    a normal situation when scanning dependencies resolved into a user-profile cache.
    """
    try:
        return os.path.relpath(path, start)
    except ValueError:
        return path


def normalize_posix(path_str: str) -> str:
    """Backslashes to forward slashes, for links and stable cross-platform output."""
    return path_str.replace("\\", "/")


#: Directories never traversed when scanning a repository: version-control internals,
#: dependency trees, build output, tool caches, and the processed-source archive.
#: The union of the sets that `along_kb_sync.py` and `along_dep_scan.py` each defined
#: separately, so a scanner and a gate can no longer disagree about what exists.
IGNORED_DIRS: frozenset = frozenset({
    ".git", ".hg", ".svn",
    "node_modules", ".venv", "venv", "env",
    "dist", "build", "out", "bin", "obj", "target",
    ".cache", ".mypy_cache", ".pytest_cache", "__pycache__",
    ".next", ".nuxt", ".output",
    ".vscode", ".idea",
    ".archive", "archive",
    "vendor",
})

#: Provider configuration directories. Skipped by content scans because they hold
#: copies of the engines and skills rather than repository content.
PROVIDER_DIRS: frozenset = frozenset({".gemini", ".claude", ".codex", ".opencode"})


def iter_files(root: str, suffixes: Iterable[str] = (".md",),
               include_hidden: bool = False,
               extra_ignores: Iterable[str] = ()) -> Iterator[str]:
    """Walk `root` yielding absolute file paths, skipping ignored directories.

    `include_hidden=False` skips every dot-directory, which is what the existing
    gates do. That default is why a broken link or a banned character inside
    `.along/` has never been reported, tracked as
    `[bug--link-gates-skip-along-directory]` and
    `[bug--quality-gates-skip-hidden-directories]`. Those issues flip the flag at
    their call sites, with tests; the lever lives here so it only has to be flipped
    once.
    """
    root = os.path.abspath(root)
    ignored = set(IGNORED_DIRS) | set(PROVIDER_DIRS) | set(extra_ignores)
    wanted = tuple(suffixes)
    for current, dirs, files in os.walk(root):
        dirs[:] = [
            d for d in dirs
            if d not in ignored and (include_hidden or not d.startswith("."))
        ]
        for name in sorted(files):
            if not include_hidden and name.startswith(".") and not wanted:
                continue
            if wanted and not name.endswith(wanted):
                continue
            yield os.path.join(current, name)


def iter_markdown_files(root: str, include_hidden: bool = False) -> Iterator[str]:
    """Walk `root` yielding absolute paths of markdown files."""
    return iter_files(root, suffixes=(".md",), include_hidden=include_hidden)
