#!/usr/bin/env python3
"""
tests/test_zz_hermetic_suite.py - the meta-test: the suite must not touch its own repository.

Two independent guarantees, because each catches what the other cannot:

1. `test_01_working_tree_is_unchanged_by_the_suite` compares `git status --porcelain -u`
   before and after the suite. It is the observable statement of the rule, and it catches
   any mutation whatever its cause.
2. `test_02_no_test_targets_the_repository_root` is a structural gate over `tests/*.py`:
   no command line may be built with `REPO_ROOT` as the target of an engine. It catches a
   regression the moment it is written, including one whose damage happens to be
   idempotent today, which is exactly the state this repository was in: the migration
   engine ran over real project memory on every test run and only looked harmless because
   the repository was already migrated.

The module is named `test_zz_...` so `unittest discover` (alphabetical) runs it last. The
baseline is captured at import time, and `unittest.TestLoader.discover` imports every test
module before running any test, so the snapshot precedes the suite.

See `[bug--tests-mutate-working-tree]`.
"""

from __future__ import annotations

import ast
import hashlib
import os
import re
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import proc

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


def _file_digest(repo_root: str, relpath: str) -> Optional[str]:
    """Return SHA-256 hex digest of the working tree file, or None if absent/inaccessible."""
    full_path = os.path.join(repo_root, relpath)
    if not os.path.isfile(full_path):
        return None
    try:
        hasher = hashlib.sha256()
        with open(full_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return None


def porcelain_snapshot(repo_root: str) -> Optional[Dict[str, Tuple[str, Optional[str]]]]:
    """`git status --porcelain -u` as {path: (status, digest)}, or None when git cannot answer.

    Called twice: git refreshes its stat cache while producing the first answer, and a
    "racily clean" entry (same mtime as the index) is only re-examined then. Reading the
    second answer keeps a stale-index flip from being reported as a mutation.
    """
    result = None
    for _ in range(2):
        result = proc.run_capture(["git", "status", "--porcelain", "-u"], cwd=repo_root)
        if not result.ok:
            return None
    entries: Dict[str, Tuple[str, Optional[str]]] = {}
    for line in (result.stdout or "").splitlines():
        if len(line) > 3:
            path = line[3:].strip()
            if path.startswith('"') and path.endswith('"'):
                path = path[1:-1]
            status = line[:2]
            digest = _file_digest(repo_root, path)
            entries[path] = (status, digest)
    return entries


def classify_snapshot_changes(
    baseline: Dict[str, Tuple[str, Optional[str]]],
    after: Dict[str, Tuple[str, Optional[str]]],
    repo_root: str,
    digest_getter: Optional[Callable[[str], Optional[str]]] = None,
) -> List[str]:
    """Classify differences between baseline and after status snapshots by content digest.

    Decision table per path:
      - absent in baseline, present in after: fail as 'appeared'
      - present in baseline, absent in after:
          equal content digest -> stat-cache flip (ignore)
          different/missing digest -> fail as 'reverted or deleted'
      - present in both:
          status differs, equal digest -> stat-cache flip (ignore)
          status differs, different digest -> fail as 'status changed'
          same status, different digest -> fail as 'content changed'
          same status, equal digest -> pass
    """
    if digest_getter is None:
        digest_getter = lambda p: _file_digest(repo_root, p)

    report: List[str] = []
    all_paths = sorted(set(baseline.keys()) | set(after.keys()))

    for path in all_paths:
        in_baseline = path in baseline
        in_after = path in after

        if not in_baseline and in_after:
            a_status, _ = after[path]
            report.append(f"  appeared: {path} [{a_status}]")
        elif in_baseline and not in_after:
            b_status, b_digest = baseline[path]
            current_digest = digest_getter(path)
            if current_digest == b_digest and current_digest is not None:
                # Stat-cache flip: file content is unchanged on disk
                continue
            report.append(f"  reverted or deleted: {path} [{b_status}]")
        elif in_baseline and in_after:
            b_status, b_digest = baseline[path]
            a_status, a_digest = after[path]
            if b_status != a_status:
                if b_digest == a_digest and b_digest is not None:
                    # Stat-cache flip: file content is unchanged
                    continue
                report.append(f"  status changed: {path} [{b_status} -> {a_status}]")
            else:
                if b_digest != a_digest:
                    report.append(f"  content changed: {path} [{a_status}]")

    return report


#: Snapshot of the working tree taken before the suite runs. See the module docstring.
BASELINE = porcelain_snapshot(REPO_ROOT)


class TestSuiteLeavesTheRepositoryAlone(unittest.TestCase):

    def test_01_working_tree_is_unchanged_by_the_suite(self):
        if BASELINE is None:
            self.skipTest("git is unavailable or this is not a work tree")

        after = porcelain_snapshot(REPO_ROOT)
        self.assertIsNotNone(after, "git stopped answering mid-suite")

        report = classify_snapshot_changes(BASELINE, after, REPO_ROOT)

        self.assertEqual(
            report, [],
            "the test suite modified the working tree. A suite that writes into the "
            "repository it tests cannot be a gate: it produces false diffs, can corrupt "
            "work in progress, and makes CI unable to tell a real change from test noise. "
            "Note: editing repository files while the test suite is running will trip this gate. "
            "Point the engine at a tests/hermetic.py fixture instead.\n"
            + "\n".join(report))

    #: An element that marks a list as a command line rather than data.
    COMMAND_SHAPED = re.compile(r"(?i)(script|engine|exec|executable)")

    def _command_lists_targeting_repo_root(self, path):
        """Command-shaped list literals that pass REPO_ROOT as an argument."""
        with open(path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)

        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.List):
                continue
            names = []
            for element in node.elts:
                if isinstance(element, ast.Name):
                    names.append(element.id)
                elif isinstance(element, ast.Attribute):
                    names.append(element.attr)
            if "REPO_ROOT" not in names:
                continue
            if any(self.COMMAND_SHAPED.search(name) for name in names):
                offenders.append(node.lineno)
        return offenders

    def test_02_no_test_targets_the_repository_root(self):
        violations = []
        for name in sorted(os.listdir(TESTS_DIR)):
            if not name.endswith(".py"):
                continue
            path = os.path.join(TESTS_DIR, name)
            for lineno in self._command_lists_targeting_repo_root(path):
                violations.append(f"  {name}:{lineno}")

        self.assertEqual(
            violations, [],
            "these tests build an engine command line with REPO_ROOT as the target. "
            "Engines write; use a tests/hermetic.py fixture:\n" + "\n".join(violations))

    def test_03_no_unapproved_derived_projections_are_tracked(self):
        """Derived projections must not be tracked in Git unless in the approved allowlist.

        Generated dashboard artifacts (.along/dashboard.html, .along/DASHBOARD.md) churn
        history and cause merge conflicts. They must remain untracked and gitignored.
        See [debt--generated-dashboard-artifact-committed] and
        ADR-2026-09-09--untracked-dashboard-artifacts-and-projection-policy.
        """
        result = proc.run_capture(["git", "ls-files"], cwd=REPO_ROOT)
        if not result.ok:
            self.skipTest("git ls-files unavailable")

        # Banned projection artifacts that must never be tracked in Git
        banned_patterns = {
            ".along/dashboard.html": "Generated static HTML dashboard bundle",
            ".along/DASHBOARD.md": "Generated markdown dashboard report",
        }

        tracked_files = [
            line.strip().replace("\\", "/")
            for line in (result.stdout or "").splitlines()
            if line.strip()
        ]

        violations = []
        for path in tracked_files:
            if path in banned_patterns:
                violations.append(f"  Banned projection tracked: {path} ({banned_patterns[path]})")
            elif any(path.endswith("/" + name) or path == name for name in ("dashboard.html", "DASHBOARD.md")):
                violations.append(f"  Unapproved projection artifact tracked: {path}")

        self.assertEqual(
            violations, [],
            "Derived projection artifacts are tracked in Git. Generated artifacts must not be "
            "tracked to prevent history churn and unresolvable merge conflicts. Remove them "
            "from Git tracking (git rm --cached) and add them to .gitignore:\n"
            + "\n".join(violations),
        )


if __name__ == "__main__":
    unittest.main()
