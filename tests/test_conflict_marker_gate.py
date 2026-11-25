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
from alongkit.hooks import GateDecision, HookEvent, HookEventType
from alongkit.hooks.declarative import get_all_declarative_gates
from alongkit.hooks.predicates import check_staged_conflict_markers, find_added_conflict_markers

MARKED = "a\n<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> branch\n"


def _git(root, *args):
    res = proc.run_capture(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "-c", "core.autocrlf=false", *args],
        cwd=root,
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
        self.assertIsNone(check_staged_conflict_markers(_commit_event('rg -n "git commit" docs/'), self.root))

    def test_enumerates_all_commit_invocation_shapes_with_staged_markers(self):
        self._write(MARKED)
        _git(self.root, "add", "f.txt")
        gates = {g.name: g for g in get_all_declarative_gates(repo_root=self.root)}
        conflict_gate = gates["commit_no_conflict_markers"]

        shapes = (
            ("plain", 'git commit -m "merge"'),
            ("and_chain", 'cd /tmp && git commit -m "merge"'),
            ("semicolon_chain", 'cd /tmp; git commit -m "merge"'),
            ("pipe", "echo merge | git commit -F -"),
            ("dash_c_dummy", 'git -C /tmp commit -m "merge"'),
            ("dash_c_repo", f'git -C "{self.root}" commit -m "merge"'),
            ("cd_repo_chain", f'cd "{self.root}" && git commit -m "merge"'),
        )
        for label, cmd in shapes:
            event = _commit_event(cmd)
            with self.subTest(check="predicate", shape=label, cmd=cmd):
                reason = check_staged_conflict_markers(event, self.root)
                self.assertIsNotNone(reason, f"{label} was admitted: {cmd}")
                self.assertIn("commit-no-conflict-markers", reason or "")
            with self.subTest(check="declarative_gate", shape=label, cmd=cmd):
                res = conflict_gate.evaluate(event)
                self.assertEqual(res.decision, GateDecision.DENY, f"{label} was admitted: {cmd}")
                self.assertIn("commit-no-conflict-markers", res.reason or "")

    def test_chained_and_dash_c_commit_all_inspects_unstaged_changes(self):
        self._write(MARKED)
        self.assertIsNone(check_staged_conflict_markers(_commit_event("echo -a && git commit -m x"), self.root))
        self.assertIsNone(check_staged_conflict_markers(_commit_event('git commit -m "fix -a"'), self.root))
        for cmd in (
            "cd /tmp && git commit -am x",
            "cd /tmp; git commit --all -m x",
            f'git -C "{self.root}" commit -am x',
            "echo x | git commit -a -F -",
        ):
            with self.subTest(cmd=cmd):
                reason = check_staged_conflict_markers(_commit_event(cmd), self.root)
                self.assertIsNotNone(reason, f"expected denial for {cmd}")
                self.assertIn("commit-no-conflict-markers", reason or "")

    def test_dash_c_and_cd_target_separate_repository(self):
        other = tempfile.mkdtemp(prefix="along-conflict-other-")
        try:
            _git(other, "init", "-q")
            other_file = os.path.join(other, "g.txt")
            with open(other_file, "w", encoding="utf-8", newline="\n") as f:
                f.write("clean\n")
            _git(other, "add", "g.txt")
            _git(other, "commit", "-q", "-m", "init")

            # Clean self.root, dirty other repo -> caught via -C or cd &&
            with open(other_file, "w", encoding="utf-8", newline="\n") as f:
                f.write(MARKED)
            _git(other, "add", "g.txt")
            for cmd in (f'git -C "{other}" commit -m "x"', f'cd "{other}" && git commit -m "x"'):
                with self.subTest(dirty_other=cmd):
                    reason = check_staged_conflict_markers(_commit_event(cmd), self.root)
                    self.assertIsNotNone(reason)
                    self.assertIn("g.txt", reason or "")

            # Dirty self.root, clean other repo -> clean target repo is allowed
            with open(other_file, "w", encoding="utf-8", newline="\n") as f:
                f.write("clean\n")
            _git(other, "add", "g.txt")
            self._write(MARKED)
            _git(self.root, "add", "f.txt")
            self.assertIsNone(check_staged_conflict_markers(_commit_event(f'git -C "{other}" commit -m "x"'), self.root))
        finally:
            shutil.rmtree(other, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
