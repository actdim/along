#!/usr/bin/env python3
"""
tests/test_conflict_marker_gate.py - The conflict-marker gate inspects staged content.

Regression suite for [bug--conflict-marker-gate-wrong-target]: the gate used to apply a
regex to the `git commit` command line, so it never saw real markers in staged files and
rejected a commit message containing a Markdown rule of `=======`.
Runs against a throwaway git repository.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import proc
from alongkit.hooks import HookEvent, HookEventType
from alongkit.hooks.predicates import check_staged_conflict_markers, find_added_conflict_markers

MARKED = "a\n<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> branch\n"


def _git(root, *args):
    res = proc.run_capture(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "-c", "core.autocrlf=false", *args],
        cwd=root, trip_on_anomaly=False,
    )
    if res.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {res.stderr}")
    return res


def _commit_event(command):
    return HookEvent(event_type=HookEventType.PRE_TOOL_USE, tool_name="run_command",
                     tool_args={"CommandLine": command}, runtime="generic")


class TestFindAddedMarkers(unittest.TestCase):
    def test_only_added_lines_count(self):
        diff = (
            "diff --git a/f.txt b/f.txt\n--- a/f.txt\n+++ b/f.txt\n"
            "@@ -1 +1,3 @@\n-=======\n+<<<<<<< HEAD\n+=======\n+>>>>>>> other\n"
        )
        hits = find_added_conflict_markers(diff)
        self.assertEqual(len(hits), 3)
        self.assertTrue(all(h.startswith("f.txt:") for h in hits))

    def test_markdown_rule_inside_line_is_not_a_marker(self):
        diff = "+++ b/doc.md\n+Title =======\n+ ======= \n"
        self.assertEqual(find_added_conflict_markers(diff), [])


class TestStagedConflictMarkerGate(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along-conflict-gate-")
        _git(self.root, "init", "-q")
        self.path = os.path.join(self.root, "f.txt")
        with open(self.path, "w", encoding="utf-8", newline="\n") as f:
            f.write("a\n")
        _git(self.root, "add", "f.txt")
        _git(self.root, "commit", "-q", "-m", "init")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, text):
        with open(self.path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def test_staged_markers_are_blocked(self):
        self._write(MARKED)
        _git(self.root, "add", "f.txt")
        reason = check_staged_conflict_markers(_commit_event("git commit -m \"merge\""), self.root)
        self.assertIsNotNone(reason)
        self.assertIn("commit-no-conflict-markers", reason)
        self.assertIn("f.txt", reason)

    def test_message_with_rule_and_clean_content_is_allowed(self):
        self._write("a\nb\n")
        _git(self.root, "add", "f.txt")
        cmd = "git commit -m \"Title\n=======\nbody\""
        self.assertIsNone(check_staged_conflict_markers(_commit_event(cmd), self.root))

    def test_commit_all_inspects_unstaged_tracked_changes(self):
        self._write(MARKED)
        self.assertIsNone(check_staged_conflict_markers(_commit_event("git commit -m x"), self.root))
        self.assertIsNotNone(check_staged_conflict_markers(_commit_event("git commit -am x"), self.root))

    def test_non_commit_commands_are_ignored(self):
        self._write(MARKED)
        _git(self.root, "add", "f.txt")
        self.assertIsNone(check_staged_conflict_markers(_commit_event("git status"), self.root))


if __name__ == "__main__":
    unittest.main(verbosity=2)
