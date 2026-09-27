#!/usr/bin/env python3
"""
tests/test_telemetry_models.py - Unit tests for Along telemetry data models.
"""

from __future__ import annotations

import json
import os
import sys
import time
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit.telemetry import conventions
from alongkit.telemetry.models import ArtifactRef, Span, SpanEvent, SpanKind, StatusCode


class TestSpanKindEnum(unittest.TestCase):
    def test_span_kind_values(self) -> None:
        self.assertEqual(SpanKind.AGENT, "AGENT")
        self.assertEqual(SpanKind.CHAIN, "CHAIN")
        self.assertEqual(SpanKind.TOOL, "TOOL")
        self.assertEqual(SpanKind.LLM, "LLM")
        self.assertTrue(isinstance(SpanKind.AGENT, str))
        self.assertTrue(isinstance(SpanKind.CHAIN, str))
        self.assertTrue(isinstance(SpanKind.TOOL, str))
        self.assertTrue(isinstance(SpanKind.LLM, str))


class TestStatusCodeEnum(unittest.TestCase):
    def test_status_code_values(self) -> None:
        self.assertEqual(StatusCode.UNSET, 0)
        self.assertEqual(StatusCode.OK, 1)
        self.assertEqual(StatusCode.ERROR, 2)
        self.assertTrue(isinstance(StatusCode.UNSET, int))
        self.assertTrue(isinstance(StatusCode.OK, int))
        self.assertTrue(isinstance(StatusCode.ERROR, int))


class TestArtifactRefModel(unittest.TestCase):
    def test_artifact_ref_creation_and_to_dict(self) -> None:
        ref = ArtifactRef(
            artifact_id="art-12345",
            path=".along/artifacts/diff_output.txt",
            sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            size_bytes=4096,
            line_count=120,
            mime_type="text/plain",
        )
        self.assertEqual(ref.artifact_id, "art-12345")
        self.assertEqual(ref.path, ".along/artifacts/diff_output.txt")
        self.assertEqual(ref.sha256, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        self.assertEqual(ref.size_bytes, 4096)
        self.assertEqual(ref.line_count, 120)
        self.assertEqual(ref.mime_type, "text/plain")

        as_dict = ref.to_dict()
        expected = {
            "artifact_id": "art-12345",
            "path": ".along/artifacts/diff_output.txt",
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "size_bytes": 4096,
            "line_count": 120,
            "mime_type": "text/plain",
        }
        self.assertEqual(as_dict, expected)
        # Verify JSON serializability
        encoded = json.dumps(as_dict)
        self.assertIn("art-12345", encoded)

    def test_artifact_ref_default_mime_type(self) -> None:
        ref = ArtifactRef(
            artifact_id="art-default",
            path=".along/artifacts/stdout.log",
            sha256="abc",
            size_bytes=100,
            line_count=10,
        )
        self.assertEqual(ref.mime_type, "text/plain")
        self.assertEqual(ref.to_dict()["mime_type"], "text/plain")


class TestSpanEventModel(unittest.TestCase):
    def test_span_event_creation_and_to_dict(self) -> None:
        ts = 1727271000000000000
        event = SpanEvent(
            name="cache_hit",
            timestamp_ns=ts,
            attributes={"cache.key": "hash_123", "hit": True},
        )
        self.assertEqual(event.name, "cache_hit")
        self.assertEqual(event.timestamp_ns, ts)
        self.assertEqual(event.attributes, {"cache.key": "hash_123", "hit": True})

        as_dict = event.to_dict()
        expected = {
            "name": "cache_hit",
            "timestamp_ns": ts,
            "attributes": {"cache.key": "hash_123", "hit": True},
        }
        self.assertEqual(as_dict, expected)
        self.assertEqual(json.dumps(as_dict), json.dumps(expected))

    def test_span_event_default_attributes_factory(self) -> None:
        event1 = SpanEvent(name="ev1", timestamp_ns=1)
        event2 = SpanEvent(name="ev2", timestamp_ns=2)
        event1.attributes["key"] = "val"
        self.assertNotIn("key", event2.attributes)


class TestSpanModel(unittest.TestCase):
    def test_span_creation_defaults(self) -> None:
        t0 = time.time_ns()
        span = Span(
            trace_id="trace-001",
            span_id="span-001",
            name="agent_turn",
            kind=SpanKind.AGENT,
            start_time_ns=t0,
        )
        self.assertEqual(span.trace_id, "trace-001")
        self.assertEqual(span.span_id, "span-001")
        self.assertEqual(span.name, "agent_turn")
        self.assertEqual(span.kind, SpanKind.AGENT)
        self.assertEqual(span.start_time_ns, t0)
        self.assertIsNone(span.end_time_ns)
        self.assertIsNone(span.parent_span_id)
        self.assertEqual(span.attributes, {})
        self.assertEqual(span.events, [])
        self.assertEqual(span.status_code, StatusCode.UNSET)
        self.assertEqual(span.status_message, "")

    def test_span_set_attribute(self) -> None:
        span = Span(
            trace_id="t1",
            span_id="s1",
            name="tool_call",
            kind=SpanKind.TOOL,
            start_time_ns=1000,
        )
        span.set_attribute(conventions.TOOL_NAME, "read_file")
        span.set_attribute(conventions.PROCESS_PID, 4321)
        self.assertEqual(span.attributes[conventions.TOOL_NAME], "read_file")
        self.assertEqual(span.attributes[conventions.PROCESS_PID], 4321)

    def test_span_add_event(self) -> None:
        span = Span(
            trace_id="t1",
            span_id="s1",
            name="inference",
            kind=SpanKind.LLM,
            start_time_ns=1000,
        )
        event = span.add_event("token_stream_start", {"chunk": 1})
        self.assertEqual(len(span.events), 1)
        self.assertEqual(span.events[0], event)
        self.assertEqual(event.name, "token_stream_start")
        self.assertEqual(event.attributes, {"chunk": 1})
        self.assertGreaterEqual(event.timestamp_ns, 1000)

    def test_span_add_event_explicit_timestamp(self) -> None:
        span = Span(
            trace_id="t1",
            span_id="s1",
            name="inference",
            kind=SpanKind.LLM,
            start_time_ns=1000,
        )
        event = span.add_event("token_stream_end", {"total": 50}, timestamp_ns=2000)
        self.assertEqual(event.timestamp_ns, 2000)
        self.assertEqual(event.attributes["total"], 50)

    def test_span_finish_defaults(self) -> None:
        t0 = time.time_ns()
        span = Span(
            trace_id="t1",
            span_id="s1",
            name="turn",
            kind=SpanKind.CHAIN,
            start_time_ns=t0,
        )
        self.assertIsNone(span.end_time_ns)
        span.finish()
        self.assertEqual(span.status_code, StatusCode.OK)
        self.assertEqual(span.status_message, "")
        self.assertIsNotNone(span.end_time_ns)
        self.assertGreaterEqual(span.end_time_ns, t0)

    def test_span_finish_error_and_explicit_time(self) -> None:
        t0 = 1000
        span = Span(
            trace_id="t1",
            span_id="s1",
            name="tool_call",
            kind=SpanKind.TOOL,
            start_time_ns=t0,
        )
        span.finish(status=StatusCode.ERROR, message="Command timed out", end_time_ns=5000)
        self.assertEqual(span.status_code, StatusCode.ERROR)
        self.assertEqual(span.status_message, "Command timed out")
        self.assertEqual(span.end_time_ns, 5000)

    def test_span_finish_does_not_overwrite_if_already_set_and_not_passed(self) -> None:
        span = Span(
            trace_id="t1",
            span_id="s1",
            name="test",
            kind=SpanKind.TOOL,
            start_time_ns=1000,
            end_time_ns=2000,
        )
        span.finish(status=StatusCode.OK)
        self.assertEqual(span.end_time_ns, 2000)

    def test_span_to_dict_full_serialization(self) -> None:
        span = Span(
            trace_id="trace-abc-123",
            span_id="span-xyz-789",
            name="along.agent.run",
            kind=SpanKind.AGENT,
            start_time_ns=1700000000000000000,
            end_time_ns=1700000005000000000,
            parent_span_id="parent-000",
            attributes={
                conventions.ALONG_RUN_ID: "run-uuid-1",
                conventions.ALONG_AGENT_NAME: "antigravity",
                conventions.ALONG_ISSUE_SLUG: "feat--core",
            },
            status_code=StatusCode.OK,
            status_message="Completed successfully",
        )
        span.add_event("checkpoint", {"stage": "init"}, timestamp_ns=1700000001000000000)

        as_dict = span.to_dict()
        expected = {
            "trace_id": "trace-abc-123",
            "span_id": "span-xyz-789",
            "name": "along.agent.run",
            "kind": "AGENT",
            "start_time_ns": 1700000000000000000,
            "end_time_ns": 1700000005000000000,
            "parent_span_id": "parent-000",
            "attributes": {
                "along.run.id": "run-uuid-1",
                "along.agent.name": "antigravity",
                "along.issue.slug": "feat--core",
            },
            "events": [
                {
                    "name": "checkpoint",
                    "timestamp_ns": 1700000001000000000,
                    "attributes": {"stage": "init"},
                }
            ],
            "status_code": 1,
            "status_message": "Completed successfully",
        }
        self.assertEqual(as_dict, expected)

        # Confirm JSON serializability without errors
        encoded = json.dumps(as_dict)
        decoded = json.loads(encoded)
        self.assertEqual(decoded["kind"], "AGENT")
        self.assertEqual(decoded["status_code"], 1)
        self.assertEqual(len(decoded["events"]), 1)


class TestTelemetryConventions(unittest.TestCase):
    def test_openinference_conventions(self) -> None:
        self.assertEqual(conventions.SPAN_KIND, "openinference.span.kind")
        self.assertEqual(conventions.LLM_MODEL_NAME, "llm.model_name")
        self.assertEqual(conventions.INPUT_VALUE, "input.value")
        self.assertEqual(conventions.OUTPUT_VALUE, "output.value")

    def test_otel_genai_conventions(self) -> None:
        self.assertEqual(conventions.GEN_AI_SYSTEM, "gen_ai.system")
        self.assertEqual(conventions.GEN_AI_REQUEST_MODEL, "gen_ai.request.model")
        self.assertEqual(conventions.GEN_AI_USAGE_INPUT_TOKENS, "gen_ai.usage.input_tokens")
        self.assertEqual(conventions.GEN_AI_USAGE_OUTPUT_TOKENS, "gen_ai.usage.output_tokens")

    def test_process_conventions(self) -> None:
        self.assertEqual(conventions.PROCESS_COMMAND_LINE, "process.command_line")
        self.assertEqual(conventions.PROCESS_PID, "process.pid")
        self.assertEqual(conventions.PROCESS_EXIT_CODE, "process.exit.code")

    def test_tool_conventions(self) -> None:
        self.assertEqual(conventions.TOOL_NAME, "tool.name")
        self.assertEqual(conventions.TOOL_PARAMETERS, "tool.parameters")

    def test_along_protocol_conventions(self) -> None:
        self.assertEqual(conventions.ALONG_RUN_ID, "along.run.id")
        self.assertEqual(conventions.ALONG_REPO_ROOT, "along.repo.root")
        self.assertEqual(conventions.ALONG_REPO_NAME, "along.repo.name")
        self.assertEqual(conventions.ALONG_ISSUE_SLUG, "along.issue.slug")
        self.assertEqual(conventions.ALONG_AGENT_NAME, "along.agent.name")
        self.assertEqual(conventions.ALONG_OBSERVABILITY_LEVEL, "along.observability.level")
        self.assertEqual(conventions.ALONG_OBSERVABILITY_SOURCES, "along.observability.sources")
        self.assertEqual(conventions.ALONG_TURN_SEQ, "along.turn.seq")
        self.assertEqual(conventions.ALONG_TURN_TITLE, "along.turn.title")
        self.assertEqual(conventions.ALONG_TURN_PHASE, "along.turn.phase")
        self.assertEqual(conventions.ALONG_TURN_RETRIES, "along.turn.retries")
        self.assertEqual(conventions.ALONG_ARTIFACT_OFFLOADED, "along.artifact.offloaded")
        self.assertEqual(conventions.ALONG_ARTIFACT_REF, "along.artifact.ref")
        self.assertEqual(conventions.ALONG_ARTIFACT_SHA256, "along.artifact.sha256")
        self.assertEqual(conventions.SERVICE_NAME, "service.name")


if __name__ == "__main__":
    unittest.main()
