#!/usr/bin/env python3
"""alongkit.runner.claude - Claude Code headless runtime adapter."""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .base import BaseRunner, merge_args


class ClaudeCodeRunner(BaseRunner):
    """Claude Code headless agent runtime adapter."""

    runtime: str = "claude"
    runtime_label: str = "Claude Code"
    default_binary: str = "claude"
    cli_version: str = "2.1.228"
    brief_via_stdin: bool = True

    RUNTIME_ENV_ALLOW: Set[str] = {
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "CLAUDE_CONFIG_DIR",
    }
    RUNTIME_ENV_ALLOW_PREFIXES: Tuple[str, ...] = ("CLAUDE_CODE_",)
    VALUE_FLAGS: Set[str] = {
        "-p", "--print", "--model", "--output-format", "--settings",
        "--permission-mode", "--tools", "--system-prompt", "--mcp-config",
        "--plugin-dir", "--plugin-url", "--fallback-model", "--json-schema",
        "--max-budget-usd", "--effort", "--add-dir", "--agents",
        "--allowed-tools", "--allowedTools", "--disallowed-tools",
        "--disallowedTools", "--session-id", "--setting-sources",
    }

    @classmethod
    def role_args(cls, role: str) -> List[str]:
        """Return runtime-specific default arguments for Claude Code."""
        return ["--dangerously-skip-permissions"]

    def build_command(self, prompt: Optional[str] = None) -> List[str]:
        """Construct command line arguments for Claude Code headless execution."""
        binary = self.resolve_binary()
        cmd = [
            binary,
            "-p",
            "--output-format",
            "json",
            "--no-session-persistence",
        ]
        if self.model:
            cmd.extend(["--model", self.model])
        role = self.role or "implementer"
        r_args = self.role_args(role)
        cmd = merge_args(cmd, r_args, self.VALUE_FLAGS)
        if self.extra_args:
            cmd = merge_args(cmd, self.extra_args, self.VALUE_FLAGS)
        return cmd

    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> Dict[str, Any]:
        """Parse structured JSON emitted by Claude Code --output-format json."""
        clean_stdout = stdout.strip()
        parsed_json: Optional[Dict[str, Any]] = None

        if clean_stdout:
            try:
                data = json.loads(clean_stdout)
                if isinstance(data, dict):
                    parsed_json = data
            except (json.JSONDecodeError, ValueError):
                for line in reversed(clean_stdout.splitlines()):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if isinstance(data, dict):
                            parsed_json = data
                            break
                    except (json.JSONDecodeError, ValueError):
                        continue

        usage: Optional[Dict[str, Any]] = None
        handoff_note: Optional[str] = None
        is_error = False
        result_str = clean_stdout

        if parsed_json:
            is_error = bool(parsed_json.get("is_error"))
            raw_usage = parsed_json.get("usage")
            if isinstance(raw_usage, dict):
                usage = {
                    "input_tokens": raw_usage.get("input_tokens") or 0,
                    "output_tokens": raw_usage.get("output_tokens") or 0,
                }
            if "total_cost_usd" in parsed_json and parsed_json["total_cost_usd"] is not None:
                if usage is None:
                    usage = {"input_tokens": 0, "output_tokens": 0}
                usage["cost_usd"] = parsed_json["total_cost_usd"]

            result_str = str(parsed_json.get("result") or "")
            if parsed_json.get("handoff_note"):
                handoff_note = str(parsed_json["handoff_note"])

        if exit_code == 0 and not is_error:
            outcome = "done"
        else:
            outcome = "fail"

        return {
            "outcome": outcome,
            "usage": usage,
            "changed_files": [],
            "handoff_note": handoff_note,
            "text": result_str,
        }
