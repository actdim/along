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
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Set, Tuple

from .. import proc, runtime as along_runtime
from .base import BaseRunner, merge_args


def _parse_semver(raw: str) -> Optional[Tuple[int, int, int]]:
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", raw or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


class OpenCodeRunner(BaseRunner):
    """OpenCode headless runtime adapter for private and air-gapped workflows (Ollama, vLLM)."""

    runtime: str = "opencode"
    runtime_label: str = "OpenCode"
    default_binary: str = "opencode"
    cli_version: str = along_runtime.OPENCODE_MIN_VERSION
    brief_via_stdin: bool = False
    supports_base_url: bool = True

    RUNTIME_ENV_ALLOW: Set[str] = {
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    }
    RUNTIME_ENV_ALLOW_PREFIXES: Tuple[str, ...] = ("OPENCODE_",)
    VALUE_FLAGS: Set[str] = {
        "-m", "--model", "--format", "-s", "--session",
        "-f", "--file", "--title", "-w", "--worktree",
        "--agent", "--log-level", "--server",
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
        self._checked_version: Optional[str] = None

    @classmethod
    def role_args(cls, role: str) -> List[str]:
        """Return runtime-specific default arguments for OpenCode."""
        return ["--auto"]

    def validate_runtime_version(self, binary: str) -> Optional[str]:
        """Validate installed opencode CLI version once per runner instance."""
        if self._checked_version is not None:
            return self._checked_version
        exe = shutil.which(binary) or (binary if os.path.isfile(binary) else None)
        if not exe:
            return None
        try:
            res = subprocess.run(
                [exe, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
                **proc.spawn_group_kwargs(),
            )
        except (OSError, subprocess.SubprocessError):
            return None
        raw = f"{res.stdout or ''} {res.stderr or ''}".strip()
        parsed = _parse_semver(raw)
        if parsed is None:
            return None
        min_ver = _parse_semver(along_runtime.OPENCODE_MIN_VERSION) or (2, 3, 2)
        if parsed < min_ver:
            ver_str = ".".join(str(x) for x in parsed)
            raise RuntimeError(
                f"OpenCode version {ver_str} is unsupported; minimum supported version is "
                f"{along_runtime.OPENCODE_MIN_VERSION}."
            )
        self._checked_version = ".".join(str(x) for x in parsed)
        return self._checked_version

    def build_command(self, prompt: Optional[str] = None) -> List[str]:
        """Construct command line arguments for OpenCode 2.3.2+ headless execution (uses cwd, not --dir)."""
        binary = self.resolve_binary()
        self.validate_runtime_version(binary)
        cmd = [
            binary,
            "run",
            "--format",
            "json",
        ]
        if self.model:
            cmd.extend(["-m", self.model])
        role = self.role or "implementer"
        r_args = self.role_args(role)
        cmd = merge_args(cmd, r_args, self.VALUE_FLAGS)
        if self.extra_args:
            cmd = merge_args(cmd, self.extra_args, self.VALUE_FLAGS)
        if prompt:
            cmd.append(prompt)
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
        total_cache_read_tokens = 0
        total_cache_write_tokens = 0
        total_reasoning_tokens = 0
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
                        c_read = toks.get("cache_read") or (toks.get("cache") or {}).get("read") or 0
                        c_write = toks.get("cache_write") or (toks.get("cache") or {}).get("write") or 0
                        reas = toks.get("reasoning") or 0
                        try:
                            total_input_tokens += int(in_tok)
                            total_output_tokens += int(out_tok)
                            total_cache_read_tokens += int(c_read)
                            total_cache_write_tokens += int(c_write)
                            total_reasoning_tokens += int(reas)
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
        if total_input_tokens > 0 or total_output_tokens > 0 or total_cache_read_tokens > 0 or total_cost is not None:
            prompt_total = total_input_tokens + total_cache_read_tokens
            cache_hit_pct = round((total_cache_read_tokens / prompt_total) * 100, 1) if prompt_total > 0 else 0.0
            usage = {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "cache_read_tokens": total_cache_read_tokens,
                "cache_write_tokens": total_cache_write_tokens,
                "reasoning_tokens": total_reasoning_tokens,
                "total_tokens": total_input_tokens + total_output_tokens,
                "cache_hit_ratio_pct": cache_hit_pct,
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
