#!/usr/bin/env python3
"""
tests/test_lifecycle_wrap.py - Hermetic tests for transactional along wrap engine.

Covers feat--executable-along-wrap-engine:
- REQ-1: lifecycle.execute_wrap() implementation
- REQ-2: Registration in TOOL_MAPPINGS and CLI router
- REQ-3: Byte-exact rollback on failure via alongkit.transaction.FileTransaction
- REQ-4: Documentation in skills/along-wrap/SKILL.md
- REQ-5: Behavioral test suite verifying issue relocation, front-matter updates,
  board syncing, session blackboard purge, and rollback on failure
"""

from __future__ import annotations

import os
import sys

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

import shutil
import unittest
from unittest.mock import patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import entities, frontmatter, lifecycle, proc, repo, session, textio
import hermetic


class TestLifecycleWrap(unittest.TestCase):

    def setUp(self):
        self.root = hermetic.make_repo_fixture()
        # Initialize session blackboard for sample task
        session.init_session(
            self.root,
            "fixture-sample-task",
            title="Fixture Task",
            total_steps=2,
            step_titles=["Step 1", "Step 2"],
        )
        self.assertTrue(
            os.path.isdir(session.get_session_dir(self.root, "fixture-sample-task"))
        )

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_01_wrap_success(self):
        """Standard wrap: updates frontmatter, moves to done/, recompiles board, purges scratch."""
        src_issue = os.path.join(self.root, ".along", "ISSUES", "task--fixture-sample-task.md")
        dest_issue = os.path.join(self.root, ".along", "ISSUES", "done", "task--fixture-sample-task.md")
        board_file = os.path.join(self.root, ".along", "ISSUES.md")

        self.assertTrue(os.path.isfile(src_issue))
        self.assertFalse(os.path.isfile(dest_issue))

        code = lifecycle.execute_wrap(
            self.root,
            "fixture-sample-task",
            status="done",
            no_verify=True,
        )
        self.assertEqual(code, 0)

        # File moved to done/
        self.assertFalse(os.path.isfile(src_issue))
        self.assertTrue(os.path.isfile(dest_issue))

        # Front-matter updated
        content = textio.read_text(dest_issue)
        fm, _ = frontmatter.parse(content)
        self.assertEqual(fm["status"], "done")
        self.assertEqual(fm["completed"], entities.today_iso())
        self.assertEqual(fm["updated"], entities.today_iso())

        # Board updated
        board = textio.read_text(board_file)
        self.assertIn("ISSUES/done/task--fixture-sample-task.md", board)
        self.assertIn("- [x] `(task)` [fixture-sample-task]", board)

        # Session blackboard purged
        self.assertFalse(
            os.path.isdir(session.get_session_dir(self.root, "fixture-sample-task"))
        )

    def test_02_wrap_with_history_summary(self):
        """Providing --summary appends a formatted line to .along/HISTORY.md."""
        history_file = os.path.join(self.root, ".along", "HISTORY.md")
        textio.write_text(history_file, "# History\n\n_Log:_\n")

        # Create session file
        today = entities.today_iso()
        year = today.split("-")[0]
        sess_dir = os.path.join(self.root, ".along", "SESSIONS", year)
        os.makedirs(sess_dir, exist_ok=True)
        sess_file = os.path.join(sess_dir, f"{today}--fixture-sample-task.md")
        textio.write_text(sess_file, "# Session log\n")

        code = lifecycle.execute_wrap(
            self.root,
            "fixture-sample-task",
            summary="Completed fixture work cleanly",
            no_verify=True,
            agent="test-agent",
        )
        self.assertEqual(code, 0)

        hist = textio.read_text(history_file)
        expected_line = (
            f"{today} - fixture-sample-task - test-agent - Completed fixture work cleanly - "
            f"[Session Log](./SESSIONS/{year}/{today}--fixture-sample-task.md)"
        )
        self.assertIn(expected_line, hist)

    def test_03_test_failure_halts_without_mutations(self):
        """When pre-flight tests fail, wrap halts immediately and mutates nothing."""
        scripts_dir = os.path.join(self.root, ".along", "scripts")
        os.makedirs(scripts_dir, exist_ok=True)
        test_script = os.path.join(scripts_dir, "test.py")
        textio.write_text(test_script, "import sys\nsys.exit(1)\n")

        src_issue = os.path.join(self.root, ".along", "ISSUES", "task--fixture-sample-task.md")
        dest_issue = os.path.join(self.root, ".along", "ISSUES", "done", "task--fixture-sample-task.md")
        orig_content = textio.read_text(src_issue)

        code = lifecycle.execute_wrap(
            self.root,
            "fixture-sample-task",
            no_verify=False,
        )
        self.assertEqual(code, 1)

        # Issue untouched
        self.assertTrue(os.path.isfile(src_issue))
        self.assertFalse(os.path.isfile(dest_issue))
        self.assertEqual(textio.read_text(src_issue), orig_content)

        # Session blackboard still intact
        self.assertTrue(
            os.path.isdir(session.get_session_dir(self.root, "fixture-sample-task"))
        )

    def test_04_zero_byte_working_tree_audit_aborts(self):
        """0-byte corrupt file in working tree causes wrap to abort."""
        corrupt_file = os.path.join(self.root, "corrupt.py")
        textio.write_text(corrupt_file, "")  # 0 bytes

        src_issue = os.path.join(self.root, ".along", "ISSUES", "task--fixture-sample-task.md")
        dest_issue = os.path.join(self.root, ".along", "ISSUES", "done", "task--fixture-sample-task.md")

        code = lifecycle.execute_wrap(
            self.root,
            "fixture-sample-task",
            no_verify=True,
        )
        self.assertEqual(code, 1)
        self.assertTrue(os.path.isfile(src_issue))
        self.assertFalse(os.path.isfile(dest_issue))

    def test_05_dry_run_mutates_nothing(self):
        """Dry-run reports plan without modifying files on disk."""
        src_issue = os.path.join(self.root, ".along", "ISSUES", "task--fixture-sample-task.md")
        dest_issue = os.path.join(self.root, ".along", "ISSUES", "done", "task--fixture-sample-task.md")
        orig_content = textio.read_text(src_issue)

        code = lifecycle.execute_wrap(
            self.root,
            "fixture-sample-task",
            dry_run=True,
            no_verify=True,
        )
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isfile(src_issue))
        self.assertFalse(os.path.isfile(dest_issue))
        self.assertEqual(textio.read_text(src_issue), orig_content)
        self.assertTrue(
            os.path.isdir(session.get_session_dir(self.root, "fixture-sample-task"))
        )

    def test_06_custom_status_superseded(self):
        """--status superseded sets terminal superseded status and ~ box in ISSUES.md."""
        dest_issue = os.path.join(self.root, ".along", "ISSUES", "done", "task--fixture-sample-task.md")
        board_file = os.path.join(self.root, ".along", "ISSUES.md")

        code = lifecycle.execute_wrap(
            self.root,
            "fixture-sample-task",
            status="superseded",
            no_verify=True,
        )
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isfile(dest_issue))

        content = textio.read_text(dest_issue)
        fm, _ = frontmatter.parse(content)
        self.assertEqual(fm["status"], "superseded")

        board = textio.read_text(board_file)
        self.assertIn("- [~] `(task)` [fixture-sample-task]", board)

    def test_07_transactional_rollback_on_sync_failure(self):
        """If an error occurs midway through wrap, FileTransaction restores initial state."""
        src_issue = os.path.join(self.root, ".along", "ISSUES", "task--fixture-sample-task.md")
        dest_issue = os.path.join(self.root, ".along", "ISSUES", "done", "task--fixture-sample-task.md")
        orig_content = textio.read_text(src_issue)

        # Mock compile_issues_board to fail midway
        with patch("alongkit.entities.compile_issues_board", side_effect=RuntimeError("simulated board crash")):
            code = lifecycle.execute_wrap(
                self.root,
                "fixture-sample-task",
                no_verify=True,
            )
            self.assertEqual(code, 1)

        # Everything must be restored byte-for-byte
        self.assertTrue(os.path.isfile(src_issue))
        self.assertFalse(os.path.isfile(dest_issue))
        self.assertEqual(textio.read_text(src_issue), orig_content)

    def test_08_cli_router_invocation(self):
        """along_exec.py wrap dispatches cleanly via TOOL_MAPPINGS to along_wrap.py."""
        along_exec = os.path.join(SCRIPTS_DIR, "along_exec.py")
        dest_issue = os.path.join(self.root, ".along", "ISSUES", "done", "task--fixture-sample-task.md")

        res = proc.run_python(
            [along_exec, "wrap", "fixture-sample-task", "-n"],
            cwd=self.root,
        )
        self.assertTrue(res.ok, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        self.assertTrue(os.path.isfile(dest_issue))

    def test_09_session_wrap_subcommand_invocation(self):
        """along_exec.py session wrap dispatches cleanly."""
        along_exec = os.path.join(SCRIPTS_DIR, "along_exec.py")
        dest_issue = os.path.join(self.root, ".along", "ISSUES", "done", "task--fixture-sample-task.md")

        res = proc.run_python(
            [along_exec, "session", "wrap", "fixture-sample-task", "-n"],
            cwd=self.root,
        )
        self.assertTrue(res.ok, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        self.assertTrue(os.path.isfile(dest_issue))


if __name__ == "__main__":
    unittest.main()
