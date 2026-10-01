"""
alongkit.merge - custom git merge drivers for Along projections and entity files.

Two drivers, registered per clone by `along git setup`:

- `along-projection`: derived boards (`.along/ISSUES.md`, `.along/DECISIONS.md`,
  `.along/CONSTRAINTS.md`, `docs/INDEX.md`). Git invokes a driver BEFORE the merged
  entity files reach the working tree, and `.along/ISSUES.md` sorts before
  `.along/ISSUES/*`, so recompiling inside the driver would only reproduce the pre-merge
  "ours" board. The driver therefore keeps "ours", exits 0, and drops a per-clone marker
  in `$GIT_DIR/along-projection-resync`; `along git sync` recompiles every projection
  from the merged entity files and clears it.
- `along-frontmatter`: atomic entity files (`.along/ISSUES/**`, `.along/DECISIONS/**`).
  Performs a 3-way merge of the YAML front-matter (see `merge_frontmatter_values`) and a
  3-way text merge of the body through `git merge-file`.

Both drivers fall back to a plain `git merge-file` 3-way merge when the file is not what
they expect (not an Along projection, no parseable front-matter), so a broad `**/`
pattern in `.gitattributes` can never silently discard someone's edits.

Driver contract (gitattributes(5)): `%O` ancestor, `%A` ours (result written here),
`%B` theirs, `%P` pathname. Exit 0 = clean, non-zero = conflict left in `%A`.
"""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along git --help   (or: python scripts/along_exec.py git --help)"
    )

import os
import sys
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple

DRIVER_PROJECTION = "along-projection"
DRIVER_FRONTMATTER = "along-frontmatter"
RESYNC_MARKER = "along-projection-resync"
DRIVER_SCRIPT = "along_merge_driver.py"

#: `.gitattributes` bindings managed by `along git setup`. `**/` also covers subproject
#: `.along/` folders; the drivers themselves verify the file before acting on it.
PROJECTION_PATTERNS: Tuple[str, ...] = (
    "**/.along/ISSUES.md",
    "**/.along/CONSTRAINTS.md",
    "**/docs/INDEX.md",
)
#: Only bound when modular `.along/DECISIONS/` exists. A legacy monolithic
#: `DECISIONS.md` is the append-only ADR log itself and stays `merge=union`.
DECISIONS_BOARD_PATTERN = "**/.along/DECISIONS.md"
FRONTMATTER_PATTERNS: Tuple[str, ...] = (
    "**/.along/ISSUES/**/*.md",
    "**/.along/DECISIONS/**/*.md",
)

ATTR_BEGIN = "# >>> along git setup (managed merge drivers) >>>"
ATTR_END = "# <<< along git setup <<<"

#: Lifecycle ranks for `status`: when both sides changed it, the most advanced wins.
STATUS_RANK: Dict[str, int] = {
    "open": 0, "backlog": 0, "todo": 0, "planned": 0, "proposed": 0, "draft": 0,
    "blocked": 1,
    "in-progress": 2, "active": 2, "in_progress": 2,
    "review": 3, "accepted": 3,
    "done": 4, "completed": 4, "closed": 4, "cancelled": 4, "wontfix": 4,
    "superseded": 5, "deprecated": 5, "rejected": 5,
}
#: Date-like keys resolve to the later value.
MAX_KEYS = frozenset({"updated", "completed", "closed", "last_updated"})

_MISSING = object()


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        return handle.read()


def _write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def _log(message: str) -> None:
    sys.stderr.write(f"[Along merge] {message}\n")


def text_merge(base: str, ours: str, theirs: str, path: str = "") -> Tuple[str, bool]:
    """3-way text merge through `git merge-file -p`. Returns (merged, clean)."""
    from . import proc

    if ours == theirs:
        return ours, True
    if base == ours:
        return theirs, True
    if base == theirs:
        return ours, True

    tmp = tempfile.mkdtemp(prefix="along-merge-")
    try:
        names = []
        for label, content in (("ours", ours), ("base", base), ("theirs", theirs)):
            fname = os.path.join(tmp, label)
            _write(fname, content)
            names.append(fname)
        label = path or "file"
        result = proc.run_capture(
            ["git", "merge-file", "-p",
             "-L", f"ours:{label}", "-L", f"base:{label}", "-L", f"theirs:{label}",
             *names],
            check=False, trip_on_anomaly=False)
        if result.returncode < 0 or result.returncode > 127:
            raise RuntimeError(f"git merge-file failed: {result.stderr.strip()}")
        return result.stdout, result.returncode == 0
    finally:
        for fname in os.listdir(tmp):
            try:
                os.remove(os.path.join(tmp, fname))
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Projection driver
# ---------------------------------------------------------------------------

def is_projection(content: str, path: str) -> bool:
    """True when `content` at `path` is a compiled Along projection (safe to regenerate)."""
    name = os.path.basename(path.replace("\\", "/"))
    from . import frontmatter
    head = content.lstrip(frontmatter.BOM)[:600]
    if name == "ISSUES.md":
        return head.lstrip().startswith("# Active Issues")
    if name in ("CONSTRAINTS.md", "DECISIONS.md"):
        return "<!-- Generated projection from .along/DECISIONS" in head
    if name == "INDEX.md":
        fm, _, error = frontmatter.try_parse(content, path=path)
        return not error and fm.get("protocol") == "along" and fm.get("type") == "index"
    return False


def git_dir(cwd: Optional[str] = None) -> Optional[str]:
    """Absolute per-worktree git dir, or None outside a repository."""
    from . import proc

    result = proc.run_capture(["git", "rev-parse", "--absolute-git-dir"], cwd=cwd,
                              check=False, trip_on_anomaly=False)
    if not result.ok:
        return None
    return result.stdout.strip() or None


def mark_resync(path: str, cwd: Optional[str] = None) -> Optional[str]:
    """Record that `path` needs recompilation after the merge. Returns the marker path."""
    gdir = git_dir(cwd)
    if not gdir:
        return None
    marker = os.path.join(gdir, RESYNC_MARKER)
    existing: List[str] = []
    if os.path.isfile(marker):
        existing = [line.strip() for line in _read(marker).splitlines() if line.strip()]
    entry = path.replace("\\", "/")
    if entry not in existing:
        existing.append(entry)
    _write(marker, "\n".join(existing) + "\n")
    return marker


def pending_resync(cwd: Optional[str] = None) -> List[str]:
    """Projection paths merged by the driver and not yet recompiled."""
    gdir = git_dir(cwd)
    if not gdir:
        return []
    marker = os.path.join(gdir, RESYNC_MARKER)
    if not os.path.isfile(marker):
        return []
    return [line.strip() for line in _read(marker).splitlines() if line.strip()]


def merge_projection(base_path: str, ours_path: str, theirs_path: str, pathname: str) -> int:
    """Projection driver entry. Keeps ours and schedules a recompile; exit code for git."""
    ours = _read(ours_path)
    theirs = _read(theirs_path)
    base = _read(base_path) if os.path.isfile(base_path) else ""

    if not (is_projection(ours, pathname) or is_projection(theirs, pathname)):
        merged, clean = text_merge(base, ours, theirs, pathname)
        _write(ours_path, merged)
        _log(f"{pathname}: not an Along projection, used a standard 3-way merge"
             + ("" if clean else " (conflicts left)"))
        return 0 if clean else 1

    if ours != theirs:
        mark_resync(pathname)
        _log(f"{pathname}: projection kept as 'ours'; run `along git sync` after the merge "
             "to recompile it from the merged entity files")
    return 0


# ---------------------------------------------------------------------------
# Front-matter driver
# ---------------------------------------------------------------------------

def _plain(value: Any) -> Any:
    if value is _MISSING:
        return value
    from . import frontmatter
    return frontmatter.plain(value)


def _merge_list(base: Any, ours: list, theirs: list) -> list:
    """3-way set merge: keep ours order, drop what theirs removed, append what theirs added."""
    base_items = list(base) if isinstance(base, list) else []
    result = [item for item in ours if not (item in base_items and item not in theirs)]
    for item in theirs:
        if item not in result and item not in base_items:
            result.append(item)
    return result


def _newer(ours_fm: Dict[str, Any], theirs_fm: Dict[str, Any]) -> str:
    """'theirs' when theirs has the strictly later `updated`, else 'ours'."""
    o = str(ours_fm.get("updated") or "")
    t = str(theirs_fm.get("updated") or "")
    return "theirs" if t > o else "ours"


def merge_frontmatter_values(base: Dict[str, Any], ours: Dict[str, Any],
                             theirs: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """3-way merge of plain front-matter mappings.

    Rules, applied per key:
    - Changed on one side only: take that side (including deletions).
    - Changed on both sides to different values:
      - lists: 3-way set merge (`_merge_list`);
      - `status`: the most advanced lifecycle state (`STATUS_RANK`);
      - `updated`, `completed`, ...: the later value;
      - other scalars: the side with the newer `updated`, ties go to ours.
      - one side deleted, the other modified: keep the modification.

    Returns (merged mapping, human-readable notes on every both-sides resolution).
    """
    notes: List[str] = []
    keys: List[str] = list(ours.keys()) + [k for k in theirs.keys() if k not in ours]
    keys += [k for k in base.keys() if k not in keys]
    newer = _newer(ours, theirs)
    merged: Dict[str, Any] = {}

    for key in keys:
        b = _plain(base.get(key, _MISSING))
        o = _plain(ours.get(key, _MISSING))
        t = _plain(theirs.get(key, _MISSING))

        if o == t:
            value = o
        elif o == b:
            value = t
        elif t == b:
            value = o
        elif o is _MISSING:
            value = t
        elif t is _MISSING:
            value = o
        elif isinstance(o, list) and isinstance(t, list):
            value = _merge_list(b, o, t)
            notes.append(f"{key}: merged lists")
        elif key == "status" and str(o).lower() in STATUS_RANK and str(t).lower() in STATUS_RANK:
            value = o if STATUS_RANK[str(o).lower()] >= STATUS_RANK[str(t).lower()] else t
            notes.append(f"status: {o!r} vs {t!r} -> {value!r} (most advanced)")
        elif key in MAX_KEYS:
            value = o if str(o) >= str(t) else t
            notes.append(f"{key}: {o!r} vs {t!r} -> {value!r} (latest)")
        else:
            value = t if newer == "theirs" else o
            notes.append(f"{key}: {o!r} vs {t!r} -> {value!r} ({newer} has newer 'updated')")

        if value is not _MISSING:
            merged[key] = value
    return merged, notes


def merge_entity_text(base: str, ours: str, theirs: str,
                      pathname: str = "") -> Tuple[str, bool, List[str]]:
    """Merge a whole entity file. Returns (merged text, clean, notes).

    Falls back to a plain text merge when any side lacks a parseable front-matter block.
    The merged block is written onto "ours" through `frontmatter.update`, so key order,
    comments and quoting style of our side are preserved.
    """
    from . import frontmatter

    def _side(content: str):
        block = frontmatter.split(content) if content else None
        if block is None:
            return None, None
        fields, _, error = frontmatter.try_parse(content, path=pathname)
        return block, (None if error else fields)

    b_block, base_fm = _side(base)
    o_block, ours_fm = _side(ours)
    t_block, theirs_fm = _side(theirs)
    if o_block is None or t_block is None or ours_fm is None or theirs_fm is None:
        merged, clean = text_merge(base, ours, theirs, pathname)
        return merged, clean, ["no parseable front-matter on both sides; standard 3-way merge"]
    base_fm = base_fm or {}
    merged_fm, notes = merge_frontmatter_values(base_fm, ours_fm, theirs_fm)

    base_body = b_block.body if b_block else ""
    body, clean = text_merge(base_body, o_block.body, t_block.body, pathname)
    if not clean:
        notes.append("body: overlapping edits, conflict markers left")

    skeleton = o_block.bom + o_block.open_delim + o_block.raw + o_block.close_delim + body
    ours_plain = {str(k): frontmatter.plain(v) for k, v in ours_fm.items()}
    updates: Dict[str, Any] = {}
    for key, value in merged_fm.items():
        if ours_plain.get(key, _MISSING) != value:
            updates[key] = frontmatter.quoted(value) if key == "protocol_version" else value
    remove = [key for key in ours_plain if key not in merged_fm]
    if updates or remove:
        # Keys new to ours keep theirs' relative position when an anchor is available.
        theirs_keys = list(theirs_fm.keys())
        place_after = {}
        for key in updates:
            if key not in ours_plain and key in theirs_keys:
                idx = theirs_keys.index(key)
                if idx > 0:
                    place_after[key] = theirs_keys[idx - 1]
        result = frontmatter.update(skeleton, updates, place_after=place_after,
                                    remove=remove, path=pathname)
        if o_block.bom and not result.startswith(o_block.bom):
            result = o_block.bom + result
    else:
        result = skeleton
    return result, clean, notes


def merge_frontmatter(base_path: str, ours_path: str, theirs_path: str, pathname: str) -> int:
    """Front-matter driver entry; exit code for git."""
    base = _read(base_path) if os.path.isfile(base_path) else ""
    ours = _read(ours_path)
    theirs = _read(theirs_path)
    from . import frontmatter
    try:
        merged, clean, notes = merge_entity_text(base, ours, theirs, pathname)
    except (frontmatter.FrontmatterError, ValueError, TypeError) as exc:
        # The driver must never lose "ours": fall back to a plain text merge.
        _log(f"{pathname}: front-matter merge failed ({exc}); standard 3-way merge")
        merged, clean = text_merge(base, ours, theirs, pathname)
        notes = []
    _write(ours_path, merged)
    for note in notes:
        _log(f"{pathname}: {note}")
    return 0 if clean else 1


def run_driver(mode: str, base_path: str, ours_path: str, theirs_path: str,
               pathname: str) -> int:
    if mode == "projection":
        return merge_projection(base_path, ours_path, theirs_path, pathname)
    if mode == "frontmatter":
        return merge_frontmatter(base_path, ours_path, theirs_path, pathname)
    _log(f"unknown driver mode: {mode!r}")
    return 2


# ---------------------------------------------------------------------------
# Repository setup (`along git setup`)
# ---------------------------------------------------------------------------

def _posix(path: str) -> str:
    return os.path.abspath(path).replace("\\", "/")


def driver_command(mode: str, python: Optional[str] = None,
                   script: Optional[str] = None) -> str:
    """Shell command git runs for the driver. Absolute forward-slash paths, quoted."""
    python = python or sys.executable
    if not script:
        from . import install
        script = install.engine_script(DRIVER_SCRIPT)
    return f'"{_posix(python)}" "{_posix(script)}" {mode} %O %A %B %P'


def desired_attributes(repo_root: str) -> List[str]:
    lines = [f"{p} merge={DRIVER_PROJECTION}" for p in PROJECTION_PATTERNS]
    if os.path.isdir(os.path.join(repo_root, ".along", "DECISIONS")):
        lines.append(f"{DECISIONS_BOARD_PATTERN} merge={DRIVER_PROJECTION}")
    lines += [f"{p} merge={DRIVER_FRONTMATTER}" for p in FRONTMATTER_PATTERNS]
    return lines


def _strip_managed(text: str) -> str:
    out: List[str] = []
    inside = False
    for line in text.splitlines():
        if line.strip() == ATTR_BEGIN:
            inside = True
            continue
        if line.strip() == ATTR_END:
            inside = False
            continue
        if not inside:
            out.append(line)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out) + ("\n" if out else "")


def render_gitattributes(current: str, repo_root: str, uninstall: bool = False) -> str:
    """Return `.gitattributes` content with the managed block refreshed (or removed).

    When modular ADRs exist, a legacy `.along/DECISIONS.md merge=union` line outside the
    block is left in place; the managed block comes later in the file and git applies the
    last matching line, so the projection driver wins without editing user lines.
    """
    base = _strip_managed(current.replace("\r\n", "\n"))
    if uninstall:
        return base
    block = [ATTR_BEGIN, *desired_attributes(repo_root), ATTR_END]
    sep = "\n" if base else ""
    return base + sep + "\n".join(block) + "\n"


def _git_config(repo_root: str, *args: str):
    from . import proc
    return proc.run_capture(["git", "config", "--local", *args], cwd=repo_root,
                            check=False, trip_on_anomaly=False)


def desired_config() -> Dict[str, str]:
    return {
        f"merge.{DRIVER_PROJECTION}.name": "Along projection merge driver (keep ours, resync later)",
        f"merge.{DRIVER_PROJECTION}.driver": driver_command("projection"),
        f"merge.{DRIVER_FRONTMATTER}.name": "Along YAML front-matter 3-way merge driver",
        f"merge.{DRIVER_FRONTMATTER}.driver": driver_command("frontmatter"),
    }


def setup(repo_root: str, uninstall: bool = False, dry_run: bool = False) -> Dict[str, Any]:
    """Register (or remove) the drivers in `.git/config` and bind `.gitattributes`.

    Idempotent: re-running rewrites the same config values and the same managed block.
    Returns a report: {"git": bool, "config_changed": [...], "gitattributes_changed": bool}.
    """
    from . import textio

    report: Dict[str, Any] = {"git": False, "config_changed": [], "gitattributes_changed": False,
                              "uninstall": uninstall, "dry_run": dry_run}
    if not git_dir(repo_root):
        return report
    report["git"] = True

    for key, value in desired_config().items():
        current = _git_config(repo_root, "--get", key)
        present = current.ok
        if uninstall:
            if present:
                report["config_changed"].append(key)
                if not dry_run:
                    _git_config(repo_root, "--unset-all", key)
        elif not present or current.stdout.strip() != value:
            report["config_changed"].append(key)
            if not dry_run:
                _git_config(repo_root, "--replace-all", key, value)
    if uninstall and not dry_run:
        for driver in (DRIVER_PROJECTION, DRIVER_FRONTMATTER):
            _git_config(repo_root, "--remove-section", f"merge.{driver}")

    attr_path = os.path.join(repo_root, ".gitattributes")
    current_attrs = textio.read_text(attr_path, strict=False) if os.path.isfile(attr_path) else ""
    wanted = render_gitattributes(current_attrs, repo_root, uninstall=uninstall)
    if wanted != current_attrs.replace("\r\n", "\n"):
        report["gitattributes_changed"] = True
        if not dry_run and (wanted or os.path.isfile(attr_path)):
            textio.write_text(attr_path, wanted, newline="\n")
    return report


def status(repo_root: str) -> Dict[str, Any]:
    """Driver registration state for `along git status` and `along doctor`."""
    from . import textio

    info: Dict[str, Any] = {"git": bool(git_dir(repo_root)), "config": {}, "gitattributes": False,
                            "pending_resync": []}
    if not info["git"]:
        return info
    for key, value in desired_config().items():
        current = _git_config(repo_root, "--get", key)
        info["config"][key] = "ok" if current.ok and current.stdout.strip() == value else (
            "stale" if current.ok else "missing")
    attr_path = os.path.join(repo_root, ".gitattributes")
    if os.path.isfile(attr_path):
        text = textio.read_text(attr_path, strict=False).replace("\r\n", "\n")
        info["gitattributes"] = all(line in text.splitlines() for line in desired_attributes(repo_root))
    info["pending_resync"] = pending_resync(repo_root)
    return info


def is_configured(info: Dict[str, Any]) -> bool:
    return bool(info.get("git")) and info.get("gitattributes") is True and \
        all(v == "ok" for v in info.get("config", {}).values())


def resync(repo_root: str, kb_script: Optional[str] = None) -> List[str]:
    """Recompile every projection from the (merged) entity files and clear the marker.

    Returns the list of projections recompiled. Only the nearest `.along/` context is
    compiled here; subproject boards named in the marker are compiled from their own root.
    """
    from . import entities, proc

    done: List[str] = []
    roots = {os.path.abspath(repo_root)}
    for entry in pending_resync(repo_root):
        parts = entry.split("/")
        if ".along" in parts:
            idx = parts.index(".along")
            if idx > 0:
                roots.add(os.path.abspath(os.path.join(repo_root, *parts[:idx])))

    for root in sorted(roots):
        if not os.path.isdir(os.path.join(root, ".along")):
            continue
        entities.sync_issues_board(root)
        done.append(os.path.relpath(os.path.join(root, ".along", "ISSUES.md"), repo_root))
        if os.path.isdir(os.path.join(root, ".along", "DECISIONS")):
            entities.compile_decisions_board(root)
            entities.sync_constraints(root)
            done.append(os.path.relpath(os.path.join(root, ".along", "DECISIONS.md"), repo_root))
            done.append(os.path.relpath(os.path.join(root, ".along", "CONSTRAINTS.md"), repo_root))

    if kb_script and os.path.isdir(os.path.join(repo_root, "docs")):
        result = proc.run_capture([sys.executable, kb_script], cwd=repo_root, check=False,
                                  trip_on_anomaly=False)
        if result.ok:
            done.append("docs/INDEX.md")
        else:
            _log("kb sync failed; docs/INDEX.md not recompiled:\n" + (result.stderr or result.stdout)[-800:])

    gdir = git_dir(repo_root)
    if gdir:
        marker = os.path.join(gdir, RESYNC_MARKER)
        if os.path.isfile(marker):
            os.remove(marker)
    return [d.replace("\\", "/") for d in done]


__all__: Sequence[str] = (
    "DRIVER_PROJECTION", "DRIVER_FRONTMATTER", "RESYNC_MARKER", "STATUS_RANK",
    "text_merge", "is_projection", "merge_projection", "merge_frontmatter_values",
    "merge_entity_text", "merge_frontmatter", "run_driver", "driver_command",
    "desired_attributes", "render_gitattributes", "setup", "status", "is_configured",
    "pending_resync", "mark_resync", "resync",
)
