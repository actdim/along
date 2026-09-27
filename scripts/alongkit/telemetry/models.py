#!/usr/bin/env python3
"""
alongkit.telemetry.models - Telemetry data models for the Agent Run Protocol.
"""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Dict, List, Optional


class SpanKind(str, Enum):
    AGENT = "AGENT"
    CHAIN = "CHAIN"
    TOOL = "TOOL"
    LLM = "LLM"


class StatusCode(int, Enum):
    UNSET = 0
    OK = 1
    ERROR = 2


@dataclass
class ArtifactRef:
    artifact_id: str
    path: str
    sha256: str
    size_bytes: int
    line_count: int
    mime_type: str = "text/plain"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "line_count": self.line_count,
            "mime_type": self.mime_type,
        }


@dataclass
class SpanEvent:
    name: str
    timestamp_ns: int
    attributes: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.attributes is None:
            self.attributes = {}
        elif not isinstance(self.attributes, dict):
            self.attributes = dict(self.attributes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "timestamp_ns": self.timestamp_ns,
            "attributes": dict(self.attributes),
        }


@dataclass
class Span:
    trace_id: str
    span_id: str
    name: str
    kind: SpanKind
    start_time_ns: int
    end_time_ns: Optional[int] = None
    parent_span_id: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[SpanEvent] = field(default_factory=list)
    status_code: StatusCode = StatusCode.UNSET
    status_message: str = ""

    def __post_init__(self) -> None:
        if self.attributes is None:
            self.attributes = {}
        elif not isinstance(self.attributes, dict):
            self.attributes = dict(self.attributes)
        if self.events is None:
            self.events = []
        elif not isinstance(self.events, list):
            self.events = list(self.events)
        if isinstance(self.kind, str) and not isinstance(self.kind, SpanKind):
            try:
                self.kind = SpanKind(self.kind)
            except ValueError:
                pass
        if isinstance(self.status_code, int) and not isinstance(self.status_code, StatusCode):
            try:
                self.status_code = StatusCode(self.status_code)
            except ValueError:
                pass

    def finish(
        self,
        status: StatusCode = StatusCode.OK,
        message: str = "",
        end_time_ns: Optional[int] = None,
    ) -> None:
        if isinstance(status, StatusCode):
            self.status_code = status
        else:
            try:
                self.status_code = StatusCode(status)
            except (ValueError, TypeError):
                self.status_code = status
        self.status_message = message
        if end_time_ns is not None:
            self.end_time_ns = end_time_ns
        elif self.end_time_ns is None:
            self.end_time_ns = time.time_ns()

    def add_event(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        timestamp_ns: Optional[int] = None,
    ) -> SpanEvent:
        if timestamp_ns is None:
            timestamp_ns = time.time_ns()
        event = SpanEvent(
            name=name,
            timestamp_ns=timestamp_ns,
            attributes=dict(attributes or {}),
        )
        self.events.append(event)
        return event

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def to_dict(self) -> Dict[str, Any]:
        kind_value = self.kind.value if hasattr(self.kind, "value") else str(self.kind)
        code_value = (
            self.status_code.value
            if hasattr(self.status_code, "value")
            else int(self.status_code)
        )
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "name": self.name,
            "kind": kind_value,
            "start_time_ns": self.start_time_ns,
            "end_time_ns": self.end_time_ns,
            "parent_span_id": self.parent_span_id,
            "attributes": dict(self.attributes),
            "events": [event.to_dict() for event in self.events],
            "status_code": code_value,
            "status_message": self.status_message,
        }
