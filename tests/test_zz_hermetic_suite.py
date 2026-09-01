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
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import proc

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


def porcelain_snapshot(repo_root: str) -> dict | None:
    """`git status --porcelain -u` as {path: status}, or None when git cannot answer.

    Called twice: git refreshes its stat cache while producing the first answer, and a
    "racily clean" entry (same mtime as the index) is only re-examined then. Reading the
    second answer keeps a stale-index flip from being reported as a mutation.
    """
    result = None
    for _ in range(2):
        result = proc.run_capture(["git", "status", "--porcelain", "-u"], cwd=repo_root)
        if not result.ok:
            return None
    entries = {}
    for line in (result.stdout or "").splitlines():
        if len(line) > 3:
            entries[line[3:].strip()] = line[:2]
    return entries


#: Snapshot of the working tree taken before the suite runs. See the module docstring.
BASELINE = porcelain_snapshot(REPO_ROOT)


class TestSuiteLeavesTheRepositoryAlone(unittest.TestCase):

    def test_01_working_tree_is_unchanged_by_the_suite(self):
        if BASELINE is None:
            self.skipTest("git is unavailable or this is not a work tree")

        after = porcelain_snapshot(REPO_ROOT)
        self.assertIsNotNone(after, "git stopped answering mid-suite")

        appeared = {p: s for p, s in after.items() if p not in BASELINE}
        changed = {p: f"{BASELINE[p]} -> {s}" for p, s in after.items()
                   if p in BASELINE and BASELINE[p] != s}
        vanished = {p: s for p, s in BASELINE.items() if p not in after}

        report = []
        for label, group in (("appeared", appeared), ("status changed", changed),
                             ("vanished", vanished)):
            for path, status in sorted(group.items()):
                report.append(f"  {label}: {path} [{status}]")

        self.assertEqual(
            report, [],
            "the test suite modified the working tree. A suite that writes into the "
            "repository it tests cannot be a gate: it produces false diffs, can corrupt "
            "work in progress, and makes CI unable to tell a real change from test noise. "
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


if __name__ == "__main__":
    unittest.main()
