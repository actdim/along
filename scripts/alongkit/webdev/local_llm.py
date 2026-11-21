#!/usr/bin/env python3
"""alongkit.webdev.local_llm - Lightweight offline/local inference client for WebDev compilation."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_LOCAL_ENDPOINTS: Tuple[str, ...] = (
    "http://127.0.0.1:11434/v1",  # Ollama
    "http://127.0.0.1:8080/v1",   # llama-server / vLLM / LM Studio
    "http://localhost:11434/v1",
    "http://localhost:8080/v1",
)


class LocalInferenceClient:
    """Zero-dependency local inference client discovering local OpenAI-compatible engines."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 3.0,
    ) -> None:
        self.configured_endpoint = endpoint or os.environ.get("ALONG_LOCAL_LLM_ENDPOINT")
        self.model = model or os.environ.get("ALONG_LOCAL_LLM_MODEL") or "default"
        self.timeout = timeout
        self._active_endpoint: Optional[str] = None
        self._probed = False

    def probe_endpoint(self) -> Optional[str]:
        """Probe available local endpoints and return the first responding endpoint."""
        if self._probed:
            return self._active_endpoint

        candidates: List[str] = []
        if self.configured_endpoint:
            candidates.append(self.configured_endpoint)
        else:
            candidates.extend(DEFAULT_LOCAL_ENDPOINTS)

        for candidate in candidates:
            url = candidate.rstrip("/") + "/models"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "along-webdev-local-llm"})
                with urllib.request.urlopen(req, timeout=0.8) as resp:
                    if resp.status == 200:
                        self._active_endpoint = candidate
                        self._probed = True
                        return candidate
            except (urllib.error.URLError, OSError, ValueError):
                continue

        self._probed = True
        self._active_endpoint = None
        return None

    def is_available(self) -> bool:
        """Return True if a local LLM daemon is reachable."""
        return self.probe_endpoint() is not None

    def generate(self, prompt: str, system: Optional[str] = None) -> Optional[str]:
        """Send chat completion request to active local LLM daemon."""
        endpoint = self.probe_endpoint()
        if not endpoint:
            return None

        url = endpoint.rstrip("/") + "/chat/completions"
        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
        }

        try:
            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "along-webdev-local-llm",
                },
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    body = json.loads(resp.read().decode("utf-8"))
                    choices = body.get("choices")
                    if isinstance(choices, list) and len(choices) > 0:
                        msg = choices[0].get("message")
                        if isinstance(msg, dict) and "content" in msg:
                            return str(msg["content"])
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
            return None

        return None
