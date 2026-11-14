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

import base64
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Union
import urllib.error
import urllib.parse
import urllib.request

from .models import Span, SpanEvent, SpanKind, StatusCode
from .spool import Spooler


def parse_otlp_headers(raw: Union[str, Dict[str, str], None]) -> Dict[str, str]:
    """
    Parses OpenTelemetry header specifications into a dictionary.
    Supports dictionary input or comma-separated key=value strings (URL-encoded or raw).
    """
    if not raw:
        return {}
    if isinstance(raw, dict):
        return {str(k).strip(): str(v).strip() for k, v in raw.items()}
    headers: Dict[str, str] = {}
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    for part in parts:
        if "=" in part:
            k, v = part.split("=", 1)
            k = urllib.parse.unquote(k).strip()
            v = urllib.parse.unquote(v).strip()
            if k:
                headers[k] = v
    return headers


def build_basic_auth_header(user: str, password: str) -> str:
    """
    Builds an HTTP Basic Authentication header value from username and password.
    """
    pair = f"{user}:{password}".encode("utf-8")
    return "Basic " + base64.b64encode(pair).decode("ascii")


def _read_repo_telemetry_section(repo_root: str) -> Optional[Dict[str, Any]]:
    """
    Scans repository configuration files for an optional telemetry or openobserve section.
    """
    candidates = [
        os.path.join(repo_root, ".along", "config.yaml"),
        os.path.join(repo_root, ".along", "config.json"),
        os.path.join(repo_root, "along.yaml"),
        os.path.join(repo_root, "along.json"),
    ]
    for cpath in candidates:
        if not os.path.isfile(cpath):
            continue
        try:
            with open(cpath, "r", encoding="utf-8") as f:
                content = f.read()
            data: Optional[Dict[str, Any]] = None
            if cpath.endswith((".yaml", ".yml")):
                try:
                    from .. import bootstrap
                    ruamel = bootstrap.require("ruamel.yaml")
                    yaml = ruamel.YAML(typ="safe")
                    data = yaml.load(content)
                except (ValueError, OSError, KeyError, TypeError, AttributeError):
                    continue
            else:
                data = json.loads(content)
            if isinstance(data, dict):
                telemetry = data.get("telemetry")
                if isinstance(telemetry, dict):
                    return dict(telemetry)
        except (ValueError, OSError, KeyError, TypeError):
            continue
    return None


def resolve_telemetry_config(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """
    Resolves OTLP and OpenObserve telemetry configuration from environment variables and repository config.
    Priority:
    1. Environment variables (OTEL_EXPORTER_OTLP_*, ALONG_OPENOBSERVE_*)
    2. Repository configuration (along.yaml, .along/config.yaml)
    3. Defaults (http://localhost:4318/v1/traces, actdim-along)
    """
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    raw_headers = os.environ.get("OTEL_EXPORTER_OTLP_HEADERS")
    service_name = os.environ.get("OTEL_SERVICE_NAME")
    headers = parse_otlp_headers(raw_headers)
    timeout: Optional[float] = None

    # Check for direct OpenObserve environment variables
    oo_endpoint = os.environ.get("ALONG_OPENOBSERVE_ENDPOINT")
    if oo_endpoint and not endpoint:
        endpoint = oo_endpoint
    oo_user = os.environ.get("ALONG_OPENOBSERVE_USER")
    oo_pass = os.environ.get("ALONG_OPENOBSERVE_PASSWORD")
    if oo_user is not None and oo_pass is not None and "Authorization" not in headers:
        headers["Authorization"] = build_basic_auth_header(oo_user, oo_pass)
    oo_auth = os.environ.get("ALONG_OPENOBSERVE_AUTH") or os.environ.get("ALONG_OPENOBSERVE_TOKEN")
    if oo_auth and "Authorization" not in headers:
        headers["Authorization"] = oo_auth if oo_auth.startswith("Basic ") else f"Basic {oo_auth}"

    # Fallback to repo config
    root = repo_root
    if not root:
        try:
            from .. import repo
            root = repo.find_repo_root()
        except (ValueError, OSError):
            root = None

    if root and os.path.isdir(root):
        cfg = _read_repo_telemetry_section(root)
        if cfg:
            if not endpoint:
                endpoint = cfg.get("endpoint") or cfg.get("traces_endpoint")
            if not service_name:
                service_name = cfg.get("service_name")
            if timeout is None and "timeout" in cfg:
                try:
                    timeout = float(cfg["timeout"])
                except (ValueError, TypeError):
                    pass
            cfg_headers = cfg.get("headers")
            if isinstance(cfg_headers, dict):
                for k, v in cfg_headers.items():
                    if k not in headers:
                        headers[k] = str(v)
            elif isinstance(cfg_headers, str):
                for k, v in parse_otlp_headers(cfg_headers).items():
                    if k not in headers:
                        headers[k] = v

            oo_cfg = cfg.get("openobserve")
            if isinstance(oo_cfg, dict):
                if not endpoint:
                    oo_ep = oo_cfg.get("endpoint")
                    if oo_ep:
                        endpoint = str(oo_ep)
                if "Authorization" not in headers:
                    u = oo_cfg.get("user") or oo_cfg.get("username")
                    p = oo_cfg.get("password")
                    tok = oo_cfg.get("token") or oo_cfg.get("auth")
                    if u and p:
                        headers["Authorization"] = build_basic_auth_header(str(u), str(p))
                    elif tok:
                        tok_str = str(tok)
                        headers["Authorization"] = tok_str if tok_str.startswith("Basic ") else f"Basic {tok_str}"
                org = oo_cfg.get("organization") or oo_cfg.get("org")
                if org and "openobserve-organization" not in headers:
                    headers["openobserve-organization"] = str(org)
                stream = oo_cfg.get("stream")
                if stream and "openobserve-stream" not in headers:
                    headers["openobserve-stream"] = str(stream)

    final_endpoint = str(endpoint).strip() if endpoint else "http://localhost:4318/v1/traces"
    final_service_name = str(service_name).strip() if service_name else "actdim-along"
    final_timeout = float(timeout) if timeout is not None else 3.0

    return {
        "endpoint": final_endpoint,
        "headers": headers,
        "service_name": final_service_name,
        "timeout": final_timeout,
    }


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
        endpoint: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        spooler: Optional[Spooler] = None,
        repo_root: Optional[str] = None,
    ) -> None:
        resolved = resolve_telemetry_config(repo_root=repo_root) if (endpoint is None or headers is None) else None
        self.endpoint = endpoint if endpoint is not None else (resolved["endpoint"] if resolved else "http://localhost:4318/v1/traces")
        merged_headers = dict(resolved["headers"]) if (headers is None and resolved) else dict(headers or {})
        if headers is not None and resolved:
            for k, v in resolved["headers"].items():
                if k not in merged_headers:
                    merged_headers[k] = v
        self.headers = merged_headers
        if "Content-Type" not in self.headers:
            self.headers["Content-Type"] = "application/json"
        self.timeout = float(timeout) if timeout is not None else (resolved["timeout"] if resolved else 3.0)
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
