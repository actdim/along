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
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )


import json
import os
import re
from typing import Iterable, Iterator, List, Optional, Tuple

# A directory is a repository root when it holds an Along installation (see `is_installed`)
# or a `.git`. An installed subproject wins over an enclosing plain git repository, which is
# what the nearest-context-boundary rule in AGENTS.md requires. `AGENTS.md` is no marker: a
# nested AGENTS.md is a folder guide (progressive disclosure), not a context.
# [ADR-2026-10-07--along-installation-is-state-not-agents-md]
ROOT_MARKERS: tuple = (".git",)

# Legacy state directory name, still readable for repositories initialized before v2.0.0.
STATE_DIR = ".along"
LEGACY_STATE_DIR = ".agents"

#: Entries that only Along state has. A `.along/` holding at least one of them is an Along
#: installation; one holding only what Along writes on its own (diagnostics, synthesized
#: lifecycle hooks, artifacts, blackboards, migration backups) or nothing at all is not, so a
#: folder never becomes a context by side effect. [bug--along-install-marker-ambiguous]
STATE_ENTRIES: frozenset = frozenset({
    "ISSUES", "ISSUES.md", "DECISIONS", "DECISIONS.md", "MILESTONES", "SESSIONS",
    "HISTORY.md", "VISION.md", "GLOSSARY.md", "CONSTRAINTS.md", "RISKS", "SPIKES",
    "CHECKLISTS", ".protocol-version", "KB",
})

#: What Along writes into a `.along/` on its own; never an installation by itself.
#: See [bug--hook-activation-and-gate-deadlock].
RUNTIME_ONLY_ENTRIES: frozenset = frozenset({
    "diagnostics", ".gitignore", "scripts", "artifacts", ".session", ".migration-backup",
    "worktrees",
})

#: Along state inside a legacy `.agents/`; that name is also a third-party convention
#: (`.agents/skills/`), so only these entries make it an Along context.
LEGACY_STATE_ENTRIES: tuple = ("ISSUES.md", "ISSUES", "DECISIONS.md", "DECISIONS", "VISION.md",
                               "HISTORY.md", "GLOSSARY.md")

#: Root pointer in a directory's AGENTS.md: the Along state of that directory lives in
#: `<dir>/<relpath>/.along/` (for example a nested personal repository).
ROOT_POINTER_RE = re.compile(r"<!--\s*along-root:\s*(.+?)\s*-->", re.IGNORECASE)

#: Bytes of AGENTS.md searched for the root pointer.
_POINTER_SCAN_BYTES = 65536


def global_along_dir() -> str:
    """The per-user Along directory (`~/.along`: install, runtime venv, global config)."""
    return os.path.join(os.path.expanduser("~"), ".along")


def _same_path(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def is_along_state_dir(path: str) -> bool:
    """True when `path` is an Along state directory, not hook output or a foreign `.agents/`.

    It must hold Along state (`STATE_ENTRIES`); an empty `.along/` or one with only what
    Along writes on its own (`RUNTIME_ONLY_ENTRIES`) does not count. The global `~/.along`
    is never a context. [bug--along-install-marker-ambiguous]
    """
    if not os.path.isdir(path) or _same_path(path, global_along_dir()):
        return False
    try:
        entries = os.listdir(path)
    except OSError:
        return False
    if os.path.basename(os.path.normpath(path)) == LEGACY_STATE_DIR:
        return any(e in LEGACY_STATE_ENTRIES for e in entries)
    return any(e in STATE_ENTRIES for e in entries)


def _pointer_from_agents_md(directory: str) -> Optional[str]:
    path = os.path.join(directory, "AGENTS.md")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            match = ROOT_POINTER_RE.search(handle.read(_POINTER_SCAN_BYTES))
    except OSError:
        return None
    if not match:
        return None
    return os.path.normpath(os.path.join(directory, match.group(1).strip().strip("'\"`")))


def configured_context_roots() -> List[Tuple[str, str]]:
    """`context_roots` of `~/.along/config.json` as (workspace, root) absolute pairs.

    `[{"workspace": "<dir>", "root": "<dir holding .along/>"}]`; a relative root resolves
    against its workspace. A personal declaration, for repositories whose shared files
    must not mention Along.
    """
    path = os.path.join(global_along_dir(), "config.json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    entries = data.get("context_roots") if isinstance(data, dict) else None
    pairs: List[Tuple[str, str]] = []
    for item in entries if isinstance(entries, list) else []:
        if not isinstance(item, dict) or not item.get("workspace") or not item.get("root"):
            continue
        workspace = os.path.abspath(os.path.expanduser(str(item["workspace"])))
        root = os.path.normpath(os.path.join(workspace, os.path.expanduser(str(item["root"]))))
        pairs.append((workspace, root))
    return pairs


def declared_root(directory: str) -> Optional[str]:
    """Directory holding the Along state declared for `directory`, or None.

    Declared by an `<!-- along-root: <relpath> -->` pointer in `<directory>/AGENTS.md` or
    by `context_roots` in `~/.along/config.json`; it counts only when `<root>/.along/` is
    an Along state directory.
    """
    directory = os.path.abspath(directory)
    candidates = [_pointer_from_agents_md(directory)]
    candidates += [root for workspace, root in configured_context_roots() if _same_path(workspace, directory)]
    for root in candidates:
        if root and not _same_path(root, directory) and is_along_state_dir(os.path.join(root, STATE_DIR)):
            return root
    return None


def context_state_dir(directory: str) -> Optional[str]:
    """The Along state directory that `directory` owns (its own, legacy, or declared), or None."""
    own = os.path.join(directory, STATE_DIR)
    if is_along_state_dir(own):
        return own
    legacy = os.path.join(directory, LEGACY_STATE_DIR)
    if is_along_state_dir(legacy):
        return legacy
    root = declared_root(directory)
    return os.path.join(root, STATE_DIR) if root else None


def find_context(start_dir: Optional[str] = None) -> Optional[Tuple[str, str]]:
    """(owner directory, state directory) of the nearest Along context at or above `start_dir`.

    The owner is the directory the context governs: for a declared root it is the directory
    carrying the declaration, not the directory the state lives in. The walk stops below the
    home directory: home and its ancestors hold the per-user install, never a project.
    """
    cur = os.path.abspath(start_dir or os.getcwd())
    home = os.path.expanduser("~")
    while True:
        if is_within(home, cur):
            return None
        sdir = context_state_dir(cur)
        if sdir:
            return cur, sdir
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent

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
    """Walk upwards from `start_dir` to the nearest Along installation or root marker (`.git`).

    A folder with only an `AGENTS.md`, or with a `.along/` that holds no Along state, is
    passed by. Falls back to `start_dir` itself (absolute) when nothing is found, so callers
    always receive a usable path instead of None. [bug--along-install-marker-ambiguous]
    """
    origin = os.path.abspath(start_dir or os.getcwd())
    cur = origin
    markers = tuple(markers)
    while True:
        if is_installed(cur):
            return cur
        for marker in markers:
            if os.path.exists(os.path.join(cur, marker)):
                return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return origin
        cur = parent


def is_installed(directory: str) -> bool:
    """Along is installed in `directory`: it owns Along state (`.along/` with state entries,
    a legacy `.agents/` with state, or a declared root pointer). Never an `AGENTS.md` alone.

    Only `along init` creates an installation; every other command works inside one.
    [ADR-2026-10-07--along-installation-is-state-not-agents-md]
    """
    return context_state_dir(directory) is not None


def _is_within(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([os.path.normcase(path), os.path.normcase(root)]) == os.path.normcase(root)
    except ValueError:          # different drives on Windows
        return False


def is_within(path: str, root: str) -> bool:
    """True when absolute `path` is `root` or lies below it (False across Windows drives)."""
    return _is_within(os.path.abspath(path), os.path.abspath(root))


def find_session_root(cwd: Optional[str] = None, project_dir: Optional[str] = None) -> str:
    """Root a hook evaluates against: the session's project, not the shell's current directory.

    Runtimes report the agent's current shell cwd, which follows `cd` into nested `.along/`
    contexts. When the runtime also names the project it was opened in (Claude Code:
    `CLAUDE_PROJECT_DIR`) and the cwd lies inside it, the project's root wins, so a nested
    context never narrows the session's scope. Nearest-context placement stays path-based.
    """
    origin = os.path.abspath(cwd or os.getcwd())
    if project_dir:
        project = os.path.abspath(project_dir)
        if os.path.isdir(project) and _is_within(origin, project):
            return find_repo_root(project)
    return find_repo_root(origin)


def find_hook_root(cwd: Optional[str] = None, project_dir: Optional[str] = None) -> Optional[str]:
    """Along root a runtime hook evaluates against, or None when no Along context applies.

    Like `find_session_root`, the session's project wins over the shell cwd; but only an
    Along context counts (a real `.along/`, or a declared root), never a bare `AGENTS.md`
    or `.git`, so repositories that never adopted Along are left alone.
    """
    origin = os.path.abspath(cwd or os.getcwd())
    starts = []
    if project_dir:
        project = os.path.abspath(project_dir)
        if os.path.isdir(project) and _is_within(origin, project):
            starts.append(project)
    starts.append(origin)
    for start in starts:
        found = find_context(start)
        if found:
            return found[0]
    return None


def find_state_dir(start_dir: Optional[str] = None) -> Optional[str]:
    """Nearest Along state directory (`.along/`, legacy `.agents/`, or declared), or None.

    This is the nearest-context-boundary lookup: entities belong to the closest
    state directory, not to the outermost repository. A `.along/` holding only hook
    output does not count.
    """
    found = find_context(start_dir)
    return found[1] if found else None


def state_dir(repo_root: str) -> str:
    """Path of the state directory for `repo_root`: its own, legacy, or declared one.

    Falls back to `<repo_root>/.along` (which may not exist) so callers can create it.
    """
    primary = os.path.join(repo_root, STATE_DIR)
    if os.path.isdir(primary) and is_along_state_dir(primary):
        return primary
    legacy = os.path.join(repo_root, LEGACY_STATE_DIR)
    if os.path.isdir(legacy) and is_along_state_dir(legacy):
        return legacy
    root = declared_root(repo_root)
    if root:
        return os.path.join(root, STATE_DIR)
    return primary


def diagnostics_dir(repo_root: Optional[str]) -> str:
    """Where per-machine diagnostics of `repo_root` live (not created here).

    `<state>/diagnostics/` when the state directory exists; otherwise a per-workspace
    directory under `~/.along/diagnostics/workspaces/`, so diagnostics never create a
    `.along/` in whatever directory a session happens to sit in.
    """
    if repo_root and is_installed(repo_root):
        return os.path.join(state_dir(repo_root), "diagnostics")
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", os.path.abspath(repo_root or os.getcwd())).strip("-")
    return os.path.join(global_along_dir(), "diagnostics", "workspaces", name[-120:] or "default")


def ensure_diagnostics_dir(repo_root: str) -> str:
    """Create the diagnostics directory (see `diagnostics_dir`) with a `*` .gitignore.

    Diagnostics are per-machine runtime state (hook audit, activity traces, heartbeat,
    circuit breaker); tracking them dirties every session and conflicts across branches.
    The directory ignores itself so the user's `.gitignore` is never edited.
    See [bug--activity-trace-shared-across-sessions].
    """
    path = diagnostics_dir(repo_root)
    os.makedirs(path, exist_ok=True)
    marker = os.path.join(path, ".gitignore")
    if not os.path.isfile(marker):
        try:
            with open(marker, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("*\n")
        except OSError:
            pass
    return path


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
    ".migration-backup",
    ".session",
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


STANDARD_MANIFESTS: tuple = (
    "package.json", "Cargo.toml", "pyproject.toml",
    "pom.xml", "build.gradle", "build.gradle.kts",
    "go.mod", "setup.py", "requirements.txt",
)

#: Files that make a directory the root of a multi-project workspace. A manifest below such a
#: root is a project of the workspace, never a context boundary: the workspace keeps one
#: `.along/` at its root. [ADR-2026-10-06--subproject-boundary-is-git-or-explicit-init]
MONOREPO_ROOT_MARKERS: tuple = (
    "Directory.Build.props", "Directory.Packages.props", "pnpm-workspace.yaml",
    "lerna.json", "nx.json", "turbo.json", "go.work",
)
_SOLUTION_SUFFIXES: tuple = (".sln", ".slnx")


def _file_mentions(path: str, needle: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return needle in handle.read()
    except OSError:
        return False


def monorepo_root_markers(path: str) -> List[str]:
    """The workspace-root markers present in `path` (empty when it is not a workspace root).

    Solutions (`*.sln`, `*.slnx`), `MONOREPO_ROOT_MARKERS`, Cargo `[workspace]`,
    `[tool.uv.workspace]` and a `package.json` with `workspaces`.
    """
    try:
        names = os.listdir(path)
    except OSError:
        return []
    found = [n for n in sorted(names) if n in MONOREPO_ROOT_MARKERS or n.endswith(_SOLUTION_SUFFIXES)]
    if "Cargo.toml" in names and _file_mentions(os.path.join(path, "Cargo.toml"), "[workspace]"):
        found.append("Cargo.toml [workspace]")
    if "pyproject.toml" in names and _file_mentions(os.path.join(path, "pyproject.toml"), "[tool.uv.workspace]"):
        found.append("pyproject.toml [tool.uv.workspace]")
    if "package.json" in names and _file_mentions(os.path.join(path, "package.json"), '"workspaces"'):
        found.append("package.json workspaces")
    return found


def is_intentional_subproject(context_dir: str) -> bool:
    """`<context>/.along/config.json` declares `"subproject": {"intentional": true}`."""
    try:
        with open(os.path.join(context_dir, STATE_DIR, "config.json"), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return False
    sub = data.get("subproject") if isinstance(data, dict) else None
    return isinstance(sub, dict) and sub.get("intentional") is True


def find_unmarked_nested_contexts(root: str) -> List[str]:
    """Nested `.along/` contexts below `root` that sit in no nested git repository and are not
    marked intentional.

    Older versions initialized a context per manifest folder; Along cannot tell those from a
    deliberate install, so it only reports them (`along doctor`) and never moves or deletes
    them. [ADR-2026-10-06--subproject-boundary-is-git-or-explicit-init]
    """
    root = os.path.abspath(root)
    found: List[str] = []
    ignored = set(IGNORED_DIRS) | set(PROVIDER_DIRS)
    for current, dirs, _files in os.walk(root):
        if current != root:
            if os.path.exists(os.path.join(current, ".git")):
                dirs[:] = []
                continue
            if is_along_state_dir(os.path.join(current, STATE_DIR)) and not is_intentional_subproject(current):
                found.append(os.path.abspath(current))
        dirs[:] = [d for d in dirs if d not in ignored and not d.startswith(".")]
    found.sort(key=lambda p: (len(p.split(os.sep)), p))
    return found


def find_nested_git_roots(root: str) -> List[str]:
    """Directories below `root` holding a `.git` (repository, submodule or worktree).

    These are the only folders that can be a subproject without the user saying so.
    The walk does not descend into a nested repository, nor into ignored and hidden dirs.
    """
    root = os.path.abspath(root)
    found: List[str] = []
    ignored = set(IGNORED_DIRS) | set(PROVIDER_DIRS)
    for current, dirs, _files in os.walk(root):
        if current != root and os.path.exists(os.path.join(current, ".git")):
            found.append(os.path.abspath(current))
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in ignored and not d.startswith(".")]
    found.sort(key=lambda p: (len(p.split(os.sep)), p))
    return found


def find_agent_contexts(root: str) -> List[str]:
    """Walk `root` downwards to find all Along installations (`is_installed`: a `.along/` or
    legacy `.agents/` with Along state, or a declared root), respecting IGNORED_DIRS and
    PROVIDER_DIRS.

    A folder with only an `AGENTS.md` is a folder guide, not a context: `along update` writes
    no protocol block into it. [bug--along-install-marker-ambiguous]
    """
    root = os.path.abspath(root)
    contexts = []
    ignored = set(IGNORED_DIRS) | set(PROVIDER_DIRS)

    for current, dirs, _files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ignored and not d.startswith(".")]
        if is_installed(current):
            contexts.append(os.path.abspath(current))

    contexts.sort(key=lambda p: (len(p.split(os.sep)), p))
    return contexts


def find_package_doc_roots(root: str) -> List[str]:
    """Package documentation roots below `root`: a folder with `docs/` plus an `AGENTS.md`,
    an `llms.txt` (or `.well-known/llms.txt`) or a package manifest. No `.along/` needed:
    a package ships its docs and guide, the board stays with the context.
    Nested git repositories and ignored or hidden dirs are not entered.
    [bug--along-install-marker-ambiguous] REQ-4
    """
    root = os.path.abspath(root)
    found: List[str] = []
    ignored = set(IGNORED_DIRS) | set(PROVIDER_DIRS)
    manifests = set(STANDARD_MANIFESTS)
    for current, dirs, files in os.walk(root):
        if current != root:
            if os.path.exists(os.path.join(current, ".git")):
                dirs[:] = []
                continue
            if "docs" in dirs and ("AGENTS.md" in files or "llms.txt" in files
                                   or os.path.isfile(os.path.join(current, ".well-known", "llms.txt"))
                                   or any(f in manifests or f.endswith(".csproj") for f in files)):
                found.append(os.path.abspath(current))
        dirs[:] = [d for d in dirs if d not in ignored and not d.startswith(".") and d != "docs"]
    found.sort(key=lambda p: (len(p.split(os.sep)), p))
    return found


def find_managed_agents_md_dirs(root: str) -> List[str]:
    """Folders below `root` whose AGENTS.md carries an Along-managed protocol block.

    Not contexts by themselves (see `find_agent_contexts`): older versions wrote that block
    into nested folders, so cleanup code looks there for leftovers Along wrote.
    """
    root = os.path.abspath(root)
    found: List[str] = []
    ignored = set(IGNORED_DIRS) | set(PROVIDER_DIRS)
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ignored and not d.startswith(".")]
        if "AGENTS.md" in files:
            try:
                with open(os.path.join(current, "AGENTS.md"), "r", encoding="utf-8", errors="replace") as handle:
                    if "BEGIN ALONG-PROTOCOL" in handle.read(_POINTER_SCAN_BYTES):
                        found.append(os.path.abspath(current))
            except OSError:
                continue
    return found


def find_manifest_projects(root: str,
                           manifests: Optional[Iterable[str]] = None) -> List[str]:
    """Walk `root` downwards to find subproject directories carrying package or build
    manifests, respecting IGNORED_DIRS and PROVIDER_DIRS.
    """
    root = os.path.abspath(root)
    projects = []
    ignored = set(IGNORED_DIRS) | set(PROVIDER_DIRS)
    target_manifests = set(manifests or STANDARD_MANIFESTS)

    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ignored and not d.startswith(".")]
        if current == root:
            continue
        has_manifest = any(m in files for m in target_manifests) or any(f.endswith(".csproj") for f in files)
        if has_manifest:
            projects.append(os.path.abspath(current))

    projects.sort(key=lambda p: (len(p.split(os.sep)), p))
    return projects


def resolve_llm_targets(target_dir: str, filename: str) -> List[str]:
    """Resolve target file paths for llms.txt or llms-full.txt in target_dir.

    Precedence:
    1. Candidates are target_dir/.well-known/{filename} and target_dir/{filename}.
    2. If existing files exist in either (or both) locations, return all existing files.
    3. If neither exists:
       - If target_dir/.well-known exists as a directory, return [target_dir/.well-known/{filename}].
       - Else return [target_dir/{filename}].
    """
    target_dir = os.path.abspath(target_dir)
    wk_candidate = os.path.join(target_dir, ".well-known", filename)
    root_candidate = os.path.join(target_dir, filename)

    existing = []
    if os.path.isfile(wk_candidate):
        existing.append(wk_candidate)
    if os.path.isfile(root_candidate):
        existing.append(root_candidate)

    if existing:
        return existing

    if os.path.isdir(os.path.join(target_dir, ".well-known")):
        return [wk_candidate]
    return [root_candidate]


def is_dev_repo(repo_root: Optional[str] = None) -> bool:
    """True if repo_root is the actdim-along framework development repository."""
    if not repo_root:
        repo_root = find_repo_root()
    if not repo_root:
        return False
    return bool(
        (os.path.exists(os.path.join(repo_root, "skills", "along-init", "SKILL.md")) or
         os.path.exists(os.path.join(repo_root, "skills", "init-agents", "SKILL.md"))) and
        (os.path.exists(os.path.join(repo_root, "skills", "along-version-bump", "SKILL.md")) or
         os.path.exists(os.path.join(repo_root, "skills", "along-bump-version", "SKILL.md")) or
         os.path.exists(os.path.join(repo_root, "skills", "bump-version", "SKILL.md")))
    )

