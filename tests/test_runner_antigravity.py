#!/usr/bin/env python3
"""tests/test_runner_antigravity.py - Hermetic tests for AntigravityRunner and CLI dispatch."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit.runner.antigravity import AntigravityRunner
from alongkit.telemetry.models import SpanKind, StatusCode
from alongkit.telemetry.tracer import Tracer


class TestAntigravityRunner(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp(prefix="along-test-antigravity-")
        self.repo_root = self.tmp_dir
        self.along_dir = os.path.join(self.repo_root, ".along")
        self.issues_dir = os.path.join(self.along_dir, "ISSUES")
        os.makedirs(self.issues_dir, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_issue(self, slug: str, status: str = "in-progress") -> str:
        issue_path = os.path.join(self.issues_dir, f"feat--{slug}.md")
        content = (
            "---\n"
            "protocol: along\n"
            'protocol_version: "4.2.0"\n'
            f"slug: {slug}\n"
            "type: feat\n"
            f"status: {status}\n"
            "priority: medium\n"
            "created: 2026-09-27\n"
            "updated: 2026-09-27\n"
            "---\n\n"
            f"# Feature: {slug}\n"
        )
        with open(issue_path, "w", encoding="utf-8") as f:
            f.write(content)
        return issue_path

    def test_module_guard(self) -> None:
        cmd = [sys.executable, os.path.join(SCRIPTS_DIR, "alongkit", "runner", "antigravity.py")]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("antigravity.py is a library module, not a command.", proc.stderr + proc.stdout)

    def test_init_defaults(self) -> None:
        runner = AntigravityRunner(repo_root=self.repo_root)
        self.assertEqual(runner.repo_root, os.path.abspath(self.repo_root))
        self.assertIsNone(runner.issue_slug)
        self.assertIsNotNone(runner.run_id)
        self.assertIsNone(runner.otel_endpoint)
        self.assertIsNone(runner.binary_path)
        self.assertFalse(runner.dry_run)
        self.assertEqual(runner.extra_args, [])

    def test_resolve_binary_custom(self) -> None:
        runner = AntigravityRunner(repo_root=self.repo_root, binary_path="/custom/path/antigravity")
        self.assertEqual(runner.resolve_binary(), "/custom/path/antigravity")

    def test_resolve_binary_fallback(self) -> None:
        with patch("shutil.which", return_value=None), patch("os.path.isfile", return_value=False):
            runner = AntigravityRunner(repo_root=self.repo_root)
            self.assertEqual(runner.resolve_binary(), "antigravity")

    def test_resolve_active_issue_explicit(self) -> None:
        self._create_issue("my-feature", status="in-progress")
        runner = AntigravityRunner(repo_root=self.repo_root, issue_slug="my-feature")
        resolved = runner.resolve_active_issue()
        self.assertEqual(resolved, "my-feature")

    def test_resolve_active_issue_auto_scan(self) -> None:
        self._create_issue("auto-feature", status="in-progress")
        runner = AntigravityRunner(repo_root=self.repo_root)
        resolved = runner.resolve_active_issue()
        self.assertEqual(resolved, "auto-feature")

    def test_resolve_active_issue_fails_when_none(self) -> None:
        runner = AntigravityRunner(repo_root=self.repo_root)
        with self.assertRaises(RuntimeError) as ctx:
            runner.resolve_active_issue()
        self.assertIn("Cannot run Antigravity: no active in-progress issue found", str(ctx.exception))

    def test_resolve_active_issue_dry_run_defaults_to_adhoc(self) -> None:
        runner = AntigravityRunner(repo_root=self.repo_root, dry_run=True)
        resolved = runner.resolve_active_issue()
        self.assertEqual(resolved, "adhoc")

    def test_build_env(self) -> None:
        self._create_issue("test-feature", status="in-progress")
        runner = AntigravityRunner(
            repo_root=self.repo_root,
            run_id="run-uuid-1234",
            otel_endpoint="http://collector:4318/v1/traces",
        )
        env = runner.build_env()
        self.assertEqual(env["ALONG_RUN_ID"], "run-uuid-1234")
        self.assertEqual(env["ALONG_ISSUE_SLUG"], "test-feature")
        self.assertEqual(env["ALONG_REPO_ROOT"], self.repo_root)
        self.assertEqual(env["ALONG_OBSERVABILITY_LEVEL"], "complete")
        self.assertEqual(env["ALONG_OBSERVABILITY_SOURCES"], "antigravity_hook,stdout_stream")
        self.assertEqual(env["ALONG_OTEL_ENDPOINT"], "http://collector:4318/v1/traces")
        self.assertEqual(env["PYTHONIOENCODING"], "utf-8")
        self.assertEqual(env["PYTHONUTF8"], "1")

    def test_dry_run_output(self) -> None:
        self._create_issue("dry-feature", status="in-progress")
        runner = AntigravityRunner(
            repo_root=self.repo_root,
            run_id="dry-run-id-999",
            dry_run=True,
            binary_path="custom-agy",
        )
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            code = runner.run()
        self.assertEqual(code, 0)
        output = captured.getvalue()
        data = json.loads(output)
        self.assertEqual(data["binary"], "custom-agy")
        self.assertEqual(data["issue_slug"], "dry-feature")
        self.assertEqual(data["run_id"], "dry-run-id-999")
        self.assertEqual(data["env"]["ALONG_RUN_ID"], "dry-run-id-999")

    def test_run_spawns_process_and_captures_telemetry(self) -> None:
        self._create_issue("exec-feature", status="in-progress")
        mock_script = os.path.join(self.repo_root, "mock_agent.py")
        with open(mock_script, "w", encoding="utf-8") as f:
            f.write(
                "import sys\n"
                "sys.stdout.write('agent started\\n')\n"
                "sys.stdout.flush()\n"
                "sys.stderr.write('agent warning\\n')\n"
                "sys.stderr.flush()\n"
                "sys.exit(0)\n"
            )

        runner = AntigravityRunner(
            repo_root=self.repo_root,
            binary_path=sys.executable,
            extra_args=[mock_script],
            run_id="test-run-trace",
        )
        exit_code = runner.run()
        self.assertEqual(exit_code, 0)

        # Verify artifacts written
        artifacts_dir = os.path.join(self.repo_root, ".along", "artifacts", "test-run-trace")
        self.assertTrue(os.path.isdir(artifacts_dir))
        stdout_file = os.path.join(artifacts_dir, "stdout.log")
        stderr_file = os.path.join(artifacts_dir, "stderr.log")
        self.assertTrue(os.path.isfile(stdout_file))
        self.assertTrue(os.path.isfile(stderr_file))
        with open(stdout_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "agent started")
        with open(stderr_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "agent warning")

    def test_run_exit_code_preservation(self) -> None:
        self._create_issue("fail-feature", status="in-progress")
        mock_script = os.path.join(self.repo_root, "mock_fail.py")
        with open(mock_script, "w", encoding="utf-8") as f:
            f.write("import sys; sys.exit(42)\n")

        runner = AntigravityRunner(
            repo_root=self.repo_root,
            binary_path=sys.executable,
            extra_args=[mock_script],
            run_id="test-run-fail",
        )
        exit_code = runner.run()
        self.assertEqual(exit_code, 42)


class TestCliDispatchAntigravity(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp(prefix="along-test-cli-")
        self.repo_root = self.tmp_dir
        self.along_dir = os.path.join(self.repo_root, ".along")
        self.issues_dir = os.path.join(self.along_dir, "ISSUES")
        os.makedirs(self.issues_dir, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_issue(self, slug: str, status: str = "in-progress") -> str:
        issue_path = os.path.join(self.issues_dir, f"feat--{slug}.md")
        content = (
            "---\n"
            "protocol: along\n"
            'protocol_version: "4.2.0"\n'
            f"slug: {slug}\n"
            "type: feat\n"
            f"status: {status}\n"
            "priority: medium\n"
            "created: 2026-09-27\n"
            "updated: 2026-09-27\n"
            "---\n\n"
            f"# Feature: {slug}\n"
        )
        with open(issue_path, "w", encoding="utf-8") as f:
            f.write(content)
        return issue_path

    def test_along_run_antigravity_help(self) -> None:
        cmd = [sys.executable, os.path.join(SCRIPTS_DIR, "along_exec.py"), "run", "antigravity", "--help"]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=self.repo_root)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Usage: along run antigravity", proc.stdout)
        self.assertIn("--dry-run", proc.stdout)

    def test_along_run_antigravity_dry_run_cli(self) -> None:
        self._create_issue("cli-feature", status="in-progress")
        cmd = [
            sys.executable,
            os.path.join(SCRIPTS_DIR, "along_exec.py"),
            "run",
            "antigravity",
            "--dry-run",
            "--run-id",
            "cli-run-123",
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=self.repo_root)
        self.assertEqual(proc.returncode, 0)
        self.assertIn('"issue_slug": "cli-feature"', proc.stdout)
        self.assertIn('"run_id": "cli-run-123"', proc.stdout)

    def test_along_run_agy_alias(self) -> None:
        self._create_issue("agy-feature", status="in-progress")
        cmd = [
            sys.executable,
            os.path.join(SCRIPTS_DIR, "along_exec.py"),
            "run",
            "agy",
            "--dry-run",
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=self.repo_root)
        self.assertEqual(proc.returncode, 0)
        self.assertIn('"issue_slug": "agy-feature"', proc.stdout)

    def test_along_run_fails_fast_on_missing_issue(self) -> None:
        cmd = [
            sys.executable,
            os.path.join(SCRIPTS_DIR, "along_exec.py"),
            "run",
            "antigravity",
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=self.repo_root)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Cannot run Antigravity: no active in-progress issue found", proc.stderr)


if __name__ == "__main__":
    unittest.main()
