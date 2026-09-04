#!/usr/bin/env python3
"""
alongkit.install - the installed layout, the install manifest, and MCP registration.

`install.ps1` and `install.sh` are the bootstrap: they copy files and must keep working
on a machine that has no Python. Everything that needs to be *decided* rather than
copied lives here, once, so the two installers cannot drift apart and so the decisions
are testable. See `[bug--installer-parity-and-destructive-rules-overwrite]`.

Three decisions, and why each is here:

1. **The layout.** `planned_files()` derives every path an install writes from the
   source tree plus the provider homes. The installers copy; this module knows what
   the copy should have produced, which is what makes a parity test possible at all.
   The previous test compared skill folder NAMES, so `install.sh` shipped for months
   without installing `rules/` and nothing noticed.

2. **The manifest.** An install used to delete the destination directory before
   copying, which is how `~/.claude/rules/` - a directory the user also writes into -
   lost its contents on every run, including the runs the release engine triggered
   unasked. Recording what Along wrote makes the destructive step unnecessary: a file
   Along installed and no longer ships can be removed by name, and a file Along never
   wrote is never touched. It also gives `--uninstall` something exact to remove.

3. **MCP registration.** The installers wrote `code-review-graph` into five paths and
   printed success for all five; four of them are not read by any provider. A target
   is written only when its configuration contract is verified, an unverified one is
   reported with the path and the snippet, and a configuration file that does not
   parse is never overwritten - it is reported and left alone.
"""


from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{__name__} is a library module, not a command.\n"
        "Run: along kb-sync   (or: python scripts/along_exec.py kb-sync)"
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along-init   (or: install.ps1 / install.sh)"
    )


import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from . import entities, textio

#: Written next to the engines, in the Along user home rather than a provider home:
#: one install may touch four providers and there is exactly one manifest for it.
MANIFEST_NAME = "install-manifest.json"

#: Bumped when the manifest layout changes in a way a previous reader cannot handle.
#: A manifest from a future schema is ignored rather than misread.
MANIFEST_SCHEMA = 1

MCP_SERVER_NAME = "code-review-graph"

#: The stdio server entry, in the shape `mcpServers` uses. `uvx` resolves and caches
#: the package on first use, so no separate install step is needed.
MCP_SERVER_ENTRY = {"command": "uvx", "args": [MCP_SERVER_NAME]}

PROVIDERS: Tuple[str, ...] = ("claude", "codex", "opencode", "antigravity")

#: Only `along-*` folders are skills; anything else under `skills/` is not installed.
SKILL_PREFIX = "along-"

#: Providers that take the skill folders verbatim. OpenCode takes flat commands
#: generated from the same `SKILL.md` bodies and is handled separately.
FOLDER_PROVIDERS: Tuple[str, ...] = ("claude", "codex", "antigravity")

#: Never copied into an install: compiled caches are interpreter-specific.
EXCLUDED_DIRS = frozenset({"__pycache__"})


@dataclass(frozen=True)
class Homes:
    """Where an install writes, with every root overridable.

    Overridable because a test must be able to run a real installer without touching
    the developer's own `~/.claude`, and because `$HOME` is not the only place a
    provider may be configured.
    """

    user: str
    along: str
    claude: str
    codex: str
    opencode: str
    antigravity: str

    @classmethod
    def defaults(cls, user_home: Optional[str] = None, **overrides) -> "Homes":
        home = os.path.abspath(user_home or os.path.expanduser("~"))
        values = {
            "user": home,
            "along": os.environ.get("ALONG_HOME") or os.path.join(home, ".along"),
            "claude": os.path.join(home, ".claude"),
            "codex": os.path.join(home, ".codex"),
            "opencode": os.path.join(home, ".config", "opencode"),
            "antigravity": os.path.join(home, ".gemini", "config"),
        }
        for key, value in overrides.items():
            if value:
                values[key] = os.path.abspath(value)
        return cls(**values)

    def provider_home(self, provider: str) -> str:
        return getattr(self, provider)

    @property
    def bin(self) -> str:
        return os.path.join(self.along, "bin")


# ---------------------------------------------------------------------------
# MCP registration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class McpTarget:
    """One provider's MCP configuration file and how much we actually know about it."""

    provider: str
    path: str
    #: `mcp_servers_json` - a JSON object with an `mcpServers` map (Claude Code).
    #: `codex_toml` - a `[mcp_servers.<name>]` table in `~/.codex/config.toml`.
    #: `opencode_json` - an `mcp` map of typed entries in `opencode.json`.
    layout: str
    #: True only where the contract has been confirmed against the running provider.
    #: An unverified target is reported, not written, unless the caller opts in.
    verified: bool
    contract: str


def mcp_target(provider: str, homes: Homes) -> McpTarget:
    """The configuration file `provider` actually reads, as far as it is known.

    The paths this replaces were `~/.claude/mcp_config.json`,
    `~/.codex/mcp_config.json`, `~/.config/opencode/mcp_config.json` and
    `~/.gemini/config/mcp_config.json`. No provider reads a file by that name; the
    installer created four inert files and reported four successes.
    """
    if provider == "claude":
        return McpTarget(
            provider="claude",
            path=os.path.join(homes.user, ".claude.json"),
            layout="mcp_servers_json",
            verified=True,
            contract="Claude Code reads user-scope MCP servers from the `mcpServers` "
                     "map in ~/.claude.json.")
    if provider == "codex":
        return McpTarget(
            provider="codex",
            path=os.path.join(homes.codex, "config.toml"),
            layout="codex_toml",
            verified=False,
            contract="Codex is configured by ~/.codex/config.toml, where an MCP server "
                     "is a [mcp_servers.<name>] table. Not confirmed against a running "
                     "Codex, so it is reported rather than written.")
    if provider == "opencode":
        return McpTarget(
            provider="opencode",
            path=os.path.join(homes.opencode, "opencode.json"),
            layout="opencode_json",
            verified=False,
            contract="OpenCode is configured by opencode.json, where MCP servers are "
                     "typed entries under `mcp`. Not confirmed, so it is reported "
                     "rather than written.")
    if provider == "antigravity":
        return McpTarget(
            provider="antigravity",
            path=os.path.join(os.path.dirname(homes.antigravity), "settings.json"),
            layout="mcp_servers_json",
            verified=False,
            contract="The Gemini-family settings file carries an `mcpServers` map. "
                     "Which file Antigravity reads is not confirmed, so it is reported "
                     "rather than written.")
    raise ValueError(f"unknown provider: {provider}")


def mcp_snippet(target: McpTarget) -> str:
    """What a user would add by hand, in the layout that target expects."""
    if target.layout == "codex_toml":
        return (f"[mcp_servers.{MCP_SERVER_NAME}]\n"
                f"command = \"{MCP_SERVER_ENTRY['command']}\"\n"
                f"args = [\"{MCP_SERVER_NAME}\"]\n")
    if target.layout == "opencode_json":
        return json.dumps({"mcp": {MCP_SERVER_NAME: {
            "type": "local",
            "command": [MCP_SERVER_ENTRY["command"], MCP_SERVER_NAME],
            "enabled": True,
        }}}, indent=2)
    return json.dumps({"mcpServers": {MCP_SERVER_NAME: MCP_SERVER_ENTRY}}, indent=2)


def _load_json_config(path: str) -> Tuple[Optional[dict], Optional[str]]:
    """Existing JSON at `path`, or a reason it must not be rewritten.

    An unparseable configuration file is a reason to stop, never a reason to start
    from `{}`: the previous installer did exactly that and would have replaced a
    user's whole `~/.claude.json` with a two-key document on any read hiccup.
    """
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        return {}, None
    try:
        raw = textio.read_text(path, strict=True)
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"cannot read it ({exc.__class__.__name__})"
    try:
        data = json.loads(raw)
    except ValueError as exc:
        return None, f"it is not valid JSON ({exc})"
    if not isinstance(data, dict):
        return None, "its top level is not a JSON object"
    return data, None


def register_mcp(target: McpTarget, *, include_unverified: bool = False,
                 dry_run: bool = False) -> Tuple[str, str]:
    """Register `code-review-graph` in `target`.

    Returns `(status, message)` where status is one of `registered`, `present`,
    `skipped` or `failed`. Nothing here raises: a provider that cannot be configured
    must not abort an install, but it must also never be reported as configured.
    """
    if not target.verified and not include_unverified:
        return "skipped", (
            f"{target.provider}: not written. {target.contract}\n"
            f"      path: {target.path}\n"
            f"      add it by hand, or re-run with the unverified targets enabled.")

    data, refusal = (None, None)
    if target.layout in ("mcp_servers_json", "opencode_json"):
        data, refusal = _load_json_config(target.path)
        if refusal:
            return "failed", f"{target.provider}: left {target.path} alone - {refusal}."

    if target.layout == "codex_toml":
        return _register_codex_toml(target, dry_run=dry_run)

    assert data is not None
    if target.layout == "opencode_json":
        section = data.setdefault("mcp", {})
        entry = {"type": "local",
                 "command": [MCP_SERVER_ENTRY["command"], MCP_SERVER_NAME],
                 "enabled": True}
    else:
        section = data.setdefault("mcpServers", {})
        entry = dict(MCP_SERVER_ENTRY)
    if not isinstance(section, dict):
        return "failed", (f"{target.provider}: left {target.path} alone - its MCP "
                          f"section is not an object.")
    if MCP_SERVER_NAME in section:
        return "present", f"{target.provider}: already configured in {target.path}."
    section[MCP_SERVER_NAME] = entry
    if dry_run:
        return "registered", f"{target.provider}: would register in {target.path}."
    try:
        textio.write_text(target.path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    except OSError as exc:
        return "failed", f"{target.provider}: could not write {target.path} ({exc})."
    return "registered", f"{target.provider}: registered in {target.path}."


def _register_codex_toml(target: McpTarget, *, dry_run: bool = False) -> Tuple[str, str]:
    """Append a `[mcp_servers.<name>]` table, or report that one is already there.

    Appending a table header at the end of a TOML document is always valid: a header
    closes whatever table preceded it. Nothing existing is parsed or rewritten.
    """
    existing = ""
    if os.path.isfile(target.path):
        try:
            existing = textio.read_text(target.path, strict=True)
        except (OSError, UnicodeDecodeError) as exc:
            return "failed", (f"{target.provider}: left {target.path} alone - cannot "
                              f"read it ({exc.__class__.__name__}).")
    pattern = re.compile(r"^\s*\[mcp_servers\.[\"']?" + re.escape(MCP_SERVER_NAME)
                         + r"[\"']?\]", re.MULTILINE)
    if pattern.search(existing):
        return "present", f"{target.provider}: already configured in {target.path}."
    if dry_run:
        return "registered", f"{target.provider}: would register in {target.path}."
    newline = textio.detect_newline(existing) if existing else os.linesep
    block = mcp_snippet(target)
    prefix = "" if (not existing or existing.endswith("\n")) else "\n"
    body = existing + prefix + "\n" + block
    try:
        textio.write_text(target.path, body, newline=newline)
    except OSError as exc:
        return "failed", f"{target.provider}: could not write {target.path} ({exc})."
    return "registered", f"{target.provider}: registered in {target.path}."


def configure_mcp(providers: Sequence[str], homes: Homes, *,
                  include_unverified: bool = False,
                  dry_run: bool = False) -> List[dict]:
    """Register the MCP server for each provider, reporting one result per provider."""
    report = []
    for provider in providers:
        target = mcp_target(provider, homes)
        status, message = register_mcp(target, include_unverified=include_unverified,
                                       dry_run=dry_run)
        report.append({"provider": provider, "path": target.path,
                       "verified": target.verified, "status": status,
                       "message": message})
    return report


# ---------------------------------------------------------------------------
# The installed layout
# ---------------------------------------------------------------------------

def walk_tree(root: str, suffixes: Iterable[str] = ()) -> List[str]:
    """Every file under `root`, sorted, skipping compiled caches.

    Deliberately not `repo.iter_files`: that walker skips `bin/` and every dot
    directory, which is precisely where an install writes.
    """
    wanted = tuple(suffixes)
    found: List[str] = []
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS)
        for name in sorted(files):
            if wanted and not name.endswith(wanted):
                continue
            found.append(os.path.join(current, name))
    return found


def source_skills(source_root: str) -> List[str]:
    """The skill folder names an install would deploy."""
    skills_dir = os.path.join(source_root, "skills")
    if not os.path.isdir(skills_dir):
        return []
    return sorted(name for name in os.listdir(skills_dir)
                  if name.startswith(SKILL_PREFIX)
                  and os.path.isdir(os.path.join(skills_dir, name)))


def _copy_pairs(source_dir: str, dest_dir: str,
                suffixes: Iterable[str] = ()) -> Dict[str, str]:
    """`{destination: source}` for a recursive copy of `source_dir` into `dest_dir`."""
    if not os.path.isdir(source_dir):
        return {}
    pairs = {}
    for path in walk_tree(source_dir, suffixes):
        rel = os.path.relpath(path, source_dir)
        pairs[os.path.join(dest_dir, rel)] = path
    return pairs


def engine_files(source_root: str) -> Dict[str, str]:
    """`{relative destination: source}` for the engines plus the shared package.

    The package travels with the engines because they import `alongkit` from their own
    directory; a `*.py`-only copy produces an install where every engine dies on
    ModuleNotFoundError.
    """
    scripts_dir = os.path.join(source_root, "scripts")
    if not os.path.isdir(scripts_dir):
        return {}
    pairs = {}
    for name in sorted(os.listdir(scripts_dir)):
        path = os.path.join(scripts_dir, name)
        if os.path.isfile(path) and name.endswith(".py"):
            pairs[name] = path
    package = os.path.join(scripts_dir, "alongkit")
    for path in walk_tree(package, (".py",)):
        pairs[os.path.join("alongkit", os.path.relpath(path, package))] = path
    return pairs


def planned_files(source_root: str, homes: Homes,
                  providers: Sequence[str] = PROVIDERS) -> Dict[str, str]:
    """Every path an install of `providers` writes, mapped to what it came from.

    A generated file (an OpenCode command) maps to the `SKILL.md` it is generated
    from. `config.json` is absent on purpose: it is seeded once and then belongs to
    the user, so it is neither pruned nor uninstalled.
    """
    plan: Dict[str, str] = {}
    plan.update({os.path.join(homes.bin, rel): src
                 for rel, src in engine_files(source_root).items()})

    skills_dir = os.path.join(source_root, "skills")
    rules_dir = os.path.join(source_root, "rules")
    skills = source_skills(source_root)
    
    plan.update(_copy_pairs(rules_dir, os.path.join(homes.along, "rules")))

    for provider in providers:
        if provider in FOLDER_PROVIDERS:
            home = homes.provider_home(provider)
            for skill in skills:
                plan.update(_copy_pairs(os.path.join(skills_dir, skill),
                                        os.path.join(home, "skills", skill)))
        elif provider == "opencode":
            commands = os.path.join(homes.opencode, "commands")
            helper = os.path.join(homes.opencode, "actdim-along")
            for skill in skills:
                manifest = os.path.join(skills_dir, skill, "SKILL.md")
                if os.path.isfile(manifest):
                    plan[os.path.join(commands, skill + ".md")] = manifest
            plan.update({os.path.join(helper, rel): src
                         for rel, src in engine_files(source_root).items()})
            protocol = os.path.join(skills_dir, "along-init", "protocol.md")
            if os.path.isfile(protocol):
                plan[os.path.join(helper, "protocol.md")] = protocol
    return plan


def owned_roots(homes: Homes, providers: Sequence[str]) -> List[str]:
    """The directories this install run is allowed to delete stale files from.

    Scoped to the providers actually being installed. Installing only Claude after a
    full install must not prune the Codex tree: from this run's point of view every
    Codex file is stale, and deleting them would uninstall a provider the user never
    mentioned.
    """
    roots = [homes.bin, os.path.join(homes.along, "rules")]
    for provider in providers:
        if provider in FOLDER_PROVIDERS:
            home = homes.provider_home(provider)
            roots.append(os.path.join(home, "skills"))
        elif provider == "opencode":
            roots.append(os.path.join(homes.opencode, "commands"))
            roots.append(os.path.join(homes.opencode, "actdim-along"))
    return roots


# ---------------------------------------------------------------------------
# The manifest
# ---------------------------------------------------------------------------

def manifest_path(along_home: str) -> str:
    return os.path.join(along_home, MANIFEST_NAME)


def path_key(path: str) -> str:
    """A manifest key: absolute, forward slashes, readable on both platforms."""
    return os.path.abspath(path).replace("\\", "/")


def same_path(left: str, right: str) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def under(path: str, root: str) -> bool:
    """True when `path` is inside `root`, case-folded where the platform folds."""
    root_abs = os.path.normcase(os.path.abspath(root)) + os.sep
    return os.path.normcase(os.path.abspath(path)).startswith(root_abs)


def file_digest(path: str) -> str:
    """Content hash, so a re-install can say what actually changed."""
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()[:16]


def read_manifest(along_home: str) -> dict:
    """The manifest of the previous install, or an empty one."""
    path = manifest_path(along_home)
    if not os.path.isfile(path):
        return {}
    try:
        data = json.loads(textio.read_text(path, strict=True))
    except (OSError, ValueError, UnicodeDecodeError):
        return {}
    if not isinstance(data, dict) or data.get("schema", 0) > MANIFEST_SCHEMA:
        return {}
    return data


def write_manifest(along_home: str, payload: dict) -> str:
    path = manifest_path(along_home)
    textio.write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return path


def is_link(path: str) -> bool:
    """True for a symlink and for a Windows directory junction.

    `os.path.islink` reports False for a junction: it is a reparse point of a
    different type. The installer's symlink fallback creates junctions (`mklink /J`
    needs no elevation, unlike a symlink), so a check that misses them would record
    the repository's own files as installed - and uninstalling would delete the
    checkout through the link.
    """
    if os.path.islink(path):
        return True
    try:
        attributes = os.lstat(path).st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attributes & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT


def symlink_ancestor(path: str, roots: Sequence[str]) -> Optional[str]:
    """The outermost symlinked directory between `path` and the root that owns it.

    `install.sh --symlink` / `install.ps1 -Symlink` link a skill folder instead of
    copying it, so the files under the destination ARE the repository's own files.
    Recording them individually would make an uninstall delete the source checkout.
    The link is recorded instead, and removing the link removes the install.
    """
    root = next((r for r in roots if under(path, r)), None)
    if root is None:
        return None
    root_abs = os.path.abspath(root)
    current = os.path.dirname(os.path.abspath(path))
    found = None
    while under(current, root_abs) or same_path(current, root_abs):
        if is_link(current):
            found = current
        if same_path(current, root_abs):
            break
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return found


def remove_file(path: str, stop_at: Optional[str] = None) -> bool:
    """Delete one file or link, and any directory it leaves empty, up to `stop_at`."""
    try:
        os.remove(path)
    except OSError:
        # A directory symlink or junction: `os.remove` refuses on Windows, `os.rmdir`
        # unlinks it without following it. Never `shutil.rmtree`, which would delete
        # whatever the link points at - here, the repository the install came from.
        if is_link(path) or os.path.isdir(path):
            try:
                os.rmdir(path)
            except OSError:
                return False
        else:
            return False
    parent = os.path.dirname(os.path.abspath(path))
    limit = os.path.abspath(stop_at) if stop_at else None
    while parent and (limit is None or under(parent, limit)):
        try:
            if os.listdir(parent):
                break
            os.rmdir(parent)
        except OSError:
            break
        parent = os.path.dirname(parent)
    return True


def sync_manifest(source_root: str, homes: Homes, providers: Sequence[str],
                  version_string: str, *, prune: bool = True,
                  dry_run: bool = False) -> dict:
    """Record what this install put on disk, and remove what it no longer ships.

    The pruning is the point. It is what makes deleting a destination directory
    unnecessary, and therefore what keeps a user's own files in `~/.claude/rules/`
    alive across an install.
    """
    previous = read_manifest(homes.along)
    previous_files: Dict[str, str] = dict(previous.get("files") or {})
    plan = planned_files(source_root, homes, providers)
    roots = owned_roots(homes, providers)

    present: Dict[str, str] = {}
    missing: List[str] = []
    for dest in sorted(plan):
        link = symlink_ancestor(dest, roots)
        if link is not None:
            present.setdefault(path_key(link), "symlink")
            continue
        key = path_key(dest)
        if os.path.isfile(dest):
            present[key] = file_digest(dest)
        elif key not in missing:
            missing.append(key)

    added = [key for key in present if key not in previous_files]
    changed = [key for key in present
               if key in previous_files and previous_files[key] != present[key]]
    unchanged = [key for key in present
                 if key in previous_files and previous_files[key] == present[key]]

    stale = [key for key in previous_files
             if key not in present
             and any(under(key, root) for root in roots)]
    removed: List[str] = []
    if prune and not dry_run:
        for key in sorted(stale):
            if os.path.lexists(key):
                root = next((r for r in roots if under(key, r)), None)
                if remove_file(key, stop_at=root):
                    removed.append(key)
            else:
                removed.append(key)
    elif stale:
        removed = sorted(stale)

    kept = {key: digest for key, digest in previous_files.items()
            if key not in stale and key not in present}
    payload = {
        "schema": MANIFEST_SCHEMA,
        "version": version_string,
        "updated": entities.today_iso(),
        "source": path_key(source_root),
        "providers": list(providers),
        "homes": {"along": path_key(homes.along),
                  **{name: path_key(homes.provider_home(name)) for name in PROVIDERS}},
        "files": dict(sorted({**kept, **present}.items())),
    }
    manifest = ""
    if not dry_run:
        manifest = write_manifest(homes.along, payload)

    return {
        "manifest": manifest or manifest_path(homes.along),
        "version": version_string,
        "providers": list(providers),
        "installed": len(present),
        "added": len(added),
        "changed": len(changed),
        "unchanged": len(unchanged),
        "removed": sorted(removed),
        "missing": missing,
        "dry_run": dry_run,
    }


def uninstall(along_home: str, *, dry_run: bool = False) -> dict:
    """Remove exactly the files the manifest records, and nothing else.

    Not a directory tree removal: the provider homes hold the user's own skills,
    rules and configuration, and an uninstall that cannot tell them apart is a
    slower version of the bug this whole change exists to fix.
    """
    manifest = read_manifest(along_home)
    files = sorted((manifest.get("files") or {}).keys())
    homes_recorded = manifest.get("homes") or {}
    stops = [value for value in homes_recorded.values() if value]

    removed: List[str] = []
    absent: List[str] = []
    failed: List[str] = []
    for key in files:
        if not os.path.lexists(key):
            absent.append(key)
            continue
        if dry_run:
            removed.append(key)
            continue
        stop = next((s for s in stops if under(key, s)), None)
        if remove_file(key, stop_at=stop):
            removed.append(key)
        else:
            failed.append(key)

    path = manifest_path(along_home)
    if files and not dry_run and not failed and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            failed.append(path_key(path))

    return {
        "manifest": path_key(path),
        "recorded": len(files),
        "removed": removed,
        "absent": absent,
        "failed": failed,
        "dry_run": dry_run,
    }
