#!/usr/bin/env python3
"""tests/test_hermetic_snapshot.py - Unit tests for hermetic suite snapshot change classifier."""

from __future__ import annotations

import os
import unittest

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

from tests.test_zz_hermetic_suite import classify_snapshot_changes


class TestHermeticSnapshotClassifier(unittest.TestCase):

    def test_unchanged_passes(self):
        baseline = {"file.py": (" M", "hash_abc")}
        after = {"file.py": (" M", "hash_abc")}
        report = classify_snapshot_changes(baseline, after, repo_root=".", digest_getter=lambda p: "hash_abc")
        self.assertEqual(report, [])

    def test_stat_cache_flip_vanished_with_same_digest_ignored(self):
        baseline = {"file.py": (" M", "hash_abc")}
        after = {}
        # File vanished from git status, but disk digest matches baseline (stat-cache flip)
        report = classify_snapshot_changes(baseline, after, repo_root=".", digest_getter=lambda p: "hash_abc")
        self.assertEqual(report, [])

    def test_revert_or_delete_detected_when_digest_differs(self):
        baseline = {"file.py": (" M", "hash_abc")}
        after = {}
        # File vanished from git status and disk digest changed (reverted or modified)
        report = classify_snapshot_changes(baseline, after, repo_root=".", digest_getter=lambda p: "hash_other")
        self.assertEqual(report, ["  reverted or deleted: file.py [ M]"])

    def test_revert_or_delete_detected_when_file_deleted(self):
        baseline = {"file.py": (" M", "hash_abc")}
        after = {}
        # File deleted from disk
        report = classify_snapshot_changes(baseline, after, repo_root=".", digest_getter=lambda p: None)
        self.assertEqual(report, ["  reverted or deleted: file.py [ M]"])

    def test_stat_cache_flip_status_changed_with_same_digest_ignored(self):
        baseline = {"file.py": ("M ", "hash_abc")}
        after = {"file.py": (" M", "hash_abc")}
        # Worktree status flipped between M and M, but content digest is identical
        report = classify_snapshot_changes(baseline, after, repo_root=".", digest_getter=lambda p: "hash_abc")
        self.assertEqual(report, [])

    def test_status_changed_with_different_digest_fails(self):
        baseline = {"file.py": ("M ", "hash_abc")}
        after = {"file.py": (" M", "hash_diff")}
        report = classify_snapshot_changes(baseline, after, repo_root=".", digest_getter=lambda p: "hash_diff")
        self.assertEqual(report, ["  status changed: file.py [M  ->  M]"])

    def test_content_changed_with_same_status_fails(self):
        baseline = {"file.py": (" M", "hash_abc")}
        after = {"file.py": (" M", "hash_new")}
        report = classify_snapshot_changes(baseline, after, repo_root=".", digest_getter=lambda p: "hash_new")
        self.assertEqual(report, ["  content changed: file.py [ M]"])

    def test_appeared_file_fails(self):
        baseline = {}
        after = {"new_file.py": ("??", "hash_123")}
        report = classify_snapshot_changes(baseline, after, repo_root=".", digest_getter=lambda p: "hash_123")
        self.assertEqual(report, ["  appeared: new_file.py [??]"])


if __name__ == "__main__":
    unittest.main()

