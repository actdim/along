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
from typing import Any, Dict, List, Optional

from .base import BaseRunner


class ClaudeCodeRunner(BaseRunner):
    """Claude Code headless agent runtime adapter."""

    runtime: str = "claude"
    runtime_label: str = "Claude Code"
    default_binary: str = "claude"

    def build_command(self, prompt: str) -> List[str]:
        """Construct command line arguments for Claude Code headless execution."""
        binary = self.resolve_binary()
        cmd = [
            binary,
            "-p",
            prompt,
            "--dangerously-skip-permissions",
            "--output-format",
            "json",
        ]
        if self.model:
            cmd.extend(["--model", self.model])
        if self.extra_args:
            cmd.extend(self.extra_args)
        return cmd

    def build_env(self) -> Dict[str, str]:
        """Construct child environment with optional model override."""
        env = super().build_env()
        if self.model:
            env["ANTHROPIC_MODEL"] = self.model
        return env

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
                # Search for JSON object substring if preface logs were printed
                m = re.search(r"(\{.*\})", clean_stdout, re.DOTALL)
                if m:
                    try:
                        data = json.loads(m.group(1))
                        if isinstance(data, dict):
                            parsed_json = data
                    except (json.JSONDecodeError, ValueError):
                        pass

        changed_files: List[str] = []
        usage: Optional[Dict[str, Any]] = None
        handoff_note: Optional[str] = None
        has_question = False

        if parsed_json:
            # Extract usage metrics
            raw_usage = parsed_json.get("usage") or parsed_json.get("tokens")
            if isinstance(raw_usage, dict):
                usage = {
                    "input_tokens": raw_usage.get("input_tokens") or raw_usage.get("input") or 0,
                    "output_tokens": raw_usage.get("output_tokens") or raw_usage.get("output") or 0,
                }
            if "cost" in parsed_json:
                if usage is None:
                    usage = {}
                usage["cost"] = parsed_json["cost"]

            # Extract changed files from tool calls
            raw_tools = parsed_json.get("tool_calls") or parsed_json.get("tools") or []
            if isinstance(raw_tools, list):
                for tc in raw_tools:
                    if not isinstance(tc, dict):
                        continue
                    name = str(tc.get("name") or "").lower()
                    params = tc.get("parameters") or tc.get("arguments") or tc.get("input") or {}
                    if isinstance(params, str):
                        try:
                            params = json.loads(params)
                        except (json.JSONDecodeError, ValueError):
                            params = {}
                    if isinstance(params, dict):
                        for key in ("file_path", "path", "file", "filename"):
                            if key in params and params[key]:
                                changed_files.append(str(params[key]))

            # Detect questions or needs-input status
            status = str(parsed_json.get("status") or "").lower()
            if status in ("needs-input", "question", "waiting-input"):
                has_question = True

            result_str = str(parsed_json.get("result") or parsed_json.get("text") or "")
            if parsed_json.get("handoff_note"):
                handoff_note = str(parsed_json["handoff_note"])
        else:
            result_str = clean_stdout

        if exit_code == 0:
            outcome = "needs-input" if has_question else "done"
        else:
            outcome = "fail"

        return {
            "outcome": outcome,
            "usage": usage,
            "changed_files": sorted(set(changed_files)),
            "handoff_note": handoff_note,
            "text": result_str,
        }
