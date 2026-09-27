#!/usr/bin/env python3
"""
alongkit.telemetry.redactor - Sensitive data redaction for telemetry.
"""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

import re
from typing import Any, Dict, List, Optional, Set, Tuple

# Pre-compiled regular expressions for sensitive token patterns

# Private keys (RSA, EC, OpenSSH, DSA, or unspecified)
RE_PRIVATE_KEY = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----[\s\S]+?-----END (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
)

# Anthropic API keys (must be evaluated before generic sk- OpenAI keys)
RE_ANTHROPIC_KEY = re.compile(
    r"sk-ant-(?:api03-)?[a-zA-Z0-9_\-]{20,}"
)

# OpenAI API keys (excludes sk-ant-)
RE_OPENAI_KEY = re.compile(
    r"sk-(?!ant-)(?:proj-)?[a-zA-Z0-9_\-]{20,}"
)

# GitHub tokens (personal access, oauth, server, user, fine-grained)
RE_GITHUB_TOKEN = re.compile(
    r"(?:gh[pousr]_[a-zA-Z0-9]{20,}|github_pat_[a-zA-Z0-9_]{22,})"
)

# AWS Access Keys (AKIA or ASIA prefix followed by 16 alphanumeric characters)
RE_AWS_KEY = re.compile(
    r"(?:AKIA|ASIA)[0-9A-Z]{16}"
)

# Bearer tokens in headers or connection strings
RE_BEARER_TOKEN = re.compile(
    r"(?i)(bearer\s+)[a-zA-Z0-9_\-.~+/]+=*"
)

# Generic password and secret assignments (e.g. api_key = "...", password: secret)
RE_GENERIC_ASSIGNMENT = re.compile(
    r'(?i)(["\']?(?:api[_-]?key|access[_-]?token|auth[_-]?token|secret[_-]?key|password|client[_-]?secret)["\']?\s*[:=]\s*)'
    r'(?:(["\'])(.*?)\2|(["\']?)([^\s"\',;]+))'
)

# User home directory paths across Windows, macOS, and Linux
RE_HOME_PATH = re.compile(
    r"(?:[a-zA-Z]:[\\/](?:Users|Documents and Settings)[\\/][^\\/]+)|(?:/(?:home|Users)/[^/]+)",
    re.IGNORECASE,
)

# Sensitive dictionary key names
RE_SENSITIVE_KEY = re.compile(
    r"^(?:api[_-]?key|access[_-]?token|auth[_-]?token|secret[_-]?key|password|client[_-]?secret)$",
    re.IGNORECASE,
)


class Redactor:
    """
    Sanitizes sensitive tokens, API keys, credentials, and user home directory paths.
    """

    def _mask_generic_assignment(self, match: re.Match) -> str:
        prefix = match.group(1)
        quote = match.group(2)
        if quote:
            val = match.group(3)
            if val.startswith("[REDACTED") or val in ("sk-[REDACTED]", "sk-ant-[REDACTED]"):
                return match.group(0)
            return f"{prefix}{quote}[REDACTED]{quote}"
        val = match.group(5) or ""
        if val.startswith("[REDACTED") or val in ("sk-[REDACTED]", "sk-ant-[REDACTED]"):
            return match.group(0)
        quote_prefix = match.group(4) or ""
        return f"{prefix}{quote_prefix}[REDACTED]"

    def sanitize_text(self, text: str) -> str:
        """
        Sanitizes text by replacing secrets and sensitive patterns with redaction placeholders.
        """
        if not isinstance(text, str):
            if text is None:
                return ""
            text = str(text)
        if not text:
            return ""

        # 1. Private keys
        text = RE_PRIVATE_KEY.sub("[REDACTED_PRIVATE_KEY]", text)

        # 2. Anthropic API keys (must precede OpenAI key pattern)
        text = RE_ANTHROPIC_KEY.sub("sk-ant-[REDACTED]", text)

        # 3. OpenAI API keys
        text = RE_OPENAI_KEY.sub("sk-[REDACTED]", text)

        # 4. GitHub tokens
        text = RE_GITHUB_TOKEN.sub("[REDACTED_GITHUB_TOKEN]", text)

        # 5. AWS Access Keys
        text = RE_AWS_KEY.sub("[REDACTED_AWS_KEY]", text)

        # 6. Bearer tokens
        text = RE_BEARER_TOKEN.sub(r"\g<1>[REDACTED]", text)

        # 7. Generic password and secret assignments
        text = RE_GENERIC_ASSIGNMENT.sub(self._mask_generic_assignment, text)

        # 8. User home directory paths
        text = RE_HOME_PATH.sub("~", text)

        return text

    def sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively sanitizes dictionary keys and values.
        """
        if not isinstance(data, dict):
            return data
        result: Dict[str, Any] = {}
        for k, v in data.items():
            key_str = self.sanitize_text(str(k)) if isinstance(k, str) else k
            if isinstance(k, str) and RE_SENSITIVE_KEY.match(k.strip()):
                if isinstance(v, str):
                    if v.startswith("[REDACTED") or v in ("sk-[REDACTED]", "sk-ant-[REDACTED]"):
                        result[key_str] = v
                    else:
                        result[key_str] = "[REDACTED]"
                elif isinstance(v, dict):
                    result[key_str] = self.sanitize_dict(v)
                elif isinstance(v, list):
                    result[key_str] = [self.sanitize_value(item) for item in v]
                else:
                    result[key_str] = "[REDACTED]"
            else:
                result[key_str] = self.sanitize_value(v)
        return result

    def sanitize_value(self, val: Any) -> Any:
        """
        Sanitizes an arbitrary value (string, dict, list, tuple, set, or primitive).
        """
        if isinstance(val, str):
            return self.sanitize_text(val)
        if isinstance(val, dict):
            return self.sanitize_dict(val)
        if isinstance(val, list):
            return [self.sanitize_value(item) for item in val]
        if isinstance(val, tuple):
            return tuple(self.sanitize_value(item) for item in val)
        if isinstance(val, set):
            return {self.sanitize_value(item) for item in val}
        return val
