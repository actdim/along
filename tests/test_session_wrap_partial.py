#!/usr/bin/env python3
"""tests/test_session_wrap_partial.py - Hermetic tests for partial wrap (--keep-open, --phase)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest


class TestSessionWrapPartial(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="along-test-partial-wrap-")
        self.scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
        self.along_exec = os.path.join(self.scripts_dir, "along_exec.py")

        # Initialize minimal .along structure
        self.along_dir = os.path.join(self.tmp, ".along")
        self.issues_dir = os.path.join(self.along_dir, "ISSUES")
        self.sessions_dir = os.path.join(self.along_dir, "SESSIONS")
        os.makedirs(self.issues_dir, exist_ok=True)
        os.makedirs(self.sessions_dir, exist_ok=True)
        with open(os.path.join(self.along_dir, "ISSUES.md"), "w", encoding="utf-8") as f:
            f.write("# Issues Board\n")
        with open(os.path.join(self.along_dir, "HISTORY.md"), "w", encoding="utf-8") as f:
            f.write("# Project History\n")

        # Create multi-phase issue
        self.slug = "sample-phases"
        self.key = f"feat--{self.slug}"
        self.issue_file = os.path.join(self.issues_dir, f"{self.key}.md")
        content = (
            "---\n"
            "protocol: along\n"
            "protocol_version: '4.6.0'\n"
            f"slug: {self.slug}\n"
            "type: feat\n"
            "status: in-progress\n"
            "priority: medium\n"
            "created: 2026-11-06\n"
            "updated: 2026-11-06\n"
            "agent: antigravity\n"
            "tags: []\n"
            "blocked_by: []\n"
            "related: []\n"
            "plan_status: approved\n"
            "---\n\n"
            "# Feature With Multiple Phases\n\n"
            "## Phases\n"
            "- [ ] Phase 1: Setup data\n"
            "- [ ] Phase 2: Add endpoints\n\n"
            "## Requirements\n- REQ-1: Work.\n\n"
            "## Acceptance Criteria\n- [ ] Done.\n"
        )
        with open(self.issue_file, "w", encoding="utf-8") as f:
            f.write(content)

        # Create canonical plan
        plan_folder = os.path.join(self.issues_dir, self.key)
        os.makedirs(plan_folder, exist_ok=True)
        with open(os.path.join(plan_folder, "plan.md"), "w", encoding="utf-8") as f:
            f.write("# Living Plan: Multi-phase work\nExecution steps.\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *args):
        cmd = [sys.executable, self.along_exec, *args]
        return subprocess.run(cmd, cwd=self.tmp, capture_output=True, text=True)

    def test_partial_wrap_leaves_issue_in_progress_and_ticks_phase(self):
        res = self._run(
            "session", "wrap", self.slug,
            "--keep-open",
            "--phase", "Phase 1: Setup data",
            "--summary", "Completed Phase 1 setup",
            "--no-decisions",
            "-n",
            "--reason", "Unit testing partial wrap",
            "--no-commit",
        )
        self.assertEqual(res.returncode, 0, f"stderr: {res.stderr}\nstdout: {res.stdout}")
        self.assertIn("Updated issue in-progress", res.stdout)
        self.assertIn("Marked phase 'Phase 1: Setup data' completed", res.stdout)

        # 1. Issue remains in ISSUES/, not moved to done/
        self.assertTrue(os.path.isfile(self.issue_file))
        done_file = os.path.join(self.issues_dir, "done", f"{self.key}.md")
        self.assertFalse(os.path.exists(done_file))

        # 2. Issue file body has Phase 1 ticked
        with open(self.issue_file, "r", encoding="utf-8") as f:
            issue_body = f.read()
            self.assertIn("- [x] Phase 1: Setup data", issue_body)
            self.assertIn("- [ ] Phase 2: Add endpoints", issue_body)
            self.assertIn("status: in-progress", issue_body)

        # 3. Canonical plan.md remains intact
        plan_file = os.path.join(self.issues_dir, self.key, "plan.md")
        self.assertTrue(os.path.isfile(plan_file))

        # 4. HISTORY.md has an entry appended
        with open(os.path.join(self.along_dir, "HISTORY.md"), "r", encoding="utf-8") as f:
            self.assertIn("Completed Phase 1 setup", f.read())


if __name__ == "__main__":
    unittest.main()
