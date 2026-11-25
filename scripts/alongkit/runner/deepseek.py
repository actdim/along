#!/usr/bin/env python3
"""alongkit.runner.deepseek - DeepSeek Harness (DSH) headless runtime adapter."""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

import json
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .. import handoff, proc
from .base import BaseRunner, merge_args


class DeepSeekHarnessRunner(BaseRunner):
    """DeepSeek Harness (DSH) headless runtime adapter (DSH CLI only, not DeepSeek HTTP API)."""

    runtime: str = "deepseek"
    runtime_label: str = "DeepSeek Harness (DSH)"
    default_binary: str = "dsh"
    cli_version: str = "unverified"
    version_verified: bool = False
    brief_via_stdin: bool = True
    supports_base_url: bool = False
    DEFAULT_TIMEOUT_SECONDS: int = 600

    RUNTIME_ENV_ALLOW: Set[str] = {
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "DSH_HOME",
        "DSH_PERMISSION_MODE",
        "DSH_TELEMETRY_MODE",
        "DSH_TOOLS_MODE",
    }
    RUNTIME_ENV_ALLOW_PREFIXES: Tuple[str, ...] = ("DSH_", "DEEPSEEK_")
    VALUE_FLAGS: Set[str] = {
        "--profile",
        "--patch",
        "--from-default-profile",
        "--session-id",
        "--model",
        "-m",
    }

    def __init__(
        self,
        repo_root: Optional[str] = None,
        issue_slug: Optional[str] = None,
        run_id: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[Union[int, float]] = None,
        binary_path: Optional[str] = None,
        dry_run: bool = False,
        extra_args: Optional[List[str]] = None,
        env_overrides: Optional[Dict[str, str]] = None,
        role: Optional[str] = None,
        env_passthrough: Optional[List[str]] = None,
        brief_via_stdin: bool = True,
        timeout_seconds: Optional[Union[int, float]] = None,
    ) -> None:
        raw_timeout = timeout if timeout is not None else timeout_seconds
        if raw_timeout is None:
            raw_timeout = self.DEFAULT_TIMEOUT_SECONDS
        if float(raw_timeout) <= 0:
            raise ValueError(f"DeepSeekHarnessRunner timeout must be positive, got {raw_timeout!r}")
        super().__init__(
            repo_root=repo_root,
            issue_slug=issue_slug,
            run_id=run_id,
            model=model,
            timeout=raw_timeout,  # type: ignore[arg-type]
            binary_path=binary_path,
            dry_run=dry_run,
            extra_args=extra_args,
            env_overrides=env_overrides,
            role=role,
            env_passthrough=env_passthrough,
        )
        self.brief_via_stdin = bool(brief_via_stdin)
        self.timeout_seconds = raw_timeout

    @classmethod
    def role_args(cls, role: str) -> List[str]:
        """Return runtime-specific default arguments for DSH."""
        return []

    def resolve_binary(self) -> str:
        """Resolve path or executable name for DSH CLI binary."""
        if self.binary_path:
            return self.binary_path
        resolved = shutil.which(self.default_binary)
        if resolved:
            return resolved

        # Windows default installation fallback
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            candidate = os.path.join(
                local_app_data,
                "Programs",
                "DeepSeek Harness",
                "resources",
                "runtime",
                "cli",
                "bin",
                "dsh.cmd",
            )
            if os.path.isfile(candidate):
                return candidate

        return self.default_binary

    def resolve_version(self) -> Tuple[str, bool]:
        """Probe `dsh --version` when the binary exists; otherwise mark as unverified."""
        binary = self.resolve_binary()
        exe = shutil.which(binary) or (binary if os.path.isfile(binary) else None)
        if not exe:
            return "unverified", False
        try:
            res = subprocess.run(
                [exe, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
                **proc.spawn_group_kwargs(),
            )
            raw = (res.stdout or res.stderr or "").strip()
            if res.returncode == 0 and raw:
                return raw.splitlines()[0].strip(), True
        except (OSError, subprocess.SubprocessError):
            pass
        return "unverified", False

    def build_command(self, prompt: Optional[str] = None) -> List[str]:
        """Construct command line arguments for DSH headless execution."""
        binary = self.resolve_binary()
        cmd = [
            binary,
            "--profile",
            "headless",
            "--json",
        ]
        if self.model:
            cmd.extend(["--model", self.model])
        role = self.role or "implementer"
        r_args = self.role_args(role)
        cmd = merge_args(cmd, r_args, self.VALUE_FLAGS)
        if self.extra_args:
            cmd = merge_args(cmd, self.extra_args, self.VALUE_FLAGS)

        if self.brief_via_stdin:
            cmd.append("-")
        elif prompt:
            cmd.append(prompt)

        return cmd

    def build_env(self) -> Dict[str, str]:
        """Construct child environment with non-interactive headless permission mode."""
        env = super().build_env()
        # Headless runs require danger-full-access or workspace-write to avoid blocking on user approval
        if "DSH_PERMISSION_MODE" not in env:
            env["DSH_PERMISSION_MODE"] = "danger-full-access"
        return env

    def execute_run(
        self,
        brief: str,
        role: str = "implementer",
        model: Optional[str] = None,
        timeout: Optional[Union[int, float]] = None,
        step: Optional[int] = None,
        run_id: Optional[str] = None,
        handoff_note: Optional[str] = None,
        dry_run: Optional[bool] = None,
        timeout_seconds: Optional[Union[int, float]] = None,
    ) -> Dict[str, Any]:
        """Launch headless DSH process with a mandatory timeout safety net."""
        eff_timeout = timeout if timeout is not None else (
            timeout_seconds if timeout_seconds is not None else self.timeout_seconds
        )
        if eff_timeout is None:
            eff_timeout = self.DEFAULT_TIMEOUT_SECONDS
        if float(eff_timeout) <= 0:
            raise ValueError(f"DeepSeekHarnessRunner timeout must be positive, got {eff_timeout!r}")
        return super().execute_run(
            brief=brief,
            role=role,
            model=model,
            timeout=eff_timeout,  # type: ignore[arg-type]
            step=step,
            run_id=run_id,
            handoff_note=handoff_note,
            dry_run=dry_run,
        )

    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> Dict[str, Any]:
        """Parse structured NDJSON or JSON events emitted by DSH headless."""
        changed_files: List[str] = []
        messages: List[str] = []
        total_input_tokens = 0
        total_output_tokens = 0
        total_cache_read_tokens = 0
        total_cache_write_tokens = 0
        total_reasoning_tokens = 0
        failed = False
        handoff_note: Optional[str] = None

        clean_stdout = stdout.strip()

        # Try parsing as a single top-level JSON object first (e.g. from tests or mock wrappers)
        parsed_single = False
        if clean_stdout.startswith("{") and clean_stdout.endswith("}"):
            try:
                single_data = json.loads(clean_stdout)
                if isinstance(single_data, dict):
                    parsed_single = True
                    if single_data.get("is_error"):
                        failed = True
                    raw_usage = single_data.get("usage")
                    if isinstance(raw_usage, dict):
                        total_input_tokens = int(raw_usage.get("input_tokens") or raw_usage.get("prompt_tokens") or 0)
                        total_output_tokens = int(raw_usage.get("output_tokens") or raw_usage.get("completion_tokens") or 0)
                        total_cache_read_tokens = int(raw_usage.get("cache_read_tokens") or raw_usage.get("prompt_cache_hit_tokens") or 0)
                        total_cache_write_tokens = int(raw_usage.get("cache_write_tokens") or raw_usage.get("prompt_cache_miss_tokens") or 0)
                        total_reasoning_tokens = int(raw_usage.get("reasoning_tokens") or 0)
                    if single_data.get("text"):
                        messages.append(str(single_data["text"]))
                    if single_data.get("handoff_note"):
                        handoff_note = str(single_data["handoff_note"])
                    if isinstance(single_data.get("changed_files"), list):
                        changed_files.extend(str(f) for f in single_data["changed_files"])
            except (json.JSONDecodeError, ValueError, TypeError):
                parsed_single = False

        if not parsed_single:
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

                ev_type = str(data.get("type") or "").lower()
                if ev_type in ("error", "fatal"):
                    failed = True

                part = data.get("part")
                if isinstance(part, dict):
                    part_type = str(part.get("type") or "").lower()
                    if ev_type == "text" or part_type == "text":
                        txt = part.get("text")
                        if txt and isinstance(txt, str):
                            messages.append(txt)

                    elif ev_type in ("tool_use", "tool_call") or part_type in ("tool", "tool_call"):
                        state = part.get("state")
                        inp = state.get("input") if isinstance(state, dict) else part.get("input")
                        if isinstance(inp, dict):
                            for key in ("filePath", "file_path", "path", "file", "filename"):
                                if key in inp and inp[key]:
                                    changed_files.append(str(inp[key]))

                    elif ev_type in ("step_finish", "step-finish") or part_type in ("step_finish", "step-finish"):
                        toks = part.get("tokens")
                        if isinstance(toks, dict):
                            in_tok = toks.get("input") or 0
                            out_tok = toks.get("output") or 0
                            c_read = toks.get("cache_read") or (toks.get("cache") or {}).get("read") or toks.get("prompt_cache_hit_tokens") or 0
                            c_write = toks.get("cache_write") or (toks.get("cache") or {}).get("write") or toks.get("prompt_cache_miss_tokens") or 0
                            reas = toks.get("reasoning") or toks.get("reasoning_tokens") or 0
                            try:
                                total_input_tokens += int(in_tok)
                                total_output_tokens += int(out_tok)
                                total_cache_read_tokens += int(c_read)
                                total_cache_write_tokens += int(c_write)
                                total_reasoning_tokens += int(reas)
                            except (ValueError, TypeError):
                                pass

                # Top-level direct keys
                if "text" in data and isinstance(data["text"], str):
                    messages.append(data["text"])
                if "handoff_note" in data:
                    handoff_note = str(data["handoff_note"])
                if "usage" in data and isinstance(data["usage"], dict):
                    u = data["usage"]
                    try:
                        total_input_tokens += int(u.get("input_tokens") or u.get("prompt_tokens") or 0)
                        total_output_tokens += int(u.get("output_tokens") or u.get("completion_tokens") or 0)
                        c_read = u.get("cache_read_tokens") or u.get("prompt_cache_hit_tokens") or 0
                        c_write = u.get("cache_write_tokens") or u.get("prompt_cache_miss_tokens") or 0
                        reas = u.get("reasoning_tokens") or 0
                        total_cache_read_tokens += int(c_read)
                        total_cache_write_tokens += int(c_write)
                        total_reasoning_tokens += int(reas)
                    except (ValueError, TypeError):
                        pass

        usage = None
        if total_input_tokens > 0 or total_output_tokens > 0 or total_cache_read_tokens > 0:
            cache_hit_pct = handoff.compute_cache_hit_ratio_pct(total_input_tokens, total_cache_read_tokens)
            usage = {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "cache_read_tokens": total_cache_read_tokens,
                "cache_write_tokens": total_cache_write_tokens,
                "reasoning_tokens": total_reasoning_tokens,
                "total_tokens": total_input_tokens + total_output_tokens,
                "cache_hit_ratio_pct": cache_hit_pct,
            }

        if exit_code == 0 and not failed:
            outcome = "done"
        else:
            outcome = "fail"

        final_text = "".join(messages) if messages else clean_stdout

        return {
            "outcome": outcome,
            "usage": usage,
            "changed_files": sorted(set(changed_files)),
            "handoff_note": handoff_note,
            "text": final_text,
        }


def format_usage_summary(usage: Optional[Dict[str, Any]]) -> str:
    """Format token and cache usage dictionary into human-readable summary."""
    if not usage:
        return "No token usage recorded."
    in_tok = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    out_tok = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    c_read = int(usage.get("cache_read_tokens") or usage.get("prompt_cache_hit_tokens") or 0)
    c_write = int(usage.get("cache_write_tokens") or usage.get("prompt_cache_miss_tokens") or 0)
    if "cache_hit_ratio_pct" in usage and usage["cache_hit_ratio_pct"] is not None:
        ratio = usage["cache_hit_ratio_pct"]
    else:
        ratio = handoff.compute_cache_hit_ratio_pct(in_tok, c_read)
    reasoning = int(usage.get("reasoning_tokens") or 0)
    parts = [
        f"input: {in_tok}",
        f"output: {out_tok}",
        f"cache read: {c_read}",
        f"cache write: {c_write}",
        f"cache hit: {ratio}%",
    ]
    if reasoning:
        parts.append(f"reasoning: {reasoning}")
    return ", ".join(parts)
