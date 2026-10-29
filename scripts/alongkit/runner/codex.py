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
from typing import Any, Dict, List, Optional, Set, Tuple

from .base import BaseRunner, merge_args


class CodexRunner(BaseRunner):
    """OpenAI Codex headless runtime adapter with JSONL event stream handling."""

    runtime: str = "codex"
    runtime_label: str = "OpenAI Codex"
    default_binary: str = "codex"
    cli_version: str = "0.158.0"
    brief_via_stdin: bool = True

    RUNTIME_ENV_ALLOW: Set[str] = {
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "CODEX_HOME",
    }
    RUNTIME_ENV_ALLOW_PREFIXES: Tuple[str, ...] = ()
    VALUE_FLAGS: Set[str] = {
        "-c", "--config", "-m", "--model", "-p", "--profile",
        "-s", "--sandbox", "-C", "--cd", "--add-dir",
        "--thread-source", "--output-schema", "--color",
        "-o", "--output-last-message", "-i", "--image",
        "--local-provider",
    }

    @classmethod
    def role_args(cls, role: str) -> List[str]:
        """Return runtime-specific default arguments for OpenAI Codex.

        The Codex sandbox blocks network by default; workspace-write allows local
        workspace filesystem writes required by all multi-agent roles.
        """
        return ["--sandbox", "workspace-write"]

    def build_command(self, prompt: Optional[str] = None) -> List[str]:
        """Construct command line arguments for Codex headless execution."""
        binary = self.resolve_binary()
        cmd = [
            binary,
            "exec",
            "--json",
            "--color",
            "never",
            "-C",
            self.repo_root,
        ]
        if self.model:
            cmd.extend(["-m", self.model])
        role = self.role or "implementer"
        r_args = self.role_args(role)
        cmd = merge_args(cmd, r_args, self.VALUE_FLAGS)
        if self.extra_args:
            cmd = merge_args(cmd, self.extra_args, self.VALUE_FLAGS)
        cmd.append("-")
        return cmd

    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> Dict[str, Any]:
        """Parse streaming JSONL event records emitted by Codex CLI."""
        events: List[Dict[str, Any]] = []
        changed_files: List[str] = []
        total_input_tokens = 0
        total_output_tokens = 0
        messages: List[str] = []
        failed = False
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

            if ev_type in ("turn.failed", "error"):
                failed = True

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

            # Handle item.completed
            item = data.get("item")
            if isinstance(item, dict):
                item_type = str(item.get("type") or "").lower()
                if item_type == "agent_message":
                    txt = item.get("text") or item.get("content")
                    if txt and isinstance(txt, str):
                        messages.append(txt)
                elif item_type == "file_change":
                    changes = item.get("changes") or []
                    if isinstance(changes, list):
                        for ch in changes:
                            if isinstance(ch, dict) and ch.get("path"):
                                changed_files.append(str(ch["path"]))

            if "handoff_note" in data:
                handoff_note = str(data["handoff_note"])

        usage = None
        if total_input_tokens > 0 or total_output_tokens > 0:
            usage = {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
            }

        if exit_code == 0 and not failed:
            outcome = "done"
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
