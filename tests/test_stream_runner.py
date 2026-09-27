#!/usr/bin/env python3
"""tests/test_stream_runner.py - Unit and hermetic integration tests for ChunkedStreamSupervisor."""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit.runner.stream import ChunkedStreamSupervisor


class TestChunkedStreamSupervisor(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp(prefix="along-test-stream-")
        self.repo_root = self.tmp_dir

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_module_guard(self) -> None:
        cmd = [sys.executable, os.path.join(SCRIPTS_DIR, "alongkit", "runner", "stream.py")]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("stream.py is a library module, not a command.", proc.stderr + proc.stdout)

    def test_init_defaults(self) -> None:
        mock_process = MagicMock(spec=subprocess.Popen)
        supervisor = ChunkedStreamSupervisor(process=mock_process)
        self.assertIs(supervisor.process, mock_process)
        self.assertIsNone(supervisor.tracer)
        self.assertEqual(supervisor.repo_root, os.getcwd())
        self.assertIsNone(supervisor.run_id)
        self.assertEqual(supervisor.chunk_size, 65536)
        self.assertEqual(supervisor.chunk_timeout, 0.2)
        self.assertTrue(supervisor.tee)
        self.assertEqual(supervisor.get_logs(), ("", ""))

    def test_init_custom_params(self) -> None:
        mock_process = MagicMock(spec=subprocess.Popen)
        mock_tracer = MagicMock()
        supervisor = ChunkedStreamSupervisor(
            process=mock_process,
            tracer=mock_tracer,
            repo_root=self.repo_root,
            run_id="test-run-123",
            chunk_size=1024,
            chunk_timeout=0.05,
            tee=False,
        )
        self.assertIs(supervisor.tracer, mock_tracer)
        self.assertEqual(supervisor.repo_root, os.path.abspath(self.repo_root))
        self.assertEqual(supervisor.run_id, "test-run-123")
        self.assertEqual(supervisor.chunk_size, 1024)
        self.assertEqual(supervisor.chunk_timeout, 0.05)
        self.assertFalse(supervisor.tee)

    def test_capture_stdout_and_stderr(self) -> None:
        cmd = [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(b'hello out\\n'); sys.stdout.buffer.flush(); sys.stderr.buffer.write(b'hello err\\n'); sys.stderr.buffer.flush()",
        ]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        supervisor = ChunkedStreamSupervisor(
            process=proc,
            repo_root=self.repo_root,
            tee=False,
        )
        supervisor.start()
        exit_code = supervisor.wait(timeout=10.0)
        self.assertEqual(exit_code, 0)
        stdout_log, stderr_log = supervisor.get_logs()
        self.assertEqual(stdout_log, "hello out\n")
        self.assertEqual(stderr_log, "hello err\n")

    def test_tee_output_buffering(self) -> None:
        fake_stdout = io.StringIO()
        fake_stderr = io.StringIO()
        cmd = [
            sys.executable,
            "-c",
            "import sys; sys.stdout.write('piped stdout'); sys.stderr.write('piped stderr')",
        ]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        supervisor = ChunkedStreamSupervisor(
            process=proc,
            repo_root=self.repo_root,
            tee=True,
        )
        with patch("sys.stdout", fake_stdout), patch("sys.stderr", fake_stderr):
            exit_code = supervisor.wait(timeout=10.0)

        self.assertEqual(exit_code, 0)
        self.assertIn("piped stdout", fake_stdout.getvalue())
        self.assertIn("piped stderr", fake_stderr.getvalue())

    def test_telemetry_span_events(self) -> None:
        mock_span = MagicMock()
        mock_tracer = MagicMock()
        mock_tracer.active_span.return_value = mock_span

        cmd = [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(b'telemetry test payload\\n')",
        ]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        supervisor = ChunkedStreamSupervisor(
            process=proc,
            tracer=mock_tracer,
            repo_root=self.repo_root,
            tee=False,
        )
        exit_code = supervisor.wait(timeout=10.0)
        self.assertEqual(exit_code, 0)

        mock_span.add_event.assert_called()
        call_args = mock_span.add_event.call_args_list
        event_names = [call[0][0] for call in call_args]
        self.assertIn("stdout.chunk", event_names)
        found_payload = False
        for call in call_args:
            attrs = call[1].get("attributes", {})
            if attrs.get("stream") == "stdout" and "telemetry test payload" in attrs.get("text_preview", ""):
                found_payload = True
                self.assertGreater(attrs.get("bytes", 0), 0)
        self.assertTrue(found_payload)

    def test_telemetry_exception_does_not_break_supervisor(self) -> None:
        mock_span = MagicMock()
        mock_span.add_event.side_effect = RuntimeError("telemetry broken")
        mock_tracer = MagicMock()
        mock_tracer.active_span.return_value = mock_span

        cmd = [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(b'resilience output\\n')",
        ]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        supervisor = ChunkedStreamSupervisor(
            process=proc,
            tracer=mock_tracer,
            repo_root=self.repo_root,
            tee=False,
        )
        exit_code = supervisor.wait(timeout=10.0)
        self.assertEqual(exit_code, 0)
        stdout_log, _ = supervisor.get_logs()
        self.assertEqual(stdout_log, "resilience output\n")

    def test_artifact_logs_saved_on_wait(self) -> None:
        run_id = "test-run-artifacts-456"
        cmd = [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(b'stdout saved\\n'); sys.stderr.buffer.write(b'stderr saved\\n')",
        ]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        supervisor = ChunkedStreamSupervisor(
            process=proc,
            repo_root=self.repo_root,
            run_id=run_id,
            tee=False,
        )
        exit_code = supervisor.wait(timeout=10.0)
        self.assertEqual(exit_code, 0)

        artifacts_dir = os.path.join(self.repo_root, ".along", "artifacts", run_id)
        stdout_file = os.path.join(artifacts_dir, "stdout.log")
        stderr_file = os.path.join(artifacts_dir, "stderr.log")

        self.assertTrue(os.path.isfile(stdout_file))
        self.assertTrue(os.path.isfile(stderr_file))

        with open(stdout_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "stdout saved\n")
        with open(stderr_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "stderr saved\n")

    def test_none_streams_graceful_handling(self) -> None:
        mock_process = MagicMock(spec=subprocess.Popen)
        mock_process.stdout = None
        mock_process.stderr = None
        mock_process.wait.return_value = 0
        mock_process.returncode = 0

        supervisor = ChunkedStreamSupervisor(process=mock_process, repo_root=self.repo_root, tee=False)
        supervisor.start()
        exit_code = supervisor.wait(timeout=5.0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(supervisor.get_logs(), ("", ""))

    def test_forced_flush_on_chunk_size(self) -> None:
        # Generate 1000 bytes with chunk_size 256
        data_chunk = "A" * 1000
        cmd = [
            sys.executable,
            "-c",
            f"import sys; sys.stdout.buffer.write(b'{data_chunk}')",
        ]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        supervisor = ChunkedStreamSupervisor(
            process=proc,
            repo_root=self.repo_root,
            chunk_size=256,
            chunk_timeout=10.0,
            tee=False,
        )
        exit_code = supervisor.wait(timeout=10.0)
        self.assertEqual(exit_code, 0)
        stdout_log, _ = supervisor.get_logs()
        self.assertEqual(stdout_log, data_chunk)
        self.assertGreater(len(supervisor._stdout_chunks), 1)


if __name__ == "__main__":
    unittest.main()
