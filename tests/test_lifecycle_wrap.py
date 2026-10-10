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

import io
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import entities, frontmatter, gates, lifecycle, proc, repo, session, textio
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
        # Wrap refuses a scaffold-only plan [bug--session-records-not-captured] REQ-5.
        session.record_plan(self.root, "fixture-sample-task", "1. Fixture plan.", "test")
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

    def test_01b_wrap_preserves_edited_research_in_session_log(self):
        sdir = session.get_session_dir(self.root, "fixture-sample-task")
        research_file = os.path.join(sdir, "research.md")
        textio.write_text(research_file, "# Research & Findings: fixture-sample-task\n\n## Custom Research\n- discovered critical behavior\n")
        code = lifecycle.execute_wrap(
            self.root,
            "fixture-sample-task",
            status="done",
            no_verify=True,
        )
        self.assertEqual(code, 0)
        today = entities.today_iso()
        year = today.split("-")[0]
        sess_file = os.path.join(self.root, ".along", "SESSIONS", year, f"{today}--fixture-sample-task.md")
        self.assertTrue(os.path.isfile(sess_file))
        log = textio.read_text(sess_file)
        self.assertIn("### Research", log)
        self.assertIn("discovered critical behavior", log)

    def test_01c_wrap_aborts_on_unknown_non_scaffold_file(self):
        sdir = session.get_session_dir(self.root, "fixture-sample-task")
        mystery_file = os.path.join(sdir, "mystery.txt")
        textio.write_text(mystery_file, "mystery data\n")
        code = lifecycle.execute_wrap(
            self.root,
            "fixture-sample-task",
            status="done",
            no_verify=True,
        )
        self.assertEqual(code, 2)
        # Blackboard is not purged
        self.assertTrue(os.path.isdir(sdir))
        # Source issue is not moved
        src_issue = os.path.join(self.root, ".along", "ISSUES", "task--fixture-sample-task.md")
        self.assertTrue(os.path.isfile(src_issue))

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

    def _record_edit(self, rel):
        diag = os.path.join(self.root, ".along", "diagnostics", "activity")
        os.makedirs(diag, exist_ok=True)
        textio.write_text(os.path.join(diag, "fixture-session.json"),
                          '{"edited_files": ["%s"]}\n' % rel)

    def test_04_zero_byte_working_tree_audit_aborts(self):
        """An empty file an agent session edited causes wrap to abort."""
        corrupt_file = os.path.join(self.root, "corrupt.py")
        textio.write_text(corrupt_file, "")  # 0 bytes
        self._record_edit("corrupt.py")

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

    def test_04b_unrelated_empty_file_only_warns(self):
        """[bug--wrap-zero-byte-audit-unscoped]: an empty file no session edited does not block."""
        placeholder = os.path.join(self.root, "packages", "other", "README.md")
        os.makedirs(os.path.dirname(placeholder), exist_ok=True)
        textio.write_text(placeholder, "")
        blocking, warnings = gates.zero_byte_working_tree_audit(self.root)
        self.assertEqual(blocking, [])
        self.assertIn("packages/other/README.md", warnings)
        code = lifecycle.execute_wrap(self.root, "fixture-sample-task", no_verify=True)
        self.assertEqual(code, 0)

    def test_04c_truncated_tracked_file_blocks(self):
        """A tracked file that was non-empty at HEAD and is now empty blocks."""
        git_root = tempfile.mkdtemp(prefix="along-zero-byte-")
        try:
            run = lambda *a: subprocess.run(["git", *a], cwd=git_root, check=True,
                                            capture_output=True, text=True)
            run("init", "-q")
            run("config", "user.email", "t@example.com")
            run("config", "user.name", "t")
            os.makedirs(os.path.join(git_root, ".along"))
            textio.write_text(os.path.join(git_root, "module.py"), "x = 1\n")
            textio.write_text(os.path.join(git_root, "untouched.py"), "y = 2\n")
            run("add", "-A")
            run("commit", "-q", "--no-verify", "-m", "fixture")
            textio.write_text(os.path.join(git_root, "module.py"), "")
            textio.write_text(os.path.join(git_root, "placeholder.md"), "")
            blocking, warnings = gates.zero_byte_working_tree_audit(git_root)
            self.assertEqual(blocking, ["module.py"])
            self.assertEqual(warnings, ["placeholder.md"])
        finally:
            shutil.rmtree(git_root, ignore_errors=True)

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
            [along_exec, "wrap", "fixture-sample-task", "-n", "--no-decisions"],
            cwd=self.root,
        )
        self.assertTrue(res.ok, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        self.assertTrue(os.path.isfile(dest_issue))

    def test_09_session_wrap_subcommand_invocation(self):
        """along_exec.py session wrap dispatches cleanly."""
        along_exec = os.path.join(SCRIPTS_DIR, "along_exec.py")
        dest_issue = os.path.join(self.root, ".along", "ISSUES", "done", "task--fixture-sample-task.md")

        res = proc.run_python(
            [along_exec, "session", "wrap", "fixture-sample-task", "-n", "--no-decisions"],
            cwd=self.root,
        )
        self.assertTrue(res.ok, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        self.assertTrue(os.path.isfile(dest_issue))

    def test_10_short_flag_status_and_summary_parity(self):
        """Verify that -s sets status and -m sets summary in along_wrap.py."""
        along_wrap = os.path.join(SCRIPTS_DIR, "along_wrap.py")
        history_file = os.path.join(self.root, ".along", "HISTORY.md")
        textio.write_text(history_file, "# History\n\n_Log:_\n")

        dest_issue = os.path.join(self.root, ".along", "ISSUES", "done", "task--fixture-sample-task.md")
        res = proc.run_python(
            [along_wrap, "fixture-sample-task", "-s", "superseded", "-m", "Direct wrap summary", "-n", "--no-decisions"],
            cwd=self.root,
        )
        self.assertTrue(res.ok, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        self.assertTrue(os.path.isfile(dest_issue))
        fm, _ = frontmatter.parse(textio.read_text(dest_issue))
        self.assertEqual(fm["status"], "superseded")
        history = textio.read_text(history_file)
        self.assertIn("Direct wrap summary", history)

    def test_11_session_wrap_short_flag_parity(self):
        """Verify that along session wrap uses -s for status and -m for summary."""
        along_exec = os.path.join(SCRIPTS_DIR, "along_exec.py")
        history_file = os.path.join(self.root, ".along", "HISTORY.md")
        textio.write_text(history_file, "# History\n\n_Log:_\n")

        dest_issue = os.path.join(self.root, ".along", "ISSUES", "done", "task--fixture-sample-task.md")
        res = proc.run_python(
            [along_exec, "session", "wrap", "fixture-sample-task", "-s", "cancelled", "-m", "Cancelled summary", "-n",
             "--no-decisions"],
            cwd=self.root,
        )
        self.assertTrue(res.ok, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        self.assertTrue(os.path.isfile(dest_issue))
        fm, _ = frontmatter.parse(textio.read_text(dest_issue))
        self.assertEqual(fm["status"], "cancelled")
        history = textio.read_text(history_file)
        self.assertIn("Cancelled summary", history)

    def test_13_wrap_writes_session_log_from_blackboard(self):
        """[feat--wrap-session-log-from-blackboard] REQ-1, REQ-2."""
        sdir = session.get_session_dir(self.root, "fixture-sample-task")
        textio.write_text(os.path.join(sdir, "plan.md"), "# Living Plan\n\n- [x] Step 1: do it\n")
        session.append_trace(self.root, "fixture-sample-task", "Implementer finished step 1")
        code = lifecycle.execute_wrap(self.root, "fixture-sample-task", status="done", no_verify=True,
                                      summary="Wrapped fixture", decisions=[])
        self.assertEqual(code, 0)
        today = entities.today_iso()
        log = os.path.join(self.root, ".along", "SESSIONS", today[:4], f"{today}--fixture-sample-task.md")
        content = textio.read_text(log)
        fm, _ = frontmatter.parse(content)
        self.assertEqual(fm["issues_completed"], ["task--fixture-sample-task"])
        self.assertEqual(fm["decisions"], [])
        self.assertIn("## Blackboard Record", content)
        self.assertIn("Implementer finished step 1", content)
        self.assertIn("#### Living Plan", content)
        self.assertIn("no architectural decisions", content)
        self.assertFalse(os.path.isdir(sdir))

    def test_14_role_based_open_steps_block_wrap(self):
        """[feat--along-team-step-enforcement] REQ-2."""
        session.init_session(self.root, "fixture-sample-task", execution_mode="role-based")
        code = lifecycle.execute_wrap(self.root, "fixture-sample-task", status="done", no_verify=True, decisions=[])
        self.assertEqual(code, 2)
        self.assertTrue(os.path.isfile(os.path.join(self.root, ".along", "ISSUES", "task--fixture-sample-task.md")))
        code = lifecycle.execute_wrap(self.root, "fixture-sample-task", status="done", no_verify=True,
                                      decisions=[], force_reason="user stopped the loop")
        self.assertEqual(code, 0)
        today = entities.today_iso()
        log = os.path.join(self.root, ".along", "SESSIONS", today[:4], f"{today}--fixture-sample-task.md")
        self.assertIn("user stopped the loop", textio.read_text(log))

    def test_15_cli_requires_decisions_answer(self):
        along_wrap = os.path.join(SCRIPTS_DIR, "along_wrap.py")
        res = proc.run_python([along_wrap, "fixture-sample-task", "-n"], cwd=self.root)
        self.assertFalse(res.ok)
        self.assertIn("--no-decisions", res.stderr)

    def test_12_invalid_status_flag_rejected(self):
        """Invalid status via -s must exit non-zero and reject wrap."""
        along_wrap = os.path.join(SCRIPTS_DIR, "along_wrap.py")
        res = proc.run_python(
            [along_wrap, "fixture-sample-task", "-s", "invalid_status", "-n"],
            cwd=self.root,
        )
        self.assertFalse(res.ok)
        self.assertIn("invalid choice", res.stderr.lower())

    def test_16_wrap_warns_on_uncommitted_attributed_files(self):
        """[bug--wrapped-work-left-uncommitted] REQ-1: wrap warns if attributed files remain uncommitted."""
        proc.run_capture(["git", "init", "-q"], cwd=self.root)
        proc.run_capture(["git", "config", "user.email", "t@example.com"], cwd=self.root)
        proc.run_capture(["git", "config", "user.name", "T"], cwd=self.root)
        proc.run_capture(["git", "add", "-A"], cwd=self.root)
        proc.run_capture(["git", "commit", "-q", "-m", "init"], cwd=self.root)

        session.append_event(self.root, "fixture-sample-task", "sess-1", "edit", "src/module.py")
        os.makedirs(os.path.join(self.root, "src"), exist_ok=True)
        textio.write_text(os.path.join(self.root, "src", "module.py"), "print('hello')\n")

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            code = lifecycle.execute_wrap(
                self.root,
                "fixture-sample-task",
                status="done",
                no_verify=True,
                decisions=[],
            )
            out = mock_stdout.getvalue()

        self.assertEqual(code, 0)
        self.assertIn("[Warning] Issue 'fixture-sample-task' wrapped with uncommitted attributed files:", out)
        self.assertIn("src/module.py", out)
        self.assertIn("along commit -i fixture-sample-task --paths", out)


if __name__ == "__main__":
    unittest.main()
