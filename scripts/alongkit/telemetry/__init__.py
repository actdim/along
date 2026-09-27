#!/usr/bin/env python3
"""
alongkit.telemetry - OpenTelemetry and OpenInference telemetry engine.
"""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

from . import conventions
from .models import ArtifactRef, Span, SpanEvent, SpanKind, StatusCode
from .offloader import ArtifactOffloader
from .otlp import OTLPExporter, build_otlp_payload
from .redactor import Redactor
from .spool import Spooler
from .tracer import Tracer

__all__ = [
    "ArtifactOffloader",
    "ArtifactRef",
    "OTLPExporter",
    "Redactor",
    "Span",
    "SpanEvent",
    "SpanKind",
    "Spooler",
    "StatusCode",
    "Tracer",
    "build_otlp_payload",
    "conventions",
]
