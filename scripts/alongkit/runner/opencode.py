#!/usr/bin/env python3
"""alongkit.runner.opencode - OpenCode headless runtime adapter for local and private workflows."""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

import json
import os
import re
from typing import Any, Dict, List, Optional

from .base import BaseRunner


class OpenCodeRunner(BaseRunner):
    """OpenCode headless runtime adapter for private and air-gapped workflows (Ollama, vLLM)."""

    runtime: str = "opencode"
    runtime_label: str = "OpenCode"
    default_binary: str = "opencode"

    def __init__(
        self,
        repo_root: Optional[str] = None,
        issue_slug: Optional[str] = None,
        run_id: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        binary_path: Optional[str] = None,
        dry_run: bool = False,
        extra_args: Optional[List[str]] = None,
        env_overrides: Optional[Dict[str, str]] = None,
        base_url: Optional[str] = None,
    ) -> None:
        super().__init__(
            repo_root=repo_root,
            issue_slug=issue_slug,
            run_id=run_id,
            model=model,
            timeout=timeout,
            binary_path=binary_path,
            dry_run=dry_run,
            extra_args=extra_args,
            env_overrides=env_overrides,
        )
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")

    def build_command(self, prompt: str) -> List[str]:
        """Construct command line arguments for OpenCode headless execution."""
        binary = self.resolve_binary()
        cmd = [
            binary,
            "run",
            prompt,
            "--yes",
            "--format",
            "json",
        ]
        if self.model:
            cmd.extend(["--model", self.model])
        if self.extra_args:
            cmd.extend(self.extra_args)
        return cmd

    def build_env(self) -> Dict[str, str]:
        """Construct child environment with local inference base URL."""
        env = super().build_env()
        if self.base_url:
            env["OPENAI_BASE_URL"] = str(self.base_url)
        return env

    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> Dict[str, Any]:
        """Parse structured output emitted by OpenCode --format json."""
        clean_stdout = stdout.strip()
        parsed_json: Optional[Dict[str, Any]] = None

        if clean_stdout:
            try:
                data = json.loads(clean_stdout)
                if isinstance(data, dict):
                    parsed_json = data
            except (json.JSONDecodeError, ValueError):
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
            raw_usage = parsed_json.get("usage") or parsed_json.get("tokens") or parsed_json.get("stats")
            if isinstance(raw_usage, dict):
                usage = {
                    "input_tokens": raw_usage.get("input_tokens") or raw_usage.get("prompt_tokens") or 0,
                    "output_tokens": raw_usage.get("output_tokens") or raw_usage.get("completion_tokens") or 0,
                }

            raw_tools = parsed_json.get("tool_calls") or parsed_json.get("tools") or []
            if isinstance(raw_tools, list):
                for tc in raw_tools:
                    if not isinstance(tc, dict):
                        continue
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

            status = str(parsed_json.get("status") or "").lower()
            if status in ("needs-input", "question", "ask"):
                has_question = True

            result_str = str(parsed_json.get("result") or parsed_json.get("text") or parsed_json.get("output") or "")
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
