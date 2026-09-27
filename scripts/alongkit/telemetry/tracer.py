#!/usr/bin/env python3
"""
alongkit.telemetry.tracer - OpenTelemetry & OpenInference trace lifecycle coordinator.
"""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

import contextlib
import hashlib
import json
import os
import time
from typing import Any, Dict, Iterator, List, Optional, Sequence, Union
import uuid

from . import conventions
from .models import ArtifactRef, Span, SpanKind, StatusCode
from .offloader import ArtifactOffloader
from .otlp import OTLPExporter
from .redactor import Redactor
from .spool import Spooler

_ACTIVE_TRACER: Optional[Tracer] = None


class Tracer:
    """
    OpenTelemetry & OpenInference trace lifecycle coordinator for Agent Run Protocol.
    """

    @classmethod
    def get_active(cls) -> Optional[Tracer]:
        """Returns the currently active Tracer instance, if any."""
        return _ACTIVE_TRACER

    @classmethod
    def set_active(cls, tracer: Optional[Tracer]) -> None:
        """Sets or unsets the globally active Tracer instance."""
        global _ACTIVE_TRACER
        _ACTIVE_TRACER = tracer

    def __init__(
        self,
        repo_root: str,
        run_id: Optional[str] = None,
        issue_slug: str = "adhoc",
        agent_name: str = "antigravity",
        exporter: Optional[OTLPExporter] = None,
        auto_flush: bool = True,
        service_name: str = "actdim-along",
    ) -> None:
        self.repo_root = os.path.abspath(repo_root)
        self.run_id = str(run_id) if run_id is not None else uuid.uuid4().hex

        clean_id = self.run_id.replace("-", "").lower()
        if len(clean_id) == 32 and all(c in "0123456789abcdef" for c in clean_id):
            self.trace_id = clean_id
        else:
            self.trace_id = hashlib.sha256(self.run_id.encode("utf-8")).hexdigest()[:32]

        self.issue_slug = str(issue_slug)
        self.agent_name = str(agent_name)
        self.auto_flush = bool(auto_flush)
        self.service_name = str(service_name)

        self.redactor = Redactor()
        self.offloader = ArtifactOffloader(self.repo_root, self.run_id)
        self.spooler = Spooler(self.repo_root, self.run_id)
        self.exporter = exporter if exporter is not None else OTLPExporter(spooler=self.spooler)

        self._span_stack: List[Span] = []
        self._buffered_spans: List[Span] = []
        self._pending_spans: List[Span] = []
        self.root_span: Optional[Span] = None

    def __enter__(self) -> Tracer:
        if self.root_span is None:
            self.start_run()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            self.end_run(status=StatusCode.ERROR, message=str(exc_val))
        else:
            self.end_run(status=StatusCode.OK)

    @property
    def active_span_id(self) -> Optional[str]:
        if self._span_stack:
            return self._span_stack[-1].span_id
        return None

    @property
    def active_span(self) -> Optional[Span]:
        if self._span_stack:
            return self._span_stack[-1]
        return None

    @property
    def buffered_spans(self) -> List[Span]:
        return list(self._buffered_spans)

    @property
    def pending_spans(self) -> List[Span]:
        return list(self._pending_spans)

    def _new_span_id(self) -> str:
        return uuid.uuid4().hex[:16]

    def start_run(
        self,
        observability_level: str = "complete",
        sources: Optional[List[str]] = None,
    ) -> Span:
        if self.root_span is not None:
            return self.root_span

        start_time_ns = time.time_ns()
        span_id = self._new_span_id()
        repo_name = os.path.basename(self.repo_root) or "actdim-along"

        attributes: Dict[str, Any] = {
            conventions.SPAN_KIND: SpanKind.AGENT.value,
            conventions.ALONG_RUN_ID: self.run_id,
            conventions.ALONG_ISSUE_SLUG: self.issue_slug,
            conventions.ALONG_AGENT_NAME: self.agent_name,
            conventions.ALONG_REPO_ROOT: self.repo_root,
            conventions.ALONG_REPO_NAME: repo_name,
            conventions.ALONG_OBSERVABILITY_LEVEL: str(observability_level),
            conventions.ALONG_OBSERVABILITY_SOURCES: list(sources) if sources is not None else ["cli", "subagent", "tool"],
            conventions.SERVICE_NAME: self.service_name,
        }

        span = Span(
            trace_id=self.trace_id,
            span_id=span_id,
            name="along.agent.run",
            kind=SpanKind.AGENT,
            start_time_ns=start_time_ns,
            parent_span_id=None,
            attributes=attributes,
        )

        self.root_span = span
        self._span_stack.append(span)
        Tracer.set_active(self)
        return span

    def end_run(
        self,
        status: StatusCode = StatusCode.OK,
        message: str = "",
    ) -> None:
        if self.root_span is not None:
            self.root_span.finish(status=status, message=message)
            if self.root_span in self._span_stack:
                self._span_stack.remove(self.root_span)
            spans_to_export = [self.root_span] + self._pending_spans
            self._pending_spans.clear()
            self.exporter.export(spans_to_export, service_name=self.service_name)
        elif self._pending_spans:
            self.flush()

        if Tracer.get_active() is self:
            Tracer.set_active(None)

    @contextlib.contextmanager
    def turn_span(
        self,
        seq: int,
        title: str,
        phase: str = "execution",
    ) -> Iterator[Span]:
        start_time_ns = time.time_ns()
        span_id = self._new_span_id()
        parent_id = self.active_span_id

        attributes: Dict[str, Any] = {
            conventions.SPAN_KIND: SpanKind.CHAIN.value,
            conventions.ALONG_TURN_SEQ: int(seq),
            conventions.ALONG_TURN_TITLE: str(title),
            conventions.ALONG_TURN_PHASE: str(phase),
        }

        span = Span(
            trace_id=self.trace_id,
            span_id=span_id,
            name=f"turn.{seq}:{title}",
            kind=SpanKind.CHAIN,
            start_time_ns=start_time_ns,
            parent_span_id=parent_id,
            attributes=attributes,
        )

        self._span_stack.append(span)
        try:
            yield span
        except Exception as exc:
            span.finish(status=StatusCode.ERROR, message=str(exc))
            raise
        else:
            if span.status_code == StatusCode.UNSET:
                span.finish(status=StatusCode.OK)
            elif span.end_time_ns is None:
                span.finish(status=span.status_code, message=span.status_message)
        finally:
            if self._span_stack and self._span_stack[-1] is span:
                self._span_stack.pop()
            elif span in self._span_stack:
                self._span_stack.remove(span)
            self._buffered_spans.append(span)
            self._pending_spans.append(span)
            if self.auto_flush:
                self.flush()

    @contextlib.contextmanager
    def tool_span(
        self,
        tool_name: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Iterator[Span]:
        start_time_ns = time.time_ns()
        span_id = self._new_span_id()
        parent_id = self.active_span_id

        clean_params = self.redactor.sanitize_dict(parameters or {})
        params_json = json.dumps(clean_params, ensure_ascii=True)

        attributes: Dict[str, Any] = {
            conventions.SPAN_KIND: SpanKind.TOOL.value,
            conventions.TOOL_NAME: str(tool_name),
            conventions.TOOL_PARAMETERS: params_json,
        }

        span = Span(
            trace_id=self.trace_id,
            span_id=span_id,
            name=f"tool.{tool_name}",
            kind=SpanKind.TOOL,
            start_time_ns=start_time_ns,
            parent_span_id=parent_id,
            attributes=attributes,
        )

        self._span_stack.append(span)
        try:
            yield span
        except Exception as exc:
            span.finish(status=StatusCode.ERROR, message=str(exc))
            raise
        else:
            if span.status_code == StatusCode.UNSET:
                span.finish(status=StatusCode.OK)
            elif span.end_time_ns is None:
                span.finish(status=span.status_code, message=span.status_message)
        finally:
            if self._span_stack and self._span_stack[-1] is span:
                self._span_stack.pop()
            elif span in self._span_stack:
                self._span_stack.remove(span)
            self._buffered_spans.append(span)
            self._pending_spans.append(span)
            if self.auto_flush:
                self.flush()

    @contextlib.contextmanager
    def llm_span(
        self,
        model: str,
        system: str = "unknown",
    ) -> Iterator[Span]:
        start_time_ns = time.time_ns()
        span_id = self._new_span_id()
        parent_id = self.active_span_id

        attributes: Dict[str, Any] = {
            conventions.SPAN_KIND: SpanKind.LLM.value,
            conventions.GEN_AI_SYSTEM: str(system),
            conventions.GEN_AI_REQUEST_MODEL: str(model),
            conventions.LLM_MODEL_NAME: str(model),
        }

        span = Span(
            trace_id=self.trace_id,
            span_id=span_id,
            name=f"llm.{model}",
            kind=SpanKind.LLM,
            start_time_ns=start_time_ns,
            parent_span_id=parent_id,
            attributes=attributes,
        )

        self._span_stack.append(span)
        try:
            yield span
        except Exception as exc:
            span.finish(status=StatusCode.ERROR, message=str(exc))
            raise
        else:
            if span.status_code == StatusCode.UNSET:
                span.finish(status=StatusCode.OK)
            elif span.end_time_ns is None:
                span.finish(status=span.status_code, message=span.status_message)
        finally:
            if self._span_stack and self._span_stack[-1] is span:
                self._span_stack.pop()
            elif span in self._span_stack:
                self._span_stack.remove(span)
            self._buffered_spans.append(span)
            self._pending_spans.append(span)
            if self.auto_flush:
                self.flush()

    def record_command_result(
        self,
        span: Span,
        cmd: Union[Sequence[str], str],
        exit_code: int,
        stdout: str,
        stderr: str = "",
        pid: Optional[int] = None,
    ) -> None:
        if isinstance(cmd, (list, tuple)):
            raw_cmd = " ".join(str(c) for c in cmd)
        else:
            raw_cmd = str(cmd)
        clean_cmd = self.redactor.sanitize_text(raw_cmd)
        span.set_attribute(conventions.PROCESS_COMMAND_LINE, clean_cmd)
        span.set_attribute(conventions.PROCESS_EXIT_CODE, int(exit_code))
        if pid is not None:
            span.set_attribute(conventions.PROCESS_PID, int(pid))

        raw_stdout = str(stdout or "")
        raw_stderr = str(stderr or "")
        if raw_stdout and raw_stderr:
            combined = f"{raw_stdout}\n{raw_stderr}"
        else:
            combined = raw_stdout or raw_stderr

        preview_text, artifact_ref = self.offloader.maybe_offload(combined)
        if artifact_ref is not None:
            span.set_attribute(conventions.ALONG_ARTIFACT_OFFLOADED, True)
            span.set_attribute(conventions.ALONG_ARTIFACT_REF, artifact_ref.path)
            span.set_attribute(conventions.ALONG_ARTIFACT_SHA256, artifact_ref.sha256)
            span.set_attribute(conventions.OUTPUT_VALUE, self.redactor.sanitize_text(preview_text))
        else:
            span.set_attribute(conventions.OUTPUT_VALUE, self.redactor.sanitize_text(combined))

        if exit_code != 0 and span.status_code == StatusCode.UNSET:
            span.status_code = StatusCode.ERROR
            span.status_message = f"command failed with exit code {exit_code}"

    def flush(self) -> None:
        if not self._pending_spans:
            return
        spans_to_export = list(self._pending_spans)
        self._pending_spans.clear()
        self.exporter.export(spans_to_export, service_name=self.service_name)
