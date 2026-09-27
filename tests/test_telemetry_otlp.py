#!/usr/bin/env python3
"""
tests/test_telemetry_otlp.py - Comprehensive hermetic tests for OTLP exporter and spooler.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit.telemetry.models import Span, SpanEvent, SpanKind, StatusCode
from alongkit.telemetry.otlp import OTLPExporter, _encode_value, build_otlp_payload
from alongkit.telemetry.spool import Spooler


class TestEncodeValue(unittest.TestCase):
    def test_encode_bool(self) -> None:
        self.assertEqual(_encode_value(True), {"boolValue": True})
        self.assertEqual(_encode_value(False), {"boolValue": False})

    def test_encode_int(self) -> None:
        self.assertEqual(_encode_value(42), {"intValue": "42"})
        self.assertEqual(_encode_value(0), {"intValue": "0"})
        self.assertEqual(_encode_value(-100), {"intValue": "-100"})

    def test_encode_float(self) -> None:
        self.assertEqual(_encode_value(3.14), {"doubleValue": 3.14})
        self.assertEqual(_encode_value(0.0), {"doubleValue": 0.0})

    def test_encode_str(self) -> None:
        self.assertEqual(_encode_value("hello"), {"stringValue": "hello"})
        self.assertEqual(_encode_value(""), {"stringValue": ""})

    def test_encode_list_and_tuple(self) -> None:
        raw_list = [1, "test", True]
        expected_list = {
            "arrayValue": {
                "values": [
                    {"intValue": "1"},
                    {"stringValue": "test"},
                    {"boolValue": True},
                ]
            }
        }
        self.assertEqual(_encode_value(raw_list), expected_list)

        raw_tuple = (42, 3.14)
        expected_tuple = {
            "arrayValue": {
                "values": [
                    {"intValue": "42"},
                    {"doubleValue": 3.14},
                ]
            }
        }
        self.assertEqual(_encode_value(raw_tuple), expected_tuple)

    def test_encode_dict(self) -> None:
        raw_dict = {"host": "localhost", "port": 8080}
        encoded = _encode_value(raw_dict)
        self.assertIn("kvlistValue", encoded)
        self.assertIn("values", encoded["kvlistValue"])
        values = encoded["kvlistValue"]["values"]
        self.assertEqual(len(values), 2)
        kv_map = {item["key"]: item["value"] for item in values}
        self.assertEqual(kv_map["host"], {"stringValue": "localhost"})
        self.assertEqual(kv_map["port"], {"intValue": "8080"})

    def test_encode_nested_structures(self) -> None:
        nested = {
            "tags": ["alpha", "beta"],
            "meta": {"active": True, "count": 10},
        }
        encoded = _encode_value(nested)
        values = encoded["kvlistValue"]["values"]
        kv_map = {item["key"]: item["value"] for item in values}
        self.assertEqual(
            kv_map["tags"],
            {
                "arrayValue": {
                    "values": [
                        {"stringValue": "alpha"},
                        {"stringValue": "beta"},
                    ]
                }
            },
        )
        self.assertEqual(
            kv_map["meta"],
            {
                "kvlistValue": {
                    "values": [
                        {"key": "active", "value": {"boolValue": True}},
                        {"key": "count", "value": {"intValue": "10"}},
                    ]
                }
            },
        )

    def test_encode_default_fallback(self) -> None:
        class CustomObj:
            def __str__(self) -> str:
                return "custom_str"

        encoded = _encode_value(CustomObj())
        self.assertEqual(encoded, {"stringValue": "custom_str"})


class TestBuildOtlpPayload(unittest.TestCase):
    def setUp(self) -> None:
        self.span = Span(
            trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
            span_id="00f067aa0ba902b7",
            name="arp.workflow.step",
            kind=SpanKind.AGENT,
            start_time_ns=1727270000000000000,
            end_time_ns=1727270001000000000,
            parent_span_id="5fb397be34d23b0f",
            attributes={"step.name": "build", "step.retry_count": 0},
            status_code=StatusCode.OK,
            status_message="step executed successfully",
        )
        self.span.add_event(
            name="step.started",
            timestamp_ns=1727270000100000000,
            attributes={"detail": "compiling"},
        )

    def test_payload_envelope_structure(self) -> None:
        payload = build_otlp_payload(
            service_name="test-service",
            resource_attrs={"env": "test"},
            spans=[self.span],
        )
        self.assertIn("resourceSpans", payload)
        self.assertEqual(len(payload["resourceSpans"]), 1)
        r_span = payload["resourceSpans"][0]
        self.assertIn("resource", r_span)
        self.assertIn("scopeSpans", r_span)

        # Check resource attributes
        r_attrs = r_span["resource"]["attributes"]
        r_map = {attr["key"]: attr["value"] for attr in r_attrs}
        self.assertEqual(r_map["service.name"], {"stringValue": "test-service"})
        self.assertEqual(r_map["env"], {"stringValue": "test"})

        # Check scope
        s_spans = r_span["scopeSpans"]
        self.assertEqual(len(s_spans), 1)
        scope = s_spans[0]["scope"]
        self.assertEqual(scope["name"], "along.arp")
        self.assertEqual(scope["version"], "5.0.0")

    def test_span_fields_mapping(self) -> None:
        payload = build_otlp_payload(
            service_name="test-service",
            resource_attrs={},
            spans=[self.span],
        )
        spans_list = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
        self.assertEqual(len(spans_list), 1)
        sp = spans_list[0]

        self.assertEqual(sp["traceId"], "4bf92f3577b34da6a3ce929d0e0e4736")
        self.assertEqual(sp["spanId"], "00f067aa0ba902b7")
        self.assertEqual(sp["parentSpanId"], "5fb397be34d23b0f")
        self.assertEqual(sp["name"], "arp.workflow.step")
        self.assertEqual(sp["kind"], 1)  # AGENT is INTERNAL (1)
        self.assertEqual(sp["startTimeUnixNano"], "1727270000000000000")
        self.assertEqual(sp["endTimeUnixNano"], "1727270001000000000")
        self.assertEqual(sp["status"], {"code": 1, "message": "step executed successfully"})

        # Check attributes
        attr_map = {a["key"]: a["value"] for a in sp["attributes"]}
        self.assertEqual(attr_map["step.name"], {"stringValue": "build"})
        self.assertEqual(attr_map["step.retry_count"], {"intValue": "0"})

        # Check events
        self.assertEqual(len(sp["events"]), 1)
        ev = sp["events"][0]
        self.assertEqual(ev["name"], "step.started")
        self.assertEqual(ev["timeUnixNano"], "1727270000100000000")
        ev_attr_map = {a["key"]: a["value"] for a in ev["attributes"]}
        self.assertEqual(ev_attr_map["detail"], {"stringValue": "compiling"})

    def test_span_without_parent_span_id(self) -> None:
        root_span = Span(
            trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
            span_id="00f067aa0ba902b7",
            name="root",
            kind=SpanKind.AGENT,
            start_time_ns=1727270000000000000,
        )
        payload = build_otlp_payload("test-service", {}, [root_span])
        sp = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        self.assertNotIn("parentSpanId", sp)

    def test_span_kind_llm_mapping(self) -> None:
        llm_span = Span(
            trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
            span_id="00f067aa0ba902b7",
            name="llm.call",
            kind=SpanKind.LLM,
            start_time_ns=1727270000000000000,
        )
        payload = build_otlp_payload("test-service", {}, [llm_span])
        sp = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        self.assertEqual(sp["kind"], 3)

    def test_span_kind_internal_mappings(self) -> None:
        for kind in (SpanKind.AGENT, SpanKind.CHAIN, SpanKind.TOOL):
            with self.subTest(kind=kind):
                span = Span(
                    trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
                    span_id="00f067aa0ba902b7",
                    name="op",
                    kind=kind,
                    start_time_ns=1727270000000000000,
                )
                payload = build_otlp_payload("test-service", {}, [span])
                sp = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
                self.assertEqual(sp["kind"], 1)

    def test_build_payload_with_dict_spans(self) -> None:
        dict_span = {
            "trace_id": "trace-dict-1",
            "span_id": "span-dict-1",
            "name": "from_spool",
            "kind": "LLM",
            "start_time_ns": 100,
            "end_time_ns": 200,
            "attributes": {"model": "gpt-4"},
            "events": [{"name": "stream.first_chunk", "timestamp_ns": 150}],
            "status_code": 1,
            "status_message": "ok",
        }
        payload = build_otlp_payload("test-service", {}, [dict_span])
        sp = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        self.assertEqual(sp["traceId"], "trace-dict-1")
        self.assertEqual(sp["spanId"], "span-dict-1")
        self.assertEqual(sp["kind"], 3)
        self.assertEqual(sp["startTimeUnixNano"], "100")
        self.assertEqual(sp["endTimeUnixNano"], "200")
        self.assertEqual(sp["attributes"][0]["key"], "model")
        self.assertEqual(sp["attributes"][0]["value"], {"stringValue": "gpt-4"})
        self.assertEqual(sp["events"][0]["name"], "stream.first_chunk")

    def test_empty_spans_list(self) -> None:
        payload = build_otlp_payload("test-service", {}, [])
        self.assertEqual(payload["resourceSpans"][0]["scopeSpans"][0]["spans"], [])


class TestSpooler(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.repo_root = self.tmp_dir.name
        self.run_id = "run-test-1234"
        self.spooler = Spooler(self.repo_root, self.run_id)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_wal_path_location(self) -> None:
        expected_path = os.path.join(
            os.path.abspath(self.repo_root),
            ".along",
            "telemetry",
            "spool",
            f"{self.run_id}.wal",
        )
        self.assertEqual(self.spooler.wal_path, expected_path)

    def test_has_spool_initially_false(self) -> None:
        self.assertFalse(self.spooler.has_spool())
        self.assertEqual(self.spooler.read_spool(), [])

    def test_append_span_and_has_spool(self) -> None:
        span = Span(
            trace_id="t1",
            span_id="s1",
            name="span1",
            kind=SpanKind.TOOL,
            start_time_ns=1000,
        )
        self.spooler.append_span(span)
        self.assertTrue(self.spooler.has_spool())
        self.assertTrue(os.path.isfile(self.spooler.wal_path))

    def test_read_spool_returns_parsed_dicts(self) -> None:
        span1 = Span(
            trace_id="t1",
            span_id="s1",
            name="span1",
            kind=SpanKind.TOOL,
            start_time_ns=1000,
            attributes={"step": 1},
        )
        span2 = Span(
            trace_id="t1",
            span_id="s2",
            name="span2",
            kind=SpanKind.AGENT,
            start_time_ns=2000,
            attributes={"step": 2},
        )
        self.spooler.append_span(span1)
        self.spooler.append_span(span2)

        spooled = self.spooler.read_spool()
        self.assertEqual(len(spooled), 2)
        self.assertEqual(spooled[0]["span_id"], "s1")
        self.assertEqual(spooled[0]["attributes"], {"step": 1})
        self.assertEqual(spooled[1]["span_id"], "s2")
        self.assertEqual(spooled[1]["attributes"], {"step": 2})

    def test_append_raw_dict(self) -> None:
        raw_dict = {"trace_id": "td", "span_id": "sd", "name": "dict_span"}
        self.spooler.append_span(raw_dict)
        self.assertTrue(self.spooler.has_spool())
        spooled = self.spooler.read_spool()
        self.assertEqual(len(spooled), 1)
        self.assertEqual(spooled[0], raw_dict)

    def test_clear_removes_wal_file(self) -> None:
        span = Span(
            trace_id="t1",
            span_id="s1",
            name="span1",
            kind=SpanKind.TOOL,
            start_time_ns=1000,
        )
        self.spooler.append_span(span)
        self.assertTrue(self.spooler.has_spool())

        self.spooler.clear()
        self.assertFalse(self.spooler.has_spool())
        self.assertFalse(os.path.isfile(self.spooler.wal_path))
        self.assertEqual(self.spooler.read_spool(), [])

        # Clearing non-existent file is safe (idempotent)
        self.spooler.clear()
        self.assertFalse(self.spooler.has_spool())


class TestOTLPExporter(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.repo_root = self.tmp_dir.name
        self.run_id = "run-otlp-test"
        self.spooler = Spooler(self.repo_root, self.run_id)
        self.exporter = OTLPExporter(
            endpoint="http://localhost:4318/v1/traces",
            headers={"X-Test": "1"},
            timeout=2.0,
            spooler=self.spooler,
        )
        self.span = Span(
            trace_id="t-100",
            span_id="s-200",
            name="unit.test",
            kind=SpanKind.AGENT,
            start_time_ns=1000000,
        )

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_export_empty_spans_returns_true(self) -> None:
        result = self.exporter.export([])
        self.assertTrue(result)
        self.assertFalse(self.spooler.has_spool())

    @patch("urllib.request.urlopen")
    def test_successful_export_200(self, mock_urlopen: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = self.exporter.export([self.span])
        self.assertTrue(result)
        self.assertFalse(self.spooler.has_spool())

        self.assertTrue(mock_urlopen.called)
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "http://localhost:4318/v1/traces")
        self.assertEqual(req.headers.get("Content-type"), "application/json")
        self.assertEqual(req.headers.get("X-test"), "1")

        # Verify sent payload parses as JSON
        data = json.loads(req.data.decode("utf-8"))
        self.assertIn("resourceSpans", data)

    @patch("urllib.request.urlopen")
    def test_successful_export_201_and_204(self, mock_urlopen: MagicMock) -> None:
        for status in (201, 204):
            with self.subTest(status=status):
                mock_response = MagicMock()
                mock_response.status = status
                mock_urlopen.return_value.__enter__.return_value = mock_response
                result = self.exporter.export([self.span])
                self.assertTrue(result)

    @patch("urllib.request.urlopen")
    def test_export_http_error_spools_to_wal(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://localhost:4318/v1/traces",
            code=500,
            msg="Internal Server Error",
            hdrs=MagicMock(),
            fp=None,
        )

        result = self.exporter.export([self.span])
        self.assertFalse(result)
        self.assertTrue(self.spooler.has_spool())

        spooled = self.spooler.read_spool()
        self.assertEqual(len(spooled), 1)
        self.assertEqual(spooled[0]["span_id"], "s-200")

    @patch("urllib.request.urlopen")
    def test_export_url_error_spools_to_wal(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        result = self.exporter.export([self.span])
        self.assertFalse(result)
        self.assertTrue(self.spooler.has_spool())

        spooled = self.spooler.read_spool()
        self.assertEqual(len(spooled), 1)
        self.assertEqual(spooled[0]["span_id"], "s-200")

    @patch("urllib.request.urlopen")
    def test_export_timeout_error_spools_to_wal(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = TimeoutError("Request timed out")

        result = self.exporter.export([self.span])
        self.assertFalse(result)
        self.assertTrue(self.spooler.has_spool())

    @patch("urllib.request.urlopen")
    def test_export_os_error_spools_to_wal(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = OSError("Network unreachable")

        result = self.exporter.export([self.span])
        self.assertFalse(result)
        self.assertTrue(self.spooler.has_spool())

    @patch("urllib.request.urlopen")
    def test_export_failure_without_spooler(self, mock_urlopen: MagicMock) -> None:
        exporter_no_spool = OTLPExporter(spooler=None)
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        result = exporter_no_spool.export([self.span])
        self.assertFalse(result)

    def test_flush_spool_no_spooler(self) -> None:
        exporter_no_spool = OTLPExporter(spooler=None)
        count = exporter_no_spool.flush_spool()
        self.assertEqual(count, 0)

    def test_flush_spool_empty_wal(self) -> None:
        count = self.exporter.flush_spool()
        self.assertEqual(count, 0)

    @patch("urllib.request.urlopen")
    def test_flush_spool_success_clears_wal(self, mock_urlopen: MagicMock) -> None:
        # Pre-seed spool with 2 spans
        span1 = Span(trace_id="t1", span_id="s1", name="span1", kind=SpanKind.AGENT, start_time_ns=100)
        span2 = Span(trace_id="t1", span_id="s2", name="span2", kind=SpanKind.TOOL, start_time_ns=200)
        self.spooler.append_span(span1)
        self.spooler.append_span(span2)
        self.assertEqual(len(self.spooler.read_spool()), 2)

        # Mock successful flush
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        flushed = self.exporter.flush_spool()
        self.assertEqual(flushed, 2)
        self.assertFalse(self.spooler.has_spool())
        self.assertEqual(self.spooler.read_spool(), [])

    @patch("urllib.request.urlopen")
    def test_flush_spool_failure_preserves_wal_without_duplication(self, mock_urlopen: MagicMock) -> None:
        # Pre-seed spool with 2 spans
        span1 = Span(trace_id="t1", span_id="s1", name="span1", kind=SpanKind.AGENT, start_time_ns=100)
        span2 = Span(trace_id="t1", span_id="s2", name="span2", kind=SpanKind.TOOL, start_time_ns=200)
        self.spooler.append_span(span1)
        self.spooler.append_span(span2)

        # Mock network failure on flush
        mock_urlopen.side_effect = urllib.error.URLError("Still offline")

        flushed = self.exporter.flush_spool()
        self.assertEqual(flushed, 0)
        # WAL must remain intact with exactly 2 items, not duplicated
        self.assertTrue(self.spooler.has_spool())
        self.assertEqual(len(self.spooler.read_spool()), 2)


if __name__ == "__main__":
    unittest.main()
