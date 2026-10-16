#!/usr/bin/env python3
"""
tests/test_start_guard.py - Hermetic tests for along start clean working tree guard.

Covers [feat--atomic-wrap-commit-and-start-guard] REQ-2:
- along start blocks if uncommitted changes from completed (wrapped) issues exist.
- along start blocks if active in-progress issues exist with uncommitted working tree changes.
- along start allows override via --allow-dirty or isolation via --worktree.
"""

from __future__ import annotations

import io
import os
import shutil
import sys
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import lifecycle, proc, session, textio
from hermetic import make_repo_fixture


class TestStartGuard(unittest.TestCase):
    def setUp(self):
        self.root = make_repo_fixture(prefix="along-start-guard-", with_docs=False)
        proc.run_capture(["git", "init", "-q"], cwd=self.root)
        proc.run_capture(["git", "config", "user.email", "t@example.com"], cwd=self.root)
        proc.run_capture(["git", "config", "user.name", "T"], cwd=self.root)
        proc.run_capture(["git", "add", "-A"], cwd=self.root)
        proc.run_capture(["git", "commit", "-q", "-m", "init"], cwd=self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_start_succeeds_on_clean_tree(self):
        from along_exec import handle_start_command
        issue_path = os.path.join(self.root, ".along", "ISSUES", "feat--task-clean.md")
        textio.write_text(issue_path, "---\nslug: task-clean\ntype: feat\nstatus: open\n---\n# Clean\n")

        # Starting on clean tree should succeed
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as cm:
                handle_start_command(self.root, ["task-clean"])
            self.assertEqual(cm.exception.code, 0)

        st = session.load_state(self.root, "task-clean")
        self.assertIsNotNone(st)

    def test_start_blocks_on_wrapped_uncommitted_files(self):
        from along_exec import handle_start_command
        # Wrap an issue leaving uncommitted files via no_commit=True
        slug = "fixture-sample-task"
        session.init_session(self.root, slug)
        session.record_plan(self.root, slug, "1. Plan", "test")
        session.append_event(self.root, slug, "sess-1", "edit", "src/work.py")
        os.makedirs(os.path.join(self.root, "src"), exist_ok=True)
        textio.write_text(os.path.join(self.root, "src", "work.py"), "code = 1\n")

        code = lifecycle.execute_wrap(self.root, slug, status="done", no_verify=True, decisions=[], no_commit=True)
        self.assertEqual(code, 0)

        # Create new issue to start
        new_issue = os.path.join(self.root, ".along", "ISSUES", "feat--task-next.md")
        textio.write_text(new_issue, "---\nslug: task-next\ntype: feat\nstatus: open\n---\n# Next\n")

        with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_err:
            with self.assertRaises(SystemExit) as cm:
                handle_start_command(self.root, ["task-next"])
            self.assertEqual(cm.exception.code, 1)
            err = mock_err.getvalue()
            self.assertIn("uncommitted changes from completed (wrapped) issue", err)
            self.assertIn("task--fixture-sample-task", err)

        # --allow-dirty bypasses the check
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as cm:
                handle_start_command(self.root, ["task-next", "--allow-dirty"])
            self.assertEqual(cm.exception.code, 0)

        st = session.load_state(self.root, "task-next")
        self.assertIsNotNone(st)

    def test_start_blocks_on_active_issue_with_dirty_changes(self):
        from along_exec import handle_start_command
        # Task 1 is in progress with dirty edits
        task1 = os.path.join(self.root, ".along", "ISSUES", "feat--task-one.md")
        textio.write_text(task1, "---\nslug: task-one\ntype: feat\nstatus: in-progress\n---\n# Task 1\n")
        session.init_session(self.root, "task-one")
        session.record_plan(self.root, "task-one", "1. Plan", "test")
        session.append_event(self.root, "task-one", "sess-1", "edit", "src/active.py")
        os.makedirs(os.path.join(self.root, "src"), exist_ok=True)
        textio.write_text(os.path.join(self.root, "src", "active.py"), "active = 1\n")

        # Try to start Task 2
        task2 = os.path.join(self.root, ".along", "ISSUES", "feat--task-two.md")
        textio.write_text(task2, "---\nslug: task-two\ntype: feat\nstatus: open\n---\n# Task 2\n")

        with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_err:
            with self.assertRaises(SystemExit) as cm:
                handle_start_command(self.root, ["task-two"])
            self.assertEqual(cm.exception.code, 1)
            err = mock_err.getvalue()
            self.assertIn("Active in-progress issue(s) exist with uncommitted working tree changes", err)
            self.assertIn("task-one", err)
            self.assertIn("--worktree", err)

        # Resuming Task 1 itself is allowed
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as cm:
                handle_start_command(self.root, ["task-one"])
            self.assertEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
