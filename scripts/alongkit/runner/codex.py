#!/usr/bin/env python3
"""alongkit.runner.codex - OpenAI Codex headless runtime adapter."""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

import json
from typing import Any, Dict, List, Optional

from .base import BaseRunner


class CodexRunner(BaseRunner):
    """OpenAI Codex headless runtime adapter with JSONL event stream handling."""

    runtime: str = "codex"
    runtime_label: str = "OpenAI Codex"
    default_binary: str = "codex"

    def build_command(self, prompt: str) -> List[str]:
        """Construct command line arguments for Codex headless execution."""
        binary = self.resolve_binary()
        cmd = [
            binary,
            "exec",
            prompt,
            "--non-interactive",
            "--json",
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
            env["OPENAI_MODEL"] = self.model
        return env

    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> Dict[str, Any]:
        """Parse streaming JSONL event records emitted by Codex CLI."""
        events: List[Dict[str, Any]] = []
        changed_files: List[str] = []
        total_input_tokens = 0
        total_output_tokens = 0
        messages: List[str] = []
        has_question = False
        handoff_note: Optional[str] = None

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

            # Handle usage and token counts
            raw_usage = data.get("usage")
            if isinstance(raw_usage, dict):
                in_tok = raw_usage.get("input_tokens") or raw_usage.get("prompt_tokens") or 0
                out_tok = raw_usage.get("output_tokens") or raw_usage.get("completion_tokens") or 0
                try:
                    total_input_tokens += int(in_tok)
                    total_output_tokens += int(out_tok)
                except (ValueError, TypeError):
                    pass

            # Handle tool calls and patch events
            item = data.get("item")
            target = item if isinstance(item, dict) else data
            item_type = str(target.get("type") or "").lower()

            if "tool" in item_type or "patch" in item_type or "call" in item_type:
                call_info = target.get("call") or target.get("parameters") or target.get("arguments") or {}
                if isinstance(call_info, str):
                    try:
                        call_info = json.loads(call_info)
                    except (json.JSONDecodeError, ValueError):
                        call_info = {}
                if isinstance(call_info, dict):
                    for key in ("file", "path", "file_path", "filename"):
                        if key in call_info and call_info[key]:
                            changed_files.append(str(call_info[key]))

            if "question" in ev_type or "ask" in ev_type or "question" in item_type:
                has_question = True

            if "content" in target and isinstance(target["content"], str):
                messages.append(target["content"])
            elif "message" in target and isinstance(target["message"], str):
                messages.append(target["message"])

            if "handoff_note" in data:
                handoff_note = str(data["handoff_note"])

        usage = None
        if total_input_tokens > 0 or total_output_tokens > 0:
            usage = {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
            }

        if exit_code == 0:
            outcome = "needs-input" if has_question else "done"
        else:
            outcome = "fail"

        final_text = "\n".join(messages) if messages else stdout.strip()

        return {
            "outcome": outcome,
            "usage": usage,
            "changed_files": sorted(set(changed_files)),
            "handoff_note": handoff_note,
            "text": final_text,
            "events_count": len(events),
        }
