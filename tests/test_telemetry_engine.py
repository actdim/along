#!/usr/bin/env python3
"""
tests/test_telemetry_engine.py - Unit and integration tests for Along telemetry tracer engine.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import proc
from alongkit.telemetry import (
    ArtifactOffloader,
    OTLPExporter,
    Redactor,
    Span,
    SpanKind,
    Spooler,
    StatusCode,
    Tracer,
    conventions,
)


class TestTracerInitializationAndHierarchy(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.repo_root = self.tmp_dir.name
        self.mock_exporter = MagicMock(spec=OTLPExporter)
        self.mock_exporter.export.return_value = True

    def tearDown(self) -> None:
        Tracer.set_active(None)
        self.tmp_dir.cleanup()

    def test_init_defaults(self) -> None:
        tracer = Tracer(
            repo_root=self.repo_root,
            exporter=self.mock_exporter,
        )
        self.assertIsNotNone(tracer.run_id)
        self.assertEqual(len(tracer.trace_id), 32)
        self.assertTrue(all(c in "0123456789abcdef" for c in tracer.trace_id))
        self.assertIsNone(tracer.active_span_id)
        self.assertIsNone(tracer.active_span)
        self.assertIsNone(tracer.root_span)
        self.assertTrue(tracer.auto_flush)
        self.assertEqual(tracer.issue_slug, "adhoc")
        self.assertEqual(tracer.agent_name, "antigravity")

    def test_init_custom_run_id_and_trace_id(self) -> None:
        custom_uuid = "372d529a-fe5e-4c53-92e3-96b08d799b5a"
        tracer = Tracer(
            repo_root=self.repo_root,
            run_id=custom_uuid,
            issue_slug="feat--core",
            agent_name="custom_agent",
            exporter=self.mock_exporter,
            auto_flush=False,
            service_name="test-along",
        )
        self.assertEqual(tracer.run_id, custom_uuid)
        self.assertEqual(tracer.trace_id, "372d529afe5e4c5392e396b08d799b5a")
        self.assertEqual(tracer.issue_slug, "feat--core")
        self.assertEqual(tracer.agent_name, "custom_agent")
        self.assertFalse(tracer.auto_flush)
        self.assertEqual(tracer.service_name, "test-along")

    def test_start_run_root_span_creation(self) -> None:
        tracer = Tracer(
            repo_root=self.repo_root,
            run_id="run-root-test-01",
            issue_slug="feat--tracer",
            agent_name="antigravity",
            exporter=self.mock_exporter,
        )
        root_span = tracer.start_run(
            observability_level="detailed",
            sources=["cli", "tool"],
        )
        self.assertIsNotNone(root_span)
        self.assertEqual(root_span.kind, SpanKind.AGENT)
        self.assertEqual(root_span.trace_id, tracer.trace_id)
        self.assertIsNone(root_span.parent_span_id)
        self.assertEqual(tracer.active_span_id, root_span.span_id)
        self.assertIs(tracer.active_span, root_span)
        self.assertIs(Tracer.get_active(), tracer)

        # Verify semantic attributes
        attrs = root_span.attributes
        self.assertEqual(attrs[conventions.SPAN_KIND], "AGENT")
        self.assertEqual(attrs[conventions.ALONG_RUN_ID], "run-root-test-01")
        self.assertEqual(attrs[conventions.ALONG_ISSUE_SLUG], "feat--tracer")
        self.assertEqual(attrs[conventions.ALONG_AGENT_NAME], "antigravity")
        self.assertEqual(attrs[conventions.ALONG_REPO_ROOT], tracer.repo_root)
        self.assertEqual(attrs[conventions.ALONG_OBSERVABILITY_LEVEL], "detailed")
        self.assertEqual(attrs[conventions.ALONG_OBSERVABILITY_SOURCES], ["cli", "tool"])
        self.assertEqual(attrs[conventions.SERVICE_NAME], "actdim-along")

    def test_turn_tool_llm_span_hierarchy(self) -> None:
        tracer = Tracer(
            repo_root=self.repo_root,
            exporter=self.mock_exporter,
            auto_flush=False,
        )
        root = tracer.start_run()

        with tracer.turn_span(1, "Analysis", phase="planning") as turn_span:
            self.assertEqual(turn_span.kind, SpanKind.CHAIN)
            self.assertEqual(turn_span.parent_span_id, root.span_id)
            self.assertEqual(tracer.active_span_id, turn_span.span_id)
            self.assertEqual(turn_span.attributes[conventions.ALONG_TURN_SEQ], 1)
            self.assertEqual(turn_span.attributes[conventions.ALONG_TURN_TITLE], "Analysis")
            self.assertEqual(turn_span.attributes[conventions.ALONG_TURN_PHASE], "planning")

            # Nested tool span
            with tracer.tool_span("read_file", {"path": "src/app.py"}) as tool_span:
                self.assertEqual(tool_span.kind, SpanKind.TOOL)
                self.assertEqual(tool_span.parent_span_id, turn_span.span_id)
                self.assertEqual(tracer.active_span_id, tool_span.span_id)
                self.assertEqual(tool_span.attributes[conventions.TOOL_NAME], "read_file")

            # Stack unwound to turn span
            self.assertEqual(tracer.active_span_id, turn_span.span_id)

            # Nested LLM span
            with tracer.llm_span("claude-3-7-sonnet", system="anthropic") as llm_span:
                self.assertEqual(llm_span.kind, SpanKind.LLM)
                self.assertEqual(llm_span.parent_span_id, turn_span.span_id)
                self.assertEqual(tracer.active_span_id, llm_span.span_id)
                self.assertEqual(llm_span.attributes[conventions.GEN_AI_SYSTEM], "anthropic")
                self.assertEqual(llm_span.attributes[conventions.GEN_AI_REQUEST_MODEL], "claude-3-7-sonnet")
                self.assertEqual(llm_span.attributes[conventions.LLM_MODEL_NAME], "claude-3-7-sonnet")

            # Stack unwound to turn span
            self.assertEqual(tracer.active_span_id, turn_span.span_id)

        # Stack unwound to root span
        self.assertEqual(tracer.active_span_id, root.span_id)

        tracer.end_run()
        self.assertIsNone(Tracer.get_active())
        self.assertEqual(root.status_code, StatusCode.OK)

        # Verify buffered spans list (completed in reverse-nesting order)
        buffered = tracer.buffered_spans
        self.assertEqual(len(buffered), 3)  # tool, llm, turn
        self.assertEqual(buffered[0], tool_span)
        self.assertEqual(buffered[1], llm_span)
        self.assertEqual(buffered[2], turn_span)

    def test_span_exception_recording(self) -> None:
        tracer = Tracer(
            repo_root=self.repo_root,
            exporter=self.mock_exporter,
            auto_flush=False,
        )
        tracer.start_run()

        with self.assertRaises(ZeroDivisionError):
            with tracer.turn_span(1, "faulty_turn"):
                _ = 1 / 0

        self.assertEqual(len(tracer.buffered_spans), 1)
        faulty = tracer.buffered_spans[0]
        self.assertEqual(faulty.status_code, StatusCode.ERROR)
        self.assertIn("division by zero", faulty.status_message)


class TestSecretMaskingInTelemetry(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.repo_root = self.tmp_dir.name
        self.mock_exporter = MagicMock(spec=OTLPExporter)
        self.tracer = Tracer(
            repo_root=self.repo_root,
            exporter=self.mock_exporter,
            auto_flush=False,
        )
        self.tracer.start_run()

    def tearDown(self) -> None:
        Tracer.set_active(None)
        self.tmp_dir.cleanup()

    def test_tool_parameters_redaction(self) -> None:
        raw_params = {
            "api_key": "sk-ant-api03-123456789012345678901234567890",
            "token": "ghp_123456789012345678901234",
            "password": "super_secret_password",
            "command": "git push origin main",
            "home": "/home/developer/repo",
            "prompt": "Here is the key: sk-ant-api03-123456789012345678901234567890 in text",
        }
        with self.tracer.tool_span("bash", raw_params) as span:
            params_str = span.attributes[conventions.TOOL_PARAMETERS]
            sanitized = json.loads(params_str)
            self.assertEqual(sanitized["api_key"], "[REDACTED]")
            self.assertEqual(sanitized["token"], "[REDACTED_GITHUB_TOKEN]")
            self.assertEqual(sanitized["password"], "[REDACTED]")
            self.assertEqual(sanitized["command"], "git push origin main")
            self.assertEqual(sanitized["home"], "~/repo")
            self.assertEqual(sanitized["prompt"], "Here is the key: sk-ant-[REDACTED] in text")

    def test_command_line_sanitization(self) -> None:
        with self.tracer.tool_span("bash") as span:
            cmd = ["curl", "-H", "Authorization: Bearer secret-auth-token-12345", "https://api.example.com"]
            self.tracer.record_command_result(
                span=span,
                cmd=cmd,
                exit_code=0,
                stdout="OK",
                pid=1234,
            )
            cmd_attr = span.attributes[conventions.PROCESS_COMMAND_LINE]
            self.assertIn("Authorization: Bearer [REDACTED]", cmd_attr)
            self.assertNotIn("secret-auth-token-12345", cmd_attr)
            self.assertEqual(span.attributes[conventions.PROCESS_EXIT_CODE], 0)
            self.assertEqual(span.attributes[conventions.PROCESS_PID], 1234)


class TestProcessResultRecordingAndOffloading(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.repo_root = self.tmp_dir.name
        self.mock_exporter = MagicMock(spec=OTLPExporter)
        self.tracer = Tracer(
            repo_root=self.repo_root,
            exporter=self.mock_exporter,
            auto_flush=False,
        )
        self.tracer.start_run()

    def tearDown(self) -> None:
        Tracer.set_active(None)
        self.tmp_dir.cleanup()

    def test_small_output_not_offloaded(self) -> None:
        with self.tracer.tool_span("exec") as span:
            small_text = "compilation succeeded\n3 warnings\n0 errors"
            self.tracer.record_command_result(
                span=span,
                cmd=["compiler", "build"],
                exit_code=0,
                stdout=small_text,
            )
            self.assertNotIn(conventions.ALONG_ARTIFACT_OFFLOADED, span.attributes)
            self.assertEqual(span.attributes[conventions.OUTPUT_VALUE], small_text)

    def test_heavy_output_bytes_offloaded(self) -> None:
        with self.tracer.tool_span("exec") as span:
            # Over default 10240 bytes
            large_text = "DUMP_LINE_" + ("A" * 100) + "\n"
            large_text = large_text * 120  # ~13KB
            self.tracer.record_command_result(
                span=span,
                cmd=["dump_state"],
                exit_code=0,
                stdout=large_text,
            )
            self.assertTrue(span.attributes.get(conventions.ALONG_ARTIFACT_OFFLOADED))
            artifact_rel_path = span.attributes.get(conventions.ALONG_ARTIFACT_REF)
            sha256 = span.attributes.get(conventions.ALONG_ARTIFACT_SHA256)
            self.assertIsNotNone(artifact_rel_path)
            self.assertIsNotNone(sha256)

            # Check artifact existence on disk
            full_path = os.path.join(self.repo_root, artifact_rel_path)
            self.assertTrue(os.path.isfile(full_path))
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertEqual(hashlib.sha256(content.encode("utf-8")).hexdigest(), sha256)

            # Check preview in OUTPUT_VALUE
            preview = span.attributes[conventions.OUTPUT_VALUE]
            self.assertIn("... [Output offloaded to", preview)

    def test_heavy_output_lines_offloaded(self) -> None:
        with self.tracer.tool_span("exec") as span:
            # Over default 50 lines but small in total bytes
            lines_content = "\n".join([f"line {i}" for i in range(75)])
            self.tracer.record_command_result(
                span=span,
                cmd=["list_items"],
                exit_code=0,
                stdout=lines_content,
            )
            self.assertTrue(span.attributes.get(conventions.ALONG_ARTIFACT_OFFLOADED))
            self.assertIn("... [Output offloaded to", span.attributes[conventions.OUTPUT_VALUE])

    def test_proc_run_capture_integration_explicit_span(self) -> None:
        with self.tracer.tool_span("python_runner") as span:
            res = proc.run_capture(
                [sys.executable, "-c", "import sys; sys.stdout.write('proc execution ok')"],
                telemetry_span=span,
                tracer=self.tracer,
            )
            self.assertTrue(res.ok)
            self.assertEqual(res.stdout, "proc execution ok")
            self.assertEqual(span.attributes[conventions.PROCESS_EXIT_CODE], 0)
            self.assertIsInstance(span.attributes.get(conventions.PROCESS_PID), int)
            self.assertGreater(span.attributes[conventions.PROCESS_PID], 0)
            self.assertEqual(span.attributes[conventions.OUTPUT_VALUE], "proc execution ok")

    def test_proc_run_capture_active_tracer_auto_detection(self) -> None:
        # Tracer is active in global context
        with self.tracer.tool_span("auto_detected_tool") as span:
            res = proc.run_capture([sys.executable, "-c", "import sys; sys.stdout.write('auto detected')"])
            self.assertTrue(res.ok)
            self.assertEqual(span.attributes[conventions.PROCESS_EXIT_CODE], 0)
            self.assertEqual(span.attributes[conventions.OUTPUT_VALUE], "auto detected")


class TestTraceLifecycleAndExportFailover(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.repo_root = self.tmp_dir.name

    def tearDown(self) -> None:
        Tracer.set_active(None)
        self.tmp_dir.cleanup()

    def test_successful_export_lifecycle(self) -> None:
        mock_exporter = MagicMock(spec=OTLPExporter)
        mock_exporter.export.return_value = True

        tracer = Tracer(
            repo_root=self.repo_root,
            exporter=mock_exporter,
            auto_flush=False,
        )
        tracer.start_run()
        with tracer.turn_span(1, "turn 1"):
            with tracer.tool_span("tool 1"):
                pass
        tracer.end_run()

        # In auto_flush=False, all spans are exported together at end_run
        mock_exporter.export.assert_called_once()
        exported_spans = mock_exporter.export.call_args[0][0]
        self.assertEqual(len(exported_spans), 3)  # root, turn 1, tool 1
        self.assertEqual(exported_spans[0].kind, SpanKind.AGENT)
        self.assertFalse(tracer.spooler.has_spool())

    def test_streaming_auto_flush_export(self) -> None:
        mock_exporter = MagicMock(spec=OTLPExporter)
        mock_exporter.export.return_value = True

        tracer = Tracer(
            repo_root=self.repo_root,
            exporter=mock_exporter,
            auto_flush=True,
        )
        tracer.start_run()
        with tracer.turn_span(1, "turn 1"):
            with tracer.tool_span("tool 1"):
                pass
            # tool 1 was flushed upon exiting its block
            self.assertEqual(mock_exporter.export.call_count, 1)

        # turn 1 was flushed upon exiting its block
        self.assertEqual(mock_exporter.export.call_count, 2)

        tracer.end_run()
        # root span flushed upon end_run
        self.assertEqual(mock_exporter.export.call_count, 3)

    @patch("urllib.request.urlopen")
    def test_wal_spooling_on_export_failure_and_recovery(self, mock_urlopen: MagicMock) -> None:
        # Simulate network error
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        real_exporter = OTLPExporter(
            endpoint="http://localhost:4318/v1/traces",
            spooler=Spooler(self.repo_root, "run-spool-test"),
        )
        tracer = Tracer(
            repo_root=self.repo_root,
            run_id="run-spool-test",
            exporter=real_exporter,
            auto_flush=False,
        )
        tracer.start_run()
        with tracer.turn_span(1, "turn 1"):
            pass
        tracer.end_run()

        # Network failed -> spans spooled to WAL
        self.assertTrue(tracer.spooler.has_spool())
        spooled_records = tracer.spooler.read_spool()
        self.assertEqual(len(spooled_records), 2)  # root and turn 1

        # Simulate network recovery
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.__enter__.return_value = mock_response

        flushed_count = tracer.exporter.flush_spool()
        self.assertEqual(flushed_count, 2)
        self.assertFalse(tracer.spooler.has_spool())

    def test_tracer_context_manager(self) -> None:
        mock_exporter = MagicMock(spec=OTLPExporter)
        mock_exporter.export.return_value = True

        with Tracer(repo_root=self.repo_root, exporter=mock_exporter) as tracer:
            self.assertIsNotNone(tracer.root_span)
            self.assertIs(Tracer.get_active(), tracer)
            with tracer.turn_span(1, "step"):
                pass

        self.assertIsNone(Tracer.get_active())
        self.assertEqual(tracer.root_span.status_code, StatusCode.OK)


if __name__ == "__main__":
    unittest.main()
