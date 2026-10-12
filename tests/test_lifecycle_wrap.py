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
import json
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

    def test_02b_wrap_without_summary_uses_issue_title_and_is_idempotent(self):
        """Wrap without --summary derives HISTORY entry from issue title and is idempotent."""
        history_file = os.path.join(self.root, ".along", "HISTORY.md")
        textio.write_text(history_file, "# History\n\n_Log:_\n")

        # First wrap without --summary
        code = lifecycle.execute_wrap(
            self.root,
            "fixture-sample-task",
            summary=None,
            no_verify=True,
            agent="test-agent",
        )
        self.assertEqual(code, 0)

        hist = textio.read_text(history_file)
        lines = [l for l in hist.splitlines() if "fixture-sample-task" in l]
        self.assertEqual(len(lines), 1)
        self.assertIn("fixture-sample-task", lines[0])
        self.assertIn("test-agent", lines[0])

        # Second wrap/append attempt on same slug should be idempotent (no duplicate line)
        code2 = lifecycle.append_history_entry(
            self.root,
            "fixture-sample-task",
            summary=None,
            agent="test-agent",
            is_wrap=True,
        )
        self.assertEqual(code2, 0)
        hist2 = textio.read_text(history_file)
        lines2 = [l for l in hist2.splitlines() if "fixture-sample-task" in l]
        self.assertEqual(len(lines2), 1)

    def test_02c_along_history_append_cli_and_state_gate(self):
        """along history append updates existing entries and passes Along state gate."""
        from alongkit.hooks import shellparse

        history_file = os.path.join(self.root, ".along", "HISTORY.md")
        textio.write_text(history_file, "# History\n\n_Log:_\n")

        # 1. State command classification passes mutation authorization
        cmd = "along history append fixture-sample-task 'Updated custom summary'"
        self.assertTrue(shellparse.is_along_state_command(cmd))

        # 2. Append new entry
        code = lifecycle.append_history_entry(
            self.root,
            "fixture-sample-task",
            summary="Initial summary",
            agent="test-agent",
        )
        self.assertEqual(code, 0)
        hist = textio.read_text(history_file)
        self.assertIn("Initial summary", hist)

        # 3. Explicit append updates the existing line
        code2 = lifecycle.append_history_entry(
            self.root,
            "fixture-sample-task",
            summary="Updated custom summary",
            agent="test-agent",
        )
        self.assertEqual(code2, 0)
        hist2 = textio.read_text(history_file)
        lines = [l for l in hist2.splitlines() if "fixture-sample-task" in l]
        self.assertEqual(len(lines), 1)
        self.assertIn("Updated custom summary", lines[0])
        self.assertNotIn("Initial summary", hist2)

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

    def _tree_snapshot(self):
        snap = {}
        for base, _dirs, files in os.walk(self.root):
            for name in files:
                path = os.path.join(base, name)
                with open(path, "rb") as handle:
                    snap[os.path.relpath(path, self.root)] = handle.read()
        return snap

    def _add_dangling_issue(self):
        textio.write_text(os.path.join(self.root, ".along", "ISSUES", "bug--broken-ref.md"),
                          "---\nprotocol: along\nslug: broken-ref\ntype: bug\nstatus: open\npriority: low\n"
                          "created: 2026-10-11\nupdated: 2026-10-11\nparent: task--nowhere\n---\n\n# broken\n")

    def test_07b_graph_failure_changes_nothing_on_disk(self):
        """[bug--wrap-not-transactional]: checks run before any write."""
        self._add_dangling_issue()
        before = self._tree_snapshot()
        with patch.dict(os.environ, {"ALONG_HOOK_MODE": "enforce"}):
            code = lifecycle.execute_wrap(self.root, "fixture-sample-task", no_verify=True, decisions=[])
        self.assertEqual(code, 1)
        self.assertEqual(self._tree_snapshot(), before)

    def test_07c_force_reason_passes_the_graph_gate_and_is_logged(self):
        self._add_dangling_issue()
        with patch.dict(os.environ, {"ALONG_HOOK_MODE": "enforce"}):
            code = lifecycle.execute_wrap(self.root, "fixture-sample-task", no_verify=True, decisions=[],
                                          force_reason="umbrella lives in another repo")
        self.assertEqual(code, 0)
        today = entities.today_iso()
        log = textio.read_text(os.path.join(self.root, ".along", "SESSIONS", today[:4],
                                            f"{today}--fixture-sample-task.md"))
        self.assertIn("entity-reference-integrity", log)
        self.assertIn("umbrella lives in another repo", log)

    def test_08_cli_router_invocation(self):
        """along_exec.py wrap dispatches cleanly via TOOL_MAPPINGS to along_wrap.py."""
        along_exec = os.path.join(SCRIPTS_DIR, "along_exec.py")
        dest_issue = os.path.join(self.root, ".along", "ISSUES", "done", "task--fixture-sample-task.md")

        res = proc.run_python(
            [along_exec, "wrap", "fixture-sample-task", "-n", "--reason", "fixture", "--no-decisions"],
            cwd=self.root,
        )
        self.assertTrue(res.ok, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        self.assertTrue(os.path.isfile(dest_issue))

    def test_09_session_wrap_subcommand_invocation(self):
        """along_exec.py session wrap dispatches cleanly."""
        along_exec = os.path.join(SCRIPTS_DIR, "along_exec.py")
        dest_issue = os.path.join(self.root, ".along", "ISSUES", "done", "task--fixture-sample-task.md")

        res = proc.run_python(
            [along_exec, "session", "wrap", "fixture-sample-task", "-n", "--reason", "fixture", "--no-decisions"],
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
            [along_wrap, "fixture-sample-task", "-s", "superseded", "-m", "Direct wrap summary", "-n", "--reason", "fixture", "--no-decisions"],
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
             "--reason", "fixture", "--no-decisions"],
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

    def test_17_wrap_docs_only_with_session_ledger_skips_test_gate(self):
        """[bug--wrap-docs-only-test-skip] REQ-1: docs-only changes in session ledger skip wrap test gate."""
        textio.write_text(os.path.join(self.root, ".along", "config.json"),
                          json.dumps({"verify": {"tests": "required"}}))
        session.append_event(self.root, "fixture-sample-task", "sess-1", "edit", "docs/topic--architecture.md")

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            code = lifecycle.execute_wrap(
                self.root,
                "fixture-sample-task",
                status="done",
                no_verify=False,
                decisions=[],
            )
            out = mock_stdout.getvalue()

        self.assertEqual(code, 0)
        self.assertIn("Only documentation / Along state changes: tests skipped.", out)

    def test_18_wrap_docs_only_with_working_tree_changes_skips_test_gate(self):
        """[bug--wrap-docs-only-test-skip] REQ-1: docs-only working tree changes skip wrap test gate when no ledger."""
        proc.run_capture(["git", "init", "-q"], cwd=self.root)
        proc.run_capture(["git", "config", "user.email", "t@example.com"], cwd=self.root)
        proc.run_capture(["git", "config", "user.name", "T"], cwd=self.root)
        proc.run_capture(["git", "add", "-A"], cwd=self.root)
        proc.run_capture(["git", "commit", "-q", "-m", "init"], cwd=self.root)

        textio.write_text(os.path.join(self.root, ".along", "config.json"),
                          json.dumps({"verify": {"tests": "required"}}))
        textio.write_text(os.path.join(self.root, "docs", "topic--architecture.md"),
                          "Updated doc content.\n")

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            code = lifecycle.execute_wrap(
                self.root,
                "fixture-sample-task",
                status="done",
                no_verify=False,
                decisions=[],
            )
            out = mock_stdout.getvalue()

        self.assertEqual(code, 0)
        self.assertIn("Only documentation / Along state changes: tests skipped.", out)

    def test_19_wrap_with_source_change_runs_and_fails_test_gate(self):
        """[bug--wrap-docs-only-test-skip] REQ-1: source changes still run and fail on test gate."""
        textio.write_text(os.path.join(self.root, ".along", "config.json"),
                          json.dumps({"verify": {"tests": "required"}}))
        session.append_event(self.root, "fixture-sample-task", "sess-1", "edit", "src/index.ts")

        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            code = lifecycle.execute_wrap(
                self.root,
                "fixture-sample-task",
                status="done",
                no_verify=False,
                decisions=[],
            )
            err = mock_stderr.getvalue()

        self.assertEqual(code, 1)
        self.assertIn("misconfigured", err.lower())

    def test_20_wrap_with_unknown_changes_keeps_test_gate(self):
        """[bug--wrap-docs-only-test-skip] REQ-3: unknown changes keep the test gate."""
        textio.write_text(os.path.join(self.root, ".along", "config.json"),
                          json.dumps({"verify": {"tests": "required"}}))
        # Not a git repo and no ledger events
        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            code = lifecycle.execute_wrap(
                self.root,
                "fixture-sample-task",
                status="done",
                no_verify=False,
                decisions=[],
            )
            err = mock_stderr.getvalue()

        self.assertEqual(code, 1)
        self.assertIn("misconfigured", err.lower())

    def test_21_wrap_nested_along_skips_test_gate(self):
        """[bug--wrap-docs-only-test-skip] REQ-2: nested .along skips test gate."""
        textio.write_text(os.path.join(self.root, ".along", "config.json"),
                          json.dumps({"verify": {"tests": "required"}}))
        session.append_event(self.root, "fixture-sample-task", "sess-1", "edit",
                             "packages/webmold/.along/ISSUES.md")
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            code = lifecycle.execute_wrap(
                self.root,
                "fixture-sample-task",
                status="done",
                no_verify=False,
                decisions=[],
            )
            out = mock_stdout.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("Only documentation / Along state changes: tests skipped.", out)

    def test_22_wrap_nested_along_scripts_runs_and_fails_test_gate(self):
        """[bug--wrap-docs-only-test-skip] REQ-2: nested .along/scripts/ is not state and runs test gate."""
        textio.write_text(os.path.join(self.root, ".along", "config.json"),
                          json.dumps({"verify": {"tests": "required"}}))
        session.append_event(self.root, "fixture-sample-task", "sess-1", "edit",
                             "packages/webmold/.along/scripts/test.py")
        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            code = lifecycle.execute_wrap(
                self.root,
                "fixture-sample-task",
                status="done",
                no_verify=False,
                decisions=[],
            )
            err = mock_stderr.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("misconfigured", err.lower())


if __name__ == "__main__":
    unittest.main()
