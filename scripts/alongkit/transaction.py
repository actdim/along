#!/usr/bin/env python3
"""
alongkit.transaction - byte-exact rollback around a multi-file mutation.

Written for the release engine, which used to bump the version, rewrite the tree,
flip milestone files, and only then run the tests it was supposed to be gated by.
When those tests failed it printed "Release aborted" and exited, leaving every one
of those edits on disk with no way back. See
`[bug--release-engine-mutates-before-tests-and-reinstalls-globals]`.

The contract is deliberately small:

- `protect(path)` snapshots a file's exact bytes (or records that it did not exist)
  before anything writes to it. Called twice for the same path, it keeps the first
  snapshot, so the state restored is always the pre-transaction one.
- `write(path, text)` protects and then writes.
- `rollback()` puts every protected path back, byte for byte, removes files the
  transaction created, and returns what it restored so the caller can report it.
- `commit()` gives up the ability to roll back. Call it once the operation has
  reached a point no longer safe to undo (a created git commit, for instance):
  after that a rollback would destroy more than it repairs.

Bytes, not decoded text: a rollback must be able to restore a file the sanitizer
would refuse to touch, and re-encoding is a change the caller never asked for.

A mutation this module cannot undo (a child process writing paths it does not
report) is recorded with `mark_unrestorable()` and named in the rollback report,
because a partial rollback the user is not told about is worse than none.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from . import repo, textio


class FileTransaction:
    """Records the prior state of every file an operation is about to change."""

    def __init__(self, root: str, label: str = "operation"):
        self.root = os.path.abspath(root)
        self.label = label
        self._before: Dict[str, Optional[bytes]] = {}
        self._made_dirs: List[str] = []
        self._unrestorable: List[str] = []
        self._finalized = False

    # -- recording ---------------------------------------------------------

    def protect(self, path: str) -> None:
        """Snapshot `path` before it is written. Idempotent per path."""
        target = os.path.abspath(path)
        if target in self._before:
            return
        if os.path.isfile(target):
            with open(target, "rb") as handle:
                self._before[target] = handle.read()
        else:
            self._before[target] = None
            self._record_missing_dirs(target)

    def write(self, path: str, text: str, *, newline: Optional[str] = None) -> None:
        """`textio.write_text` with the prior state recorded first."""
        self.protect(path)
        textio.write_text(path, text, newline=newline)

    def mark_unrestorable(self, description: str) -> None:
        """Note a mutation this transaction cannot undo, for the rollback report."""
        if description not in self._unrestorable:
            self._unrestorable.append(description)

    def _record_missing_dirs(self, target: str) -> None:
        """Remember directories that do not exist yet, so a rollback can remove them."""
        directory = os.path.dirname(target)
        missing = []
        while directory and not os.path.isdir(directory):
            missing.append(directory)
            parent = os.path.dirname(directory)
            if parent == directory:
                break
            directory = parent
        for candidate in reversed(missing):
            if candidate not in self._made_dirs:
                self._made_dirs.append(candidate)

    # -- reporting ---------------------------------------------------------

    @property
    def unrestorable(self) -> List[str]:
        return list(self._unrestorable)

    def changed(self) -> List[str]:
        """Repository-relative paths whose bytes differ from their snapshot."""
        out = []
        for target, before in sorted(self._before.items()):
            after: Optional[bytes] = None
            if os.path.isfile(target):
                with open(target, "rb") as handle:
                    after = handle.read()
            if after != before:
                out.append(repo.safe_relpath(target, self.root))
        return out

    # -- outcome -----------------------------------------------------------

    def rollback(self) -> List[str]:
        """Restore every protected path and return what was actually put back."""
        if self._finalized:
            return []
        restored = []
        for target, before in sorted(self._before.items()):
            rel = repo.safe_relpath(target, self.root)
            try:
                if before is None:
                    if os.path.isfile(target):
                        os.remove(target)
                        restored.append(f"{rel} (removed, did not exist)")
                    continue
                current: Optional[bytes] = None
                if os.path.isfile(target):
                    with open(target, "rb") as handle:
                        current = handle.read()
                if current == before:
                    continue
                directory = os.path.dirname(target)
                if directory:
                    os.makedirs(directory, exist_ok=True)
                with open(target, "wb") as handle:
                    handle.write(before)
                restored.append(rel)
            except OSError as exc:
                # Reported, never swallowed: a path that could not be restored is
                # exactly what the caller has to tell the user about.
                self.mark_unrestorable(f"{rel}: {exc}")

        for directory in sorted(self._made_dirs, key=len, reverse=True):
            try:
                if os.path.isdir(directory) and not os.listdir(directory):
                    os.rmdir(directory)
            except OSError:
                pass

        self._before.clear()
        self._made_dirs.clear()
        return restored

    def commit(self) -> None:
        """Give up the ability to roll back; the operation has passed the point of return."""
        self._finalized = True
        self._before.clear()
        self._made_dirs.clear()
