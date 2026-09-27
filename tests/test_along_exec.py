#!/usr/bin/env python3
"""
tests/test_along_exec.py - Hermetic unit and CLI integration tests for along_exec.py
telemetry commands (status, flush, router dispatch).
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import unittest
from unittest.mock import MagicMock, patch

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

import along_exec
import hermetic
from alongkit import proc


class TestAlongTelemetryCli(unittest.TestCase):
    def setUp(self):
        self.repo = hermetic.make_repo_fixture(prefix="along-exec-telemetry-test-")
        self.along_exec = os.path.join(SCRIPTS_DIR, "along_exec.py")
        self.spool_dir = os.path.join(self.repo, ".along", "telemetry", "spool")
        os.makedirs(self.spool_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_help_lists_telemetry_commands(self):
        res = proc.run_capture([sys.executable, self.along_exec, "--help"], cwd=self.repo)
        self.assertEqual(res.returncode, 0)
        self.assertIn("telemetry status", res.stdout)
        self.assertIn("telemetry flush", res.stdout)

    def test_telemetry_help(self):
        res = proc.run_capture([sys.executable, self.along_exec, "telemetry", "--help"], cwd=self.repo)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Usage: along telemetry", res.stdout)
        self.assertIn("status", res.stdout)
        self.assertIn("flush", res.stdout)

    def test_telemetry_unknown_subcommand(self):
        res = proc.run_capture([sys.executable, self.along_exec, "telemetry", "unknown"], cwd=self.repo)
        self.assertEqual(res.returncode, 1)
        self.assertIn("Unknown telemetry subcommand: 'unknown'", res.stderr)

    def test_status_empty_spool_text(self):
        res = proc.run_capture([sys.executable, self.along_exec, "telemetry", "status"], cwd=self.repo)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Along Telemetry Status:", res.stdout)
        self.assertIn("Pending WALs:  0 file(s)", res.stdout)
        self.assertIn("Spooled Size:  0 bytes", res.stdout)

    def test_status_empty_spool_json(self):
        res = proc.run_capture([sys.executable, self.along_exec, "telemetry", "status", "--json"], cwd=self.repo)
        self.assertEqual(res.returncode, 0)
        json_start = res.stdout.find("{")
        self.assertGreaterEqual(json_start, 0)
        data = json.loads(res.stdout[json_start:])
        self.assertEqual(data["wal_count"], 0)
        self.assertEqual(data["total_bytes"], 0)
        self.assertEqual(data["endpoint"], "http://localhost:4318/v1/traces")
        self.assertEqual(data["wal_files"], [])
        self.assertIn("connected", data)
        self.assertIn("endpoint_status", data)

    def test_status_with_spooled_wal_files(self):
        wal1 = os.path.join(self.spool_dir, "run-1.wal")
        wal2 = os.path.join(self.spool_dir, "run-2.wal")
        content1 = '{"name": "span1", "trace_id": "01", "span_id": "01"}\n'
        content2 = '{"name": "span2", "trace_id": "02", "span_id": "02"}\n'
        with open(wal1, "w", encoding="utf-8") as f:
            f.write(content1)
        with open(wal2, "w", encoding="utf-8") as f:
            f.write(content2)

        expected_bytes = os.path.getsize(wal1) + os.path.getsize(wal2)

        res = proc.run_capture([sys.executable, self.along_exec, "telemetry", "status", "--json"], cwd=self.repo)
        self.assertEqual(res.returncode, 0)
        json_start = res.stdout.find("{")
        self.assertGreaterEqual(json_start, 0)
        data = json.loads(res.stdout[json_start:])
        self.assertEqual(data["wal_count"], 2)
        self.assertEqual(data["total_bytes"], expected_bytes)
        file_names = [f["name"] for f in data["wal_files"]]
        self.assertIn("run-1.wal", file_names)
        self.assertIn("run-2.wal", file_names)

    def test_status_endpoint_override(self):
        custom_endpoint = "http://custom-otel:4318/v1/traces"
        res = proc.run_capture(
            [sys.executable, self.along_exec, "telemetry", "status", "--endpoint", custom_endpoint, "--json"],
            cwd=self.repo,
        )
        self.assertEqual(res.returncode, 0)
        json_start = res.stdout.find("{")
        self.assertGreaterEqual(json_start, 0)
        data = json.loads(res.stdout[json_start:])
        self.assertEqual(data["endpoint"], custom_endpoint)

    def test_flush_empty_spool(self):
        res = proc.run_capture([sys.executable, self.along_exec, "telemetry", "flush"], cwd=self.repo)
        self.assertEqual(res.returncode, 0)
        self.assertIn("No pending telemetry spans in spool.", res.stdout)

    def test_flush_success_removes_wal_files(self):
        wal1 = os.path.join(self.spool_dir, "run-success-1.wal")
        wal2 = os.path.join(self.spool_dir, "run-success-2.wal")
        span1 = {"name": "agent_run", "trace_id": "01", "span_id": "01"}
        span2 = {"name": "tool_call", "trace_id": "01", "span_id": "02"}
        with open(wal1, "w", encoding="utf-8") as f:
            f.write(json.dumps(span1) + "\n")
        with open(wal2, "w", encoding="utf-8") as f:
            f.write(json.dumps(span2) + "\n")

        with patch("alongkit.telemetry.otlp.OTLPExporter.export", return_value=True) as mock_export:
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                with self.assertRaises(SystemExit) as cm:
                    along_exec.handle_telemetry_command(self.repo, ["flush"])
                self.assertEqual(cm.exception.code, 0)
                output = mock_stdout.getvalue()
                self.assertIn("Successfully flushed 2 telemetry span(s)", output)

            mock_export.assert_called_once()
            exported_spans = mock_export.call_args[0][0]
            self.assertEqual(len(exported_spans), 2)

        # WAL files must be removed on successful flush
        self.assertFalse(os.path.exists(wal1))
        self.assertFalse(os.path.exists(wal2))

    def test_flush_network_failure_preserves_wal_files(self):
        wal1 = os.path.join(self.spool_dir, "run-fail.wal")
        span1 = {"name": "agent_run", "trace_id": "01", "span_id": "01"}
        with open(wal1, "w", encoding="utf-8") as f:
            f.write(json.dumps(span1) + "\n")

        with patch("alongkit.telemetry.otlp.OTLPExporter.export", return_value=False) as mock_export:
            with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
                with self.assertRaises(SystemExit) as cm:
                    along_exec.handle_telemetry_command(self.repo, ["flush"])
                self.assertEqual(cm.exception.code, 1)
                err_output = mock_stderr.getvalue()
                self.assertIn("Failed to flush 1 telemetry span(s)", err_output)

            mock_export.assert_called_once()

        # Fail-open guarantee: WAL files must be preserved on failure!
        self.assertTrue(os.path.exists(wal1))
        with open(wal1, "r", encoding="utf-8") as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 1)

    def test_endpoint_resolution_precedence(self):
        # 1. Default
        with patch.dict(os.environ, {}, clear=True):
            ep = along_exec._get_active_telemetry_endpoint()
            self.assertEqual(ep, "http://localhost:4318/v1/traces")

        # 2. OTEL_EXPORTER_OTLP_ENDPOINT
        with patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector:4318"}, clear=True):
            ep = along_exec._get_active_telemetry_endpoint()
            self.assertEqual(ep, "http://collector:4318/v1/traces")

        # 3. ALONG_TELEMETRY_ENDPOINT
        with patch.dict(os.environ, {"ALONG_TELEMETRY_ENDPOINT": "http://along-ep:5000"}, clear=True):
            ep = along_exec._get_active_telemetry_endpoint()
            self.assertEqual(ep, "http://along-ep:5000")

        # 4. OTEL_EXPORTER_OTLP_TRACES_ENDPOINT
        with patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://otel-traces:4318/v1/traces"}, clear=True):
            ep = along_exec._get_active_telemetry_endpoint()
            self.assertEqual(ep, "http://otel-traces:4318/v1/traces")

        # 5. Explicit CLI argument overrides all
        ep = along_exec._get_active_telemetry_endpoint("http://explicit:4318/v1/traces")
        self.assertEqual(ep, "http://explicit:4318/v1/traces")


class TestAlongMilestoneValidation(unittest.TestCase):
    def setUp(self):
        self.repo = hermetic.make_repo_fixture(prefix="along-exec-milestone-test-")
        self.along_exec = os.path.join(SCRIPTS_DIR, "along_exec.py")
        self.milestones_dir = os.path.join(self.repo, ".along", "MILESTONES")
        os.makedirs(self.milestones_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_milestone_create_and_collision_rejection(self):
        # 1. Create initial milestone
        res = proc.run_capture(
            [sys.executable, self.along_exec, "milestone", "create", "v5.0.0-initial", "--title", "Initial Release"],
            cwd=self.repo
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.milestones_dir, "v5.0.0-initial.md")))

        # 2. Reject exact SemVer collision
        res_exact = proc.run_capture(
            [sys.executable, self.along_exec, "milestone", "create", "v5.0.0-duplicate", "--title", "Duplicate Release"],
            cwd=self.repo
        )
        self.assertEqual(res_exact.returncode, 1)
        self.assertIn("Milestone exact SemVer collision (5.0.0)", res_exact.stderr)

        # 3. Reject minor version collision for active milestones
        res_minor = proc.run_capture(
            [sys.executable, self.along_exec, "milestone", "create", "v5.0.1-patch", "--title", "Patch Release"],
            cwd=self.repo
        )
        self.assertEqual(res_minor.returncode, 1)
        self.assertIn("Milestone minor version collision (5.0)", res_minor.stderr)

        # 4. Allow next minor version
        res_next = proc.run_capture(
            [sys.executable, self.along_exec, "milestone", "create", "v5.1.0-expansion", "--title", "Expansion"],
            cwd=self.repo
        )
        self.assertEqual(res_next.returncode, 0, res_next.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.milestones_dir, "v5.1.0-expansion.md")))

    def test_validate_entities_catches_collision_in_doctor(self):
        from alongkit import entities, textio

        # Write two colliding milestone files manually
        m1 = os.path.join(self.milestones_dir, "v5.0.0-track-a.md")
        m2 = os.path.join(self.milestones_dir, "v5.0.0-track-b.md")
        content1 = (
            "---\nprotocol: along\nslug: v5.0.0-track-a\ntitle: Track A\nstatus: open\ntarget_issues: []\n---\n"
        )
        content2 = (
            "---\nprotocol: along\nslug: v5.0.0-track-b\ntitle: Track B\nstatus: in-progress\ntarget_issues: []\n---\n"
        )
        textio.write_text(m1, content1)
        textio.write_text(m2, content2)

        report = entities.validate_entities(self.repo)
        self.assertFalse(report["clean"])
        error_msgs = [msg for _, msg in report["errors"]]
        self.assertTrue(any("collision" in msg.lower() for msg in error_msgs))


if __name__ == "__main__":
    unittest.main()
