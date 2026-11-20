#!/usr/bin/env python3
"""alongkit.webdev.capture - CDP console harvesting, network request tracking, and noise filtering."""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

from . import redact


class ConsoleMessage:
    """Captured browser console event."""

    def __init__(self, level: str, text: str, location: str = "", timestamp: Optional[float] = None):
        self.level = level
        self.text = text
        self.location = location
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "text": self.text,
            "location": self.location,
            "timestamp": self.timestamp,
        }


class NetworkRecord:
    """Captured network request/response interaction."""

    def __init__(
        self,
        method: str,
        url: str,
        status: Optional[int] = None,
        headers: Optional[Dict[str, str]] = None,
        failure_text: Optional[str] = None,
        timing_ms: float = 0.0,
    ):
        self.method = method
        self.url = url
        self.status = status
        self.headers = headers or {}
        self.failure_text = failure_text
        self.timing_ms = timing_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "url": self.url,
            "status": self.status,
            "headers": self.headers,
            "failure": self.failure_text,
            "timing_ms": self.timing_ms,
        }


class DiagnosticsHarvester:
    """Hooks into Playwright page events to record console messages and network traffic."""

    def __init__(
        self,
        redactor: Optional[redact.Redactor] = None,
        console_noise: Optional[List[str]] = None,
        network_noise: Optional[List[str]] = None,
    ):
        self.redactor = redactor or redact.Redactor()
        self.console_messages: List[ConsoleMessage] = []
        self.network_records: List[NetworkRecord] = []
        self.console_noise_re = [re.compile(pat) for pat in (console_noise or [])]
        self.network_noise_re = [re.compile(pat) for pat in (network_noise or [])]

    def attach(self, page: Any) -> None:
        """Attach listeners to Playwright page."""
        page.on("console", self._handle_console)
        page.on("pageerror", self._handle_pageerror)
        page.on("response", self._handle_response)
        page.on("requestfailed", self._handle_requestfailed)

    def _handle_console(self, msg: Any) -> None:
        text = self.redactor.redact_text(msg.text)
        loc = f"{msg.location.get('url', '')}:{msg.location.get('lineNumber', '')}" if hasattr(msg, "location") else ""
        self.console_messages.append(ConsoleMessage(level=msg.type, text=text, location=loc))

    def _handle_pageerror(self, err: Any) -> None:
        err_msg = self.redactor.redact_text(str(err))
        self.console_messages.append(ConsoleMessage(level="error", text=f"Uncaught Exception: {err_msg}"))

    def _handle_response(self, resp: Any) -> None:
        try:
            req = resp.request
            headers = self.redactor.redact_headers(dict(resp.headers))
            clean_url = self.redactor.redact_text(resp.url)
            rec = NetworkRecord(
                method=req.method,
                url=clean_url,
                status=resp.status,
                headers=headers,
            )
            self.network_records.append(rec)
        except (AttributeError, KeyError, TypeError, ValueError):
            pass

    def _handle_requestfailed(self, req: Any) -> None:
        try:
            failure = req.failure
            fail_text = failure if isinstance(failure, str) else getattr(failure, "error_text", "Failed")
            clean_url = self.redactor.redact_text(req.url)
            rec = NetworkRecord(
                method=req.method,
                url=clean_url,
                status=None,
                failure_text=fail_text,
            )
            self.network_records.append(rec)
        except (AttributeError, KeyError, TypeError, ValueError):
            pass

    def is_console_noise(self, text: str) -> bool:
        """Return True if console message matches configured noise patterns."""
        return any(pat.search(text) for pat in self.console_noise_re)

    def is_network_noise(self, url: str) -> bool:
        """Return True if network URL matches configured noise patterns."""
        return any(pat.search(url) for pat in self.network_noise_re)

    def filtered_console_errors(self) -> List[ConsoleMessage]:
        """Return console errors and uncaught exceptions that are not filtered by noise."""
        return [
            m for m in self.console_messages
            if m.level == "error" and not self.is_console_noise(m.text)
        ]

    def filtered_failed_requests(self) -> List[NetworkRecord]:
        """Return 4xx/5xx responses and request failures that are not filtered by noise."""
        failed: List[NetworkRecord] = []
        for r in self.network_records:
            if self.is_network_noise(r.url):
                continue
            if r.failure_text:
                failed.append(r)
            elif r.status is not None and r.status >= 400:
                failed.append(r)
        return failed
