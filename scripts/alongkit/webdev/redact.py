#!/usr/bin/env python3
"""alongkit.webdev.redact - Centralized redaction for secrets, auth headers, and sensitive payloads."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

SENSITIVE_HEADERS: Set[str] = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "proxy-authorization",
}

SENSITIVE_KEY_PATTERNS = [
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"auth", re.IGNORECASE),
]


class Redactor:
    """Masks known secret values and sensitive keys in headers and payloads."""

    def __init__(self, secrets: Optional[Dict[str, str]] = None):
        self.secrets: Dict[str, str] = secrets or {}
        # Map secret values to ***KEY*** mask
        self._val_to_mask: Dict[str, str] = {
            v: f"***{k}***" for k, v in self.secrets.items() if v and len(v) >= 3
        }

    def redact_text(self, text: str) -> str:
        """Replace literal secret values with ***KEY***."""
        if not text:
            return ""
        result = text
        for secret_val, mask in self._val_to_mask.items():
            result = result.replace(secret_val, mask)
        return result

    def redact_headers(self, headers: Dict[str, Any]) -> Dict[str, str]:
        """Redact known sensitive headers like Authorization and Cookies."""
        cleaned: Dict[str, str] = {}
        for k, v in headers.items():
            k_lower = k.lower()
            val_str = str(v)
            if k_lower in SENSITIVE_HEADERS:
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = self.redact_text(val_str)
        return cleaned

    def redact_data(self, data: Any) -> Any:
        """Recursively redact dictionaries and lists."""
        if isinstance(data, dict):
            res: Dict[str, Any] = {}
            for k, v in data.items():
                if any(p.search(k) for p in SENSITIVE_KEY_PATTERNS):
                    res[k] = "[REDACTED]"
                else:
                    res[k] = self.redact_data(v)
            return res
        if isinstance(data, list):
            return [self.redact_data(item) for item in data]
        if isinstance(data, str):
            return self.redact_text(data)
        return data
