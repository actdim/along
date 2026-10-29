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
from typing import Any, Dict, List, Optional, Set, Tuple

from .base import BaseRunner, merge_args


class OpenCodeRunner(BaseRunner):
    """OpenCode headless runtime adapter for private and air-gapped workflows (Ollama, vLLM)."""

    runtime: str = "opencode"
    runtime_label: str = "OpenCode"
    default_binary: str = "opencode"
    cli_version: str = "1.18.32"
    brief_via_stdin: bool = True

    RUNTIME_ENV_ALLOW: Set[str] = {
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    }
    RUNTIME_ENV_ALLOW_PREFIXES: Tuple[str, ...] = ("OPENCODE_",)
    VALUE_FLAGS: Set[str] = {
        "-m", "--model", "--format", "--dir", "-s", "--session",
        "-f", "--file", "--title", "--attach", "-p", "--password",
        "-u", "--username", "--port", "--variant", "--command", "--log-level",
    }

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
        role: Optional[str] = None,
        env_passthrough: Optional[List[str]] = None,
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
            role=role,
            env_passthrough=env_passthrough,
        )
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")

    @classmethod
    def role_args(cls, role: str) -> List[str]:
        """Return runtime-specific default arguments for OpenCode."""
        return ["--auto"]

    def build_command(self, prompt: Optional[str] = None) -> List[str]:
        """Construct command line arguments for OpenCode headless execution."""
        binary = self.resolve_binary()
        cmd = [
            binary,
            "run",
            "--format",
            "json",
            "--dir",
            self.repo_root,
        ]
        if self.model:
            cmd.extend(["-m", self.model])
        role = self.role or "implementer"
        r_args = self.role_args(role)
        cmd = merge_args(cmd, r_args, self.VALUE_FLAGS)
        if self.extra_args:
            cmd = merge_args(cmd, self.extra_args, self.VALUE_FLAGS)
        return cmd

    def build_env(self) -> Dict[str, str]:
        """Construct child environment with local inference base URL."""
        env = super().build_env()
        if self.base_url:
            env["OPENAI_BASE_URL"] = str(self.base_url)
        return env

    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> Dict[str, Any]:
        """Parse structured JSONL output emitted by OpenCode --format json."""
        changed_files: List[str] = []
        messages: List[str] = []
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost: Optional[float] = None
        failed = False
        handoff_note: Optional[str] = None
        events: List[Dict[str, Any]] = []

        for raw_line in stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(data, dict):
                continue

            events.append(data)
            ev_type = str(data.get("type") or "").lower()

            if ev_type == "error":
                failed = True

            part = data.get("part")
            if isinstance(part, dict):
                part_type = str(part.get("type") or "").lower()
                if ev_type == "text" or part_type == "text":
                    txt = part.get("text")
                    if txt and isinstance(txt, str):
                        messages.append(txt)

                elif ev_type == "tool_use" or part_type == "tool":
                    state = part.get("state")
                    inp = state.get("input") if isinstance(state, dict) else part.get("input")
                    if isinstance(inp, dict):
                        for key in ("filePath", "file_path", "path", "file", "filename"):
                            if key in inp and inp[key]:
                                changed_files.append(str(inp[key]))

                elif ev_type == "step_finish" or part_type == "step-finish":
                    toks = part.get("tokens")
                    if isinstance(toks, dict):
                        in_tok = toks.get("input") or 0
                        out_tok = toks.get("output") or 0
                        try:
                            total_input_tokens += int(in_tok)
                            total_output_tokens += int(out_tok)
                        except (ValueError, TypeError):
                            pass
                    if "cost" in part and part["cost"] is not None:
                        try:
                            c = float(part["cost"])
                            total_cost = (total_cost or 0.0) + c
                        except (ValueError, TypeError):
                            pass

            if "handoff_note" in data:
                handoff_note = str(data["handoff_note"])

        usage = None
        if total_input_tokens > 0 or total_output_tokens > 0 or total_cost is not None:
            usage = {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
            }
            if total_cost is not None:
                usage["cost"] = total_cost

        if exit_code == 0 and not failed:
            outcome = "done"
        else:
            outcome = "fail"

        final_text = "".join(messages) if messages else stdout.strip()

        return {
            "outcome": outcome,
            "usage": usage,
            "changed_files": sorted(set(changed_files)),
            "handoff_note": handoff_note,
            "text": final_text,
        }
