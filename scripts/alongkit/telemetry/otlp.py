#!/usr/bin/env python3
"""
alongkit.telemetry.otlp - OpenTelemetry OTLP/HTTP Trace Exporter and serializer.
"""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

import json
from typing import Any, Dict, List, Optional, Sequence, Union
import urllib.error
import urllib.request

from .models import Span, SpanEvent, SpanKind, StatusCode
from .spool import Spooler


def _encode_value(val: Any) -> Dict[str, Any]:
    """
    Encodes a Python primitive into OpenTelemetry AnyValue format.
    """
    if isinstance(val, bool):
        return {"boolValue": val}
    if isinstance(val, int):
        return {"intValue": str(val)}
    if isinstance(val, float):
        return {"doubleValue": float(val)}
    if isinstance(val, str):
        return {"stringValue": str(val)}
    if isinstance(val, (list, tuple)):
        return {"arrayValue": {"values": [_encode_value(x) for x in val]}}
    if isinstance(val, dict):
        return {
            "kvlistValue": {
                "values": [
                    {"key": str(k), "value": _encode_value(v)}
                    for k, v in val.items()
                ]
            }
        }
    return {"stringValue": str(val)}


def _format_span(span: Union[Span, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Formats a single Span or span dictionary into OTel span JSON representation.
    """
    if isinstance(span, Span):
        trace_id = span.trace_id
        span_id = span.span_id
        parent_span_id = span.parent_span_id
        name = span.name
        kind = span.kind
        start_time_ns = span.start_time_ns
        end_time_ns = span.end_time_ns
        attributes = span.attributes
        events = span.events
        status_code = span.status_code
        status_message = span.status_message
    elif isinstance(span, dict):
        trace_id = span.get("trace_id", "")
        span_id = span.get("span_id", "")
        parent_span_id = span.get("parent_span_id")
        name = span.get("name", "")
        kind = span.get("kind", 1)
        start_time_ns = span.get("start_time_ns", 0)
        end_time_ns = span.get("end_time_ns")
        attributes = span.get("attributes", {})
        events = span.get("events", [])
        status_code = span.get("status_code", StatusCode.UNSET)
        status_message = span.get("status_message", "")
    else:
        trace_id = getattr(span, "trace_id", "")
        span_id = getattr(span, "span_id", "")
        parent_span_id = getattr(span, "parent_span_id", None)
        name = getattr(span, "name", "")
        kind = getattr(span, "kind", 1)
        start_time_ns = getattr(span, "start_time_ns", 0)
        end_time_ns = getattr(span, "end_time_ns", None)
        attributes = getattr(span, "attributes", {})
        events = getattr(span, "events", [])
        status_code = getattr(span, "status_code", StatusCode.UNSET)
        status_message = getattr(span, "status_message", "")

    # kind: 3 for LLM, 1 for INTERNAL/AGENT/CHAIN/TOOL
    if isinstance(kind, int):
        kind_num = 3 if kind == 3 else 1
    else:
        kind_str = str(getattr(kind, "value", kind)).upper()
        if kind_str in ("LLM", "CLIENT", "SPAN_KIND_CLIENT"):
            kind_num = 3
        else:
            kind_num = 1

    start_ns = int(start_time_ns) if start_time_ns is not None else 0
    end_ns = int(end_time_ns) if end_time_ns is not None else start_ns

    # attributes
    encoded_attrs: List[Dict[str, Any]] = []
    if isinstance(attributes, dict):
        for k, v in attributes.items():
            encoded_attrs.append({"key": str(k), "value": _encode_value(v)})

    # events
    encoded_events: List[Dict[str, Any]] = []
    for ev in events:
        if isinstance(ev, SpanEvent):
            ev_name = ev.name
            ev_ts = ev.timestamp_ns
            ev_attrs = ev.attributes
        elif isinstance(ev, dict):
            ev_name = ev.get("name", "")
            ev_ts = ev.get("timestamp_ns") or ev.get("timeUnixNano", 0)
            ev_attrs = ev.get("attributes", {})
        else:
            ev_name = getattr(ev, "name", "")
            ev_ts = getattr(ev, "timestamp_ns", 0)
            ev_attrs = getattr(ev, "attributes", {})

        ev_attr_list: List[Dict[str, Any]] = []
        if isinstance(ev_attrs, dict):
            for k, v in ev_attrs.items():
                ev_attr_list.append({"key": str(k), "value": _encode_value(v)})

        encoded_events.append({
            "timeUnixNano": str(ev_ts),
            "name": str(ev_name),
            "attributes": ev_attr_list,
        })

    # status
    if isinstance(status_code, StatusCode):
        code_int = status_code.value
    elif isinstance(status_code, int):
        code_int = status_code
    else:
        try:
            code_int = int(status_code)
        except (ValueError, TypeError):
            code_int = 0

    status_obj: Dict[str, Any] = {"code": code_int}
    if status_message:
        status_obj["message"] = str(status_message)

    formatted: Dict[str, Any] = {
        "traceId": str(trace_id),
        "spanId": str(span_id),
        "name": str(name),
        "kind": kind_num,
        "startTimeUnixNano": str(start_ns),
        "endTimeUnixNano": str(end_ns),
        "attributes": encoded_attrs,
        "events": encoded_events,
        "status": status_obj,
    }
    if parent_span_id:
        formatted["parentSpanId"] = str(parent_span_id)

    return formatted


def build_otlp_payload(
    service_name: str,
    resource_attrs: Dict[str, Any],
    spans: Sequence[Union[Span, Dict[str, Any]]],
) -> Dict[str, Any]:
    """
    Formats spans into OpenTelemetry v1/traces JSON schema payload.
    """
    res_attrs = dict(resource_attrs or {})
    if "service.name" not in res_attrs and service_name:
        res_attrs["service.name"] = service_name

    resource_attr_list = [
        {"key": str(k), "value": _encode_value(v)}
        for k, v in res_attrs.items()
    ]

    scope_spans = [
        {
            "scope": {
                "name": "along.arp",
                "version": "5.0.0",
            },
            "spans": [_format_span(s) for s in spans],
        }
    ]

    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": resource_attr_list,
                },
                "scopeSpans": scope_spans,
            }
        ]
    }


class OTLPExporter:
    """
    OpenTelemetry OTLP/HTTP Trace Exporter with disk spool failover.
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:4318/v1/traces",
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 3.0,
        spooler: Optional[Spooler] = None,
    ) -> None:
        self.endpoint = endpoint
        self.headers = dict(headers or {})
        if "Content-Type" not in self.headers:
            self.headers["Content-Type"] = "application/json"
        self.timeout = float(timeout)
        self.spooler = spooler

    def export(
        self,
        spans: Sequence[Union[Span, Dict[str, Any]]],
        service_name: str = "actdim-along",
        resource_attrs: Optional[Dict[str, Any]] = None,
        spool_on_failure: bool = True,
    ) -> bool:
        """
        Exports a sequence of spans over HTTP POST.
        Spools to WAL on connection, timeout, or HTTP errors.
        """
        if not spans:
            return True

        payload = build_otlp_payload(
            service_name=service_name,
            resource_attrs=resource_attrs or {},
            spans=spans,
        )
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        req = urllib.request.Request(
            url=self.endpoint,
            data=data,
            headers=self.headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                status = getattr(response, "status", 200)
                if 200 <= status <= 299:
                    return True
                if spool_on_failure:
                    self._spool_spans(spans)
                return False
        except (urllib.error.URLError, TimeoutError, OSError):
            if spool_on_failure:
                self._spool_spans(spans)
            return False

    def _spool_spans(self, spans: Sequence[Union[Span, Dict[str, Any]]]) -> None:
        if self.spooler is not None:
            for s in spans:
                try:
                    self.spooler.append_span(s)
                except (OSError, TypeError, ValueError):
                    pass

    def flush_spool(
        self,
        service_name: str = "actdim-along",
        resource_attrs: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Attempts to export all buffered spans from the WAL file.
        Clears the WAL file on success.
        """
        if self.spooler is None:
            return 0
        spooled_spans = self.spooler.read_spool()
        if not spooled_spans:
            return 0

        success = self.export(
            spans=spooled_spans,
            service_name=service_name,
            resource_attrs=resource_attrs,
            spool_on_failure=False,
        )
        if success:
            self.spooler.clear()
            return len(spooled_spans)
        return 0
