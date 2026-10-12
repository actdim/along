#!/usr/bin/env python3
"""
tests/test_release_ci_check.py - hermetic tests for release CI precondition checks.

REQ-1: Lookup CI status of HEAD commit via `gh run list --commit <sha>`.
REQ-2: Green -> proceed; failed -> abort with run URL; pending/missing -> abort with hint,
       unless --skip-ci with a reason is given.
REQ-3: No gh, no remote, or no workflow files -> warning, not a block.
REQ-4: Repository opt-out / workflow name in .along/config.json.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import unittest
from unittest.mock import MagicMock, patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
for _path in (SCRIPTS_DIR, TESTS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import hermetic
from alongkit import gates, proc, textio
from along_version_bump import check_ci_precondition, release_preflight, ReleaseAborted


class ReleaseCiCheckFixtureCase(unittest.TestCase):
    """Hermetic test fixture for release CI precondition checks."""

    def setUp(self):
        self.root = hermetic.make_repo_fixture(prefix="along-ci-check-")
        self.workflows_dir = os.path.join(self.root, ".github", "workflows")
        os.makedirs(self.workflows_dir, exist_ok=True)
        self.workflow_file = os.path.join(self.workflows_dir, "tests.yml")
        textio.write_text(self.workflow_file, "name: Tests\non: [push]\njobs: {}\n")
        self.head_sha = "1234567890abcdef1234567890abcdef12345678"

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write_config(self, release_cfg: dict):
        config_path = os.path.join(self.root, ".along", "config.json")
        textio.write_text(config_path, json.dumps({"release": release_cfg}, indent=2) + "\n")


class TestReleaseCiCheck(ReleaseCiCheckFixtureCase):

    @patch("shutil.which", return_value="/usr/bin/gh")
    @patch("alongkit.proc.git")
    @patch("alongkit.proc.run_capture")
    def test_ci_green_proceeds(self, mock_run_capture, mock_git, mock_which):
        mock_git.side_effect = lambda args, cwd=None: (
            proc.Result(args, 0, "origin\n", "") if "remote" in args
            else proc.Result(args, 0, self.head_sha, "")
        )
        runs = [
            {
                "workflowName": "Tests",
                "name": "Tests",
                "status": "completed",
                "conclusion": "success",
                "url": "https://github.com/actdim/along/actions/runs/100",
            }
        ]
        mock_run_capture.return_value = proc.Result(
            ["gh"], 0, json.dumps(runs), ""
        )

        # Must not raise
        check_ci_precondition(self.root, head_sha=self.head_sha)
        self.assertTrue(mock_run_capture.called)

    @patch("shutil.which", return_value="/usr/bin/gh")
    @patch("alongkit.proc.git")
    @patch("alongkit.proc.run_capture")
    def test_ci_failed_aborts_with_url(self, mock_run_capture, mock_git, mock_which):
        mock_git.side_effect = lambda args, cwd=None: (
            proc.Result(args, 0, "origin\n", "") if "remote" in args
            else proc.Result(args, 0, self.head_sha, "")
        )
        runs = [
            {
                "workflowName": "Tests",
                "name": "Tests",
                "status": "completed",
                "conclusion": "failure",
                "url": "https://github.com/actdim/along/actions/runs/101",
            }
        ]
        mock_run_capture.return_value = proc.Result(
            ["gh"], 0, json.dumps(runs), ""
        )

        with self.assertRaises(ReleaseAborted) as ctx:
            check_ci_precondition(self.root, head_sha=self.head_sha)
        err = str(ctx.exception)
        self.assertIn("failure", err)
        self.assertIn("Tests", err)
        self.assertIn("https://github.com/actdim/along/actions/runs/101", err)

    @patch("shutil.which", return_value="/usr/bin/gh")
    @patch("alongkit.proc.git")
    @patch("alongkit.proc.run_capture")
    def test_ci_cancelled_and_timed_out_abort(self, mock_run_capture, mock_git, mock_which):
        mock_git.side_effect = lambda args, cwd=None: (
            proc.Result(args, 0, "origin\n", "") if "remote" in args
            else proc.Result(args, 0, self.head_sha, "")
        )
        for conclusion in ("cancelled", "timed_out"):
            runs = [
                {
                    "workflowName": "Tests",
                    "status": "completed",
                    "conclusion": conclusion,
                    "url": f"https://github.com/actdim/along/actions/runs/{conclusion}",
                }
            ]
            mock_run_capture.return_value = proc.Result(["gh"], 0, json.dumps(runs), "")
            with self.assertRaises(ReleaseAborted) as ctx:
                check_ci_precondition(self.root, head_sha=self.head_sha)
            self.assertIn(conclusion, str(ctx.exception))

    @patch("shutil.which", return_value="/usr/bin/gh")
    @patch("alongkit.proc.git")
    @patch("alongkit.proc.run_capture")
    def test_ci_pending_aborts_with_hint(self, mock_run_capture, mock_git, mock_which):
        mock_git.side_effect = lambda args, cwd=None: (
            proc.Result(args, 0, "origin\n", "") if "remote" in args
            else proc.Result(args, 0, self.head_sha, "")
        )
        for status in ("in_progress", "queued", "pending"):
            runs = [
                {
                    "workflowName": "Tests",
                    "status": status,
                    "conclusion": "",
                    "url": "https://github.com/actdim/along/actions/runs/200",
                }
            ]
            mock_run_capture.return_value = proc.Result(["gh"], 0, json.dumps(runs), "")
            with self.assertRaises(ReleaseAborted) as ctx:
                check_ci_precondition(self.root, head_sha=self.head_sha)
            err = str(ctx.exception)
            self.assertIn(status, err)
            self.assertIn("--skip-ci", err)

    @patch("shutil.which", return_value="/usr/bin/gh")
    @patch("alongkit.proc.git")
    @patch("alongkit.proc.run_capture")
    def test_ci_missing_runs_aborts_with_hint(self, mock_run_capture, mock_git, mock_which):
        mock_git.side_effect = lambda args, cwd=None: (
            proc.Result(args, 0, "origin\n", "") if "remote" in args
            else proc.Result(args, 0, self.head_sha, "")
        )
        mock_run_capture.return_value = proc.Result(["gh"], 0, "[]", "")

        with self.assertRaises(ReleaseAborted) as ctx:
            check_ci_precondition(self.root, head_sha=self.head_sha)
        err = str(ctx.exception)
        self.assertIn("no CI runs recorded", err)
        self.assertIn("--skip-ci", err)

    @patch("shutil.which", return_value=None)
    def test_ci_no_gh_warns_and_proceeds(self, mock_which):
        buf = io.StringIO()
        with patch("sys.stderr", buf):
            check_ci_precondition(self.root, head_sha=self.head_sha)
        self.assertIn("'gh' CLI not found; skipping CI check", buf.getvalue())

    @patch("shutil.which", return_value="/usr/bin/gh")
    @patch("alongkit.proc.git")
    def test_ci_no_remote_warns_and_proceeds(self, mock_git, mock_which):
        mock_git.return_value = proc.Result(["git", "remote"], 0, "", "")
        buf = io.StringIO()
        with patch("sys.stderr", buf):
            check_ci_precondition(self.root, head_sha=self.head_sha)
        self.assertIn("no git remote; skipping CI check", buf.getvalue())

    def test_ci_no_workflow_files_warns_and_proceeds(self):
        os.remove(self.workflow_file)
        buf = io.StringIO()
        with patch("sys.stderr", buf):
            check_ci_precondition(self.root, head_sha=self.head_sha)
        self.assertIn("no workflow files in .github/workflows/; skipping CI check", buf.getvalue())

    @patch("shutil.which", return_value="/usr/bin/gh")
    @patch("alongkit.proc.run_capture")
    def test_ci_opt_out_in_config(self, mock_run_capture, mock_which):
        self.write_config({"require_ci": False})
        # When require_ci is false, it returns early without querying runs
        check_ci_precondition(self.root, head_sha=self.head_sha)
        self.assertFalse(mock_run_capture.called)

    @patch("shutil.which", return_value="/usr/bin/gh")
    @patch("alongkit.proc.git")
    @patch("alongkit.proc.run_capture")
    def test_ci_specific_workflow_filtering_success(self, mock_run_capture, mock_git, mock_which):
        self.write_config({"ci_workflow": "Tests"})
        mock_git.side_effect = lambda args, cwd=None: (
            proc.Result(args, 0, "origin\n", "") if "remote" in args
            else proc.Result(args, 0, self.head_sha, "")
        )
        runs = [
            {
                "workflowName": "Docs",
                "status": "completed",
                "conclusion": "failure",
                "url": "http://docs",
            },
            {
                "workflowName": "Tests",
                "status": "completed",
                "conclusion": "success",
                "url": "http://tests",
            },
        ]
        mock_run_capture.return_value = proc.Result(["gh"], 0, json.dumps(runs), "")

        # Tests workflow is green, Docs failure is filtered out
        check_ci_precondition(self.root, head_sha=self.head_sha)

    @patch("shutil.which", return_value="/usr/bin/gh")
    @patch("alongkit.proc.git")
    @patch("alongkit.proc.run_capture")
    def test_ci_specific_workflow_missing_aborts(self, mock_run_capture, mock_git, mock_which):
        self.write_config({"ci_workflow": "Tests"})
        mock_git.side_effect = lambda args, cwd=None: (
            proc.Result(args, 0, "origin\n", "") if "remote" in args
            else proc.Result(args, 0, self.head_sha, "")
        )
        runs = [
            {
                "workflowName": "Docs",
                "status": "completed",
                "conclusion": "success",
                "url": "http://docs",
            }
        ]
        mock_run_capture.return_value = proc.Result(["gh"], 0, json.dumps(runs), "")

        with self.assertRaises(ReleaseAborted) as ctx:
            check_ci_precondition(self.root, head_sha=self.head_sha)
        self.assertIn("no CI runs for workflow 'Tests'", str(ctx.exception))

    def test_ci_skip_ci_with_reason_proceeds(self):
        buf = io.StringIO()
        with patch("sys.stderr", buf):
            check_ci_precondition(self.root, head_sha=self.head_sha, skip_ci=True, skip_reason="emergency hotfix")
        self.assertIn("Release CI precondition skipped: emergency hotfix", buf.getvalue())

    def test_ci_skip_ci_without_reason_aborts(self):
        for invalid_reason in (None, "", "   "):
            with self.assertRaises(ReleaseAborted) as ctx:
                check_ci_precondition(self.root, head_sha=self.head_sha, skip_ci=True, skip_reason=invalid_reason)
            self.assertIn("--skip-ci requires --reason", str(ctx.exception))

    @patch("along_version_bump.check_ci_precondition")
    @patch("alongkit.gates.run_test_gate", return_value=gates.TESTS_PASSED)
    @patch("alongkit.gates.run_sanitizer")
    @patch("alongkit.gates.link_integrity_gate", return_value=True)
    def test_release_preflight_passes_skip_ci_to_precondition(
        self, mock_link, mock_sanitizer, mock_test_gate, mock_check_ci
    ):
        mock_report = MagicMock()
        mock_report.clean = True
        mock_report.skipped = []
        mock_report.files_scanned = 1
        mock_sanitizer.return_value = mock_report

        release_preflight(self.root, skip_ci=True, skip_reason="hotfix")
        mock_check_ci.assert_called_once_with(
            self.root, head_sha=None, skip_ci=True, skip_reason="hotfix"
        )


if __name__ == "__main__":
    unittest.main()
