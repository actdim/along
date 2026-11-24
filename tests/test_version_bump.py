#!/usr/bin/env python3
"""
tests/test_version_bump.py - Unit tests for along_version_bump CLI behavior, error reporting, and rollback.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from along_version_bump import report_rollback, ReleaseAborted, deduplicate_log_entries


class TestVersionBumpCli(unittest.TestCase):
    """Test CLI behavior and rollback reporting for along_version_bump."""

    def test_cli_help_exits_cleanly(self):
        script_path = os.path.join(SCRIPTS_DIR, "along_version_bump.py")
        res = subprocess.run(
            [sys.executable, script_path, "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("usage: python along_version_bump.py", res.stdout.lower())

    def test_report_rollback_untouched_working_tree(self):
        mock_tx = MagicMock()
        mock_tx.rollback.return_value = []
        mock_tx.unrestorable = []

        buf = io.StringIO()
        with patch("sys.stderr", buf):
            report_rollback(mock_tx, "precondition failed")

        output = buf.getvalue()
        self.assertIn("[Abort] Release aborted: precondition failed", output)
        self.assertIn("Nothing was written; the working tree is untouched", output)

    def test_report_rollback_restores_mutated_files(self):
        mock_tx = MagicMock()
        mock_tx.rollback.return_value = ["package.json", ".along/VERSION"]
        mock_tx.unrestorable = []

        buf = io.StringIO()
        with patch("sys.stderr", buf):
            report_rollback(mock_tx, "gate error")

        output = buf.getvalue()
        self.assertIn("[Abort] Release aborted: gate error", output)
        self.assertIn("Rolled back 2 file(s):", output)
        self.assertIn("package.json", output)


class TestDeduplicateLogEntries(unittest.TestCase):
    """Test changelog log entry deduplication and prefix normalization."""

    def test_deduplicates_by_issue_reference_and_prefers_scope(self):
        entries = [
            "fix: Fix webdev session browser creation (refs #webdev-session-create-browser-helper)",
            "fix(webdev): session browser creation, thread affinity, and doctor checks (refs #webdev-session-create-browser-helper)",
            "feat: Standalone feature without refs",
            "fix: fix(opencode): guard undefined output in shell hooks (refs #opencode-shell-env-runner-fix)",
            "fix(opencode): guard undefined output in shell hooks and align runner CLI contract (refs #opencode-shell-env-runner-fix)",
        ]
        deduped = deduplicate_log_entries(entries)
        self.assertEqual(len(deduped), 3)
        self.assertEqual(
            deduped[0],
            "fix(webdev): session browser creation, thread affinity, and doctor checks (refs #webdev-session-create-browser-helper)",
        )
        self.assertEqual(deduped[1], "feat: Standalone feature without refs")
        self.assertEqual(
            deduped[2],
            "fix(opencode): guard undefined output in shell hooks and align runner CLI contract (refs #opencode-shell-env-runner-fix)",
        )


if __name__ == "__main__":
    unittest.main()
