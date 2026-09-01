#!/usr/bin/env python3
"""
alongkit.migration - non-destructive primitives for the protocol migration engine.

`migrate_protocol.py` moved legacy `.agents/` content into `.along/` by deleting
whatever already occupied the destination:

    if os.path.exists(dst):
        os.remove(dst)          # destination content destroyed
    shutil.move(src, dst)

A repository that had both a legacy `.agents/` and an already-started `.along/` (a
partial migration, or two developers migrating on different branches) therefore lost
the newer `DECISIONS.md` and `HISTORY.md` in favour of the stale legacy copies. Both
files are append-only by protocol, so the loss was irreversible. See
`[bug--migration-deletes-destination-without-backup]`.

This module holds the three things that were missing, so the engine reads as a
sequence of intentions rather than of file operations:

- `Migration` records every intention and either performs it or, in dry-run mode,
  only prints it. Nothing else in the engine calls `shutil` or `os.remove`.
- `adopt` never deletes a destination. What happens on a collision is decided by
  `classify`, per file class, and every outcome keeps both bodies on disk.
- `ensure_backup` copies the whole state directory aside before the first
  modification of an existing file, and says where it went.

The transaction in `alongkit.transaction` covers a mutation that must be undone in
full when a later step fails. A migration is not that: it is expected to be run,
inspected, and re-run, so it needs a durable copy on disk rather than an in-memory
snapshot that dies with the process.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

from . import repo, textio

#: Append-only by protocol: two branches append different entries to the same file and
#: `.gitattributes` declares `merge=union` for exactly this reason. A migration must do
#: what git would do, not pick a winner.
APPEND_ONLY_FILES = ("DECISIONS.md", "HISTORY.md")

#: Derived projections. They are recompiled from the entity files by
#: `/along-issue-sync` and `/along-kb-sync`, so a legacy copy carries no information
#: the sources do not already have.
PROJECTION_FILES = ("ISSUES.md", "DASHBOARD.md", "dashboard.html", "INDEX.md")

#: Where the pre-migration copy of the state directory goes, relative to `.along/`.
BACKUP_DIRNAME = ".migration-backup"

#: Records the protocol version the repository was last migrated to, inside `.along/`.
STATE_FILENAME = ".protocol-version"

#: Infix given to a legacy file preserved next to the destination it collided with.
LEGACY_INFIX = ".legacy"

APPEND_ONLY = "append-only"
PROJECTION = "projection"
CONTENT = "content"


def classify(path: str) -> str:
    """Which collision policy governs `path`, by file name alone.

    Name-based on purpose: the policy has to be decidable for a destination that is
    about to be overwritten, before anything reads either body.
    """
    name = os.path.basename(path)
    if name in APPEND_ONLY_FILES:
        return APPEND_ONLY
    if name in PROJECTION_FILES:
        return PROJECTION
    return CONTENT


def sidecar_path(destination: str) -> str:
    """A free path next to `destination` for the legacy copy that collided with it.

    `.along/ISSUES/bug--x.md` yields `.along/ISSUES/bug--x.legacy.md`, and a second
    collision yields `bug--x.legacy-2.md` rather than overwriting the first.
    """
    stem, ext = os.path.splitext(destination)
    candidate = f"{stem}{LEGACY_INFIX}{ext}"
    counter = 2
    while os.path.exists(candidate):
        candidate = f"{stem}{LEGACY_INFIX}-{counter}{ext}"
        counter += 1
    return candidate


def _split_sections(text: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Preamble plus `## ` sections, each as (heading line, full section text)."""
    lines = text.splitlines(keepends=True)
    preamble: List[str] = []
    sections: List[Tuple[str, List[str]]] = []
    for line in lines:
        if line.startswith("## "):
            sections.append((line.strip(), [line]))
        elif sections:
            sections[-1][1].append(line)
        else:
            preamble.append(line)
    return "".join(preamble), [(head, "".join(body)) for head, body in sections]


def union_merge(destination: str, legacy: str) -> Tuple[str, int]:
    """Merge `legacy` into `destination`, keeping everything both of them say.

    Section-wise when the file is built from `## ` headings (`DECISIONS.md`, where a
    section is one ADR), line-wise otherwise (`HISTORY.md`, where an entry is one
    line). The destination keeps its own order; whatever the legacy copy has and the
    destination lacks is appended after it. Returns the merged text and how many
    entries were adopted.

    Appending rather than interleaving is deliberate: an ADR slug header and a history
    line both carry their own date, so the reader can order them, while a merge that
    tried to interleave would have to guess at entries whose dates tie.
    """
    if not destination.strip():
        return legacy, 0
    if not legacy.strip():
        return destination, 0

    newline = textio.detect_newline(destination)
    dst_preamble, dst_sections = _split_sections(destination)

    if dst_sections:
        _, src_sections = _split_sections(legacy)
        known = {head for head, _ in dst_sections}
        adopted = [body for head, body in src_sections if head not in known]
        if not adopted:
            return destination, 0
        merged = dst_preamble + "".join(body for _, body in dst_sections)
        if not merged.endswith(("\n", "\r")):
            merged += newline
        return merged + newline + "".join(adopted), len(adopted)

    dst_lines = destination.splitlines()
    known = {line.strip() for line in dst_lines if line.strip()}
    adopted = []
    for line in legacy.splitlines():
        stripped = line.strip()
        if not stripped or stripped in known:
            continue
        known.add(stripped)
        adopted.append(line)
    if not adopted:
        return destination, 0
    body = destination
    if not body.endswith(("\n", "\r")):
        body += newline
    return body + newline.join(adopted) + newline, len(adopted)


def read_state(state_dir: str) -> Optional[str]:
    """The protocol version this repository was last migrated to, if it is recorded."""
    path = os.path.join(state_dir, STATE_FILENAME)
    if not os.path.isfile(path):
        return None
    try:
        return textio.read_text(path).strip() or None
    except (OSError, UnicodeDecodeError):
        return None


@dataclass
class PlannedOp:
    """One intention: what would happen, to what, and why."""

    action: str
    target: str
    detail: str = ""

    def render(self) -> str:
        return f"{self.action}: {self.target}" + (f" ({self.detail})" if self.detail else "")


@dataclass
class Conflict:
    """A collision the migration resolved without discarding either side."""

    destination: str
    resolution: str
    detail: str = ""


class Migration:
    """Every file mutation the migration engine makes, recorded and reversible.

    In dry-run mode nothing touches the disk: each call records what it would do and
    returns the same value it would have returned, so the caller's control flow is
    identical in both modes and a plan cannot drift from the execution it describes.
    """

    def __init__(self, repo_root: str, *, dry_run: bool, state_dir: Optional[str] = None,
                 backup: bool = True, printer: Callable[[str], None] = print):
        self.repo_root = os.path.abspath(repo_root)
        self.dry_run = dry_run
        self.state_dir = state_dir or os.path.join(self.repo_root, ".along")
        self.plan: List[PlannedOp] = []
        self.conflicts: List[Conflict] = []
        self.skipped: List[Tuple[str, str]] = []
        self.backup_dir: Optional[str] = None
        self._backup_enabled = backup
        self._backup_done = False
        self._print = printer

    # -- recording ---------------------------------------------------------

    def rel(self, path: str) -> str:
        return repo.normalize_posix(repo.safe_relpath(path, self.repo_root))

    def record(self, action: str, target: str, detail: str = "",
               announce: bool = True) -> PlannedOp:
        """Note one intention, printing it when it is worth a line of output."""
        op = PlannedOp(action=action, target=self.rel(target), detail=detail)
        self.plan.append(op)
        if announce:
            self._print(f"   [{'would' if self.dry_run else 'done'}] {op.render()}")
        return op

    def note_skipped(self, path: str, reason: str) -> None:
        """A file the migration deliberately did not touch, and why."""
        self.skipped.append((self.rel(path), reason))

    def count(self, action: str) -> int:
        return sum(1 for op in self.plan if op.action == action)

    # -- backup ------------------------------------------------------------

    def ensure_backup(self) -> Optional[str]:
        """Copy the state directories aside before the first modification.

        Called by every method that changes an existing file, so the guarantee holds
        without each call site remembering it. Idempotent: one backup per run.
        """
        if self._backup_done or not self._backup_enabled:
            return self.backup_dir
        self._backup_done = True
        stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        self.backup_dir = os.path.join(self.state_dir, BACKUP_DIRNAME, stamp)
        sources = [path for path in (self.state_dir,
                                     os.path.join(self.repo_root, ".agents"))
                   if os.path.isdir(path)]
        if not sources:
            self.backup_dir = None
            self._print("   [note] nothing to back up yet; no state directory exists.")
            return None
        if self.dry_run:
            self._print(f"   [would] back up {', '.join(self.rel(s) for s in sources)} "
                        f"to {self.rel(self.backup_dir)}")
            return self.backup_dir
        os.makedirs(self.backup_dir, exist_ok=True)
        # The backup lives inside `.along/`, so it must exclude itself from its own copy
        # and keep itself out of the user's history without editing their `.gitignore`.
        textio.write_text(os.path.join(self.state_dir, BACKUP_DIRNAME, ".gitignore"), "*\n")
        for source in sources:
            shutil.copytree(source, os.path.join(self.backup_dir, os.path.basename(source)),
                            ignore=shutil.ignore_patterns(BACKUP_DIRNAME),
                            dirs_exist_ok=True)
        self._print(f"   [backup] {', '.join(self.rel(s) for s in sources)} -> "
                    f"{self.rel(self.backup_dir)}")
        return self.backup_dir

    # -- primitive mutations -----------------------------------------------

    def makedirs(self, path: str, announce: bool = False) -> None:
        if os.path.isdir(path):
            return
        if not self.dry_run:
            os.makedirs(path, exist_ok=True)
        self.record("create directory", path, announce=announce)

    def touch(self, path: str) -> None:
        """Create an empty marker file (`.gitkeep`) if it is absent."""
        if os.path.exists(path):
            return
        if not self.dry_run:
            with open(path, "a", encoding="utf-8"):
                pass
        self.record("create", path, announce=False)

    def write(self, path: str, text: str, *, newline: Optional[str] = None,
              detail: str = "", announce: bool = False) -> None:
        """Write `path`, backing up the state directory first if it already exists."""
        existed = os.path.isfile(path)
        if existed:
            try:
                if textio.read_text(path) == text:
                    return
            except (OSError, UnicodeDecodeError):
                pass
            self.ensure_backup()
        if not self.dry_run:
            textio.write_text(path, text, newline=newline)
        self.record("update" if existed else "create", path, detail, announce=announce)

    def discard(self, path: str, reason: str) -> None:
        """Delete a path the protocol no longer recognizes, after backing it up."""
        if not os.path.exists(path):
            return
        self.ensure_backup()
        if not self.dry_run:
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                os.remove(path)
        self.record("remove", path, reason)

    def move(self, src: str, dst: str, detail: str = "") -> None:
        """Move `src` onto a destination that does not exist."""
        if not self.dry_run:
            parent = os.path.dirname(dst)
            if parent:
                os.makedirs(parent, exist_ok=True)
            shutil.move(src, dst)
        self.record("move", dst, detail or f"from {self.rel(src)}")

    def rmdir_if_empty(self, path: str) -> bool:
        """Remove `path` only when it holds no files; report whether it went."""
        if not os.path.isdir(path):
            return False
        remaining = [os.path.join(root, name)
                     for root, _, files in os.walk(path) for name in files]
        if remaining:
            self.record("keep", path, f"{len(remaining)} file(s) not owned by Along")
            return False
        if not self.dry_run:
            shutil.rmtree(path, ignore_errors=True)
        self.record("remove", path, "empty legacy directory")
        return True

    # -- collision policy --------------------------------------------------

    def adopt(self, src: str, dst: str) -> str:
        """Bring a legacy file to its destination without ever deleting the destination.

        Returns the resolution: `moved`, `merged`, `discarded-legacy`, or `preserved`.
        """
        if not os.path.exists(src):
            return "absent"
        if not os.path.exists(dst):
            self.move(src, dst)
            return "moved"

        kind = classify(dst)
        if kind == APPEND_ONLY:
            try:
                merged, adopted = union_merge(textio.read_text(dst), textio.read_text(src))
            except UnicodeDecodeError as exc:
                self.note_skipped(src, f"not valid UTF-8 ({exc.reason})")
                return self._preserve(src, dst, "undecodable legacy copy kept aside")
            self.ensure_backup()
            if not self.dry_run:
                textio.write_text(dst, merged)
                os.remove(src)
            self.record("merge", dst, f"{adopted} entry(ies) adopted from {self.rel(src)}")
            self.conflicts.append(Conflict(self.rel(dst), "union merge",
                                           f"{adopted} entry(ies) adopted"))
            return "merged"

        if kind == PROJECTION:
            self.ensure_backup()
            if not self.dry_run:
                os.remove(src)
            self.record("discard legacy", src,
                        "derived projection; recompile with /along-issue-sync or /along-kb-sync")
            self.conflicts.append(Conflict(self.rel(dst), "kept destination",
                                           "legacy projection discarded, recompile it"))
            return "discarded-legacy"

        return self._preserve(src, dst, "destination kept")

    def _preserve(self, src: str, dst: str, why: str) -> str:
        sidecar = sidecar_path(dst)
        self.move(src, sidecar, f"collision with {self.rel(dst)}; {why}")
        self.conflicts.append(Conflict(self.rel(dst), "kept destination",
                                       f"legacy copy preserved as {self.rel(sidecar)}"))
        return "preserved"

    def adopt_tree(self, src_dir: str, dst_dir: str) -> Dict[str, int]:
        """`adopt` every file under `src_dir` into `dst_dir`, then drop the empty source."""
        outcomes: Dict[str, int] = {}
        if not os.path.isdir(src_dir):
            return outcomes
        if not os.path.exists(dst_dir):
            self.move(src_dir, dst_dir)
            outcomes["moved"] = 1
            return outcomes
        for root, _, files in os.walk(src_dir):
            relative = os.path.relpath(root, src_dir)
            target_dir = dst_dir if relative == "." else os.path.join(dst_dir, relative)
            self.makedirs(target_dir)
            for name in sorted(files):
                outcome = self.adopt(os.path.join(root, name), os.path.join(target_dir, name))
                outcomes[outcome] = outcomes.get(outcome, 0) + 1
        self.rmdir_if_empty(src_dir)
        return outcomes

    # -- state -------------------------------------------------------------

    def record_state(self, version: str) -> None:
        """Persist the protocol version this repository has now been migrated to."""
        self.write(os.path.join(self.state_dir, STATE_FILENAME), f"{version}\n",
                   detail=f"migrated to v{version}", announce=True)

    # -- reporting ---------------------------------------------------------

    def summary(self) -> List[str]:
        """The plan, grouped by action, plus every conflict and every skipped file."""
        lines: List[str] = []
        counts: Dict[str, int] = {}
        for op in self.plan:
            counts[op.action] = counts.get(op.action, 0) + 1
        if counts:
            lines.append("Planned operations:" if self.dry_run else "Operations performed:")
            for action in sorted(counts):
                lines.append(f"   {counts[action]:>4}  {action}")
        else:
            lines.append("Nothing to do; the repository is already current.")
        if self.dry_run and self.plan:
            lines.append("Full operation list:")
            lines.extend(f"   {op.render()}" for op in self.plan)
        if self.conflicts:
            lines.append("Collisions resolved without discarding content:")
            for conflict in self.conflicts:
                lines.append(f"   {conflict.destination}: {conflict.resolution}"
                             + (f" ({conflict.detail})" if conflict.detail else ""))
        if self.skipped:
            lines.append("Files skipped:")
            lines.extend(f"   {path}: {reason}" for path, reason in self.skipped)
        if self.backup_dir:
            verb = "would be written to" if self.dry_run else "written to"
            lines.append(f"Backup {verb} {self.rel(self.backup_dir)}")
        return lines
