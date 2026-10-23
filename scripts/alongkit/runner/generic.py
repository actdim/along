#!/usr/bin/env python3
"""alongkit.runner.generic - Fallback generic CLI runner capturing exit codes, timeouts, and lines."""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

import os
from typing import Any, Dict, List, Optional

from .base import BaseRunner


class GenericCliRunner(BaseRunner):
    """Fallback generic CLI adapter with exit code, timeout, and line-buffered stream capture."""

    runtime: str = "generic"
    runtime_label: str = "Generic CLI"
    default_binary: str = "bash" if os.name != "nt" else "powershell"

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
        command_template: Optional[List[str]] = None,
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
        self.command_template = list(command_template) if command_template is not None else None
        self.stdout_lines: List[str] = []
        self.stderr_lines: List[str] = []

    def build_command(self, prompt: str) -> List[str]:
        """Construct command line arguments from custom template or generic binary invocation."""
        if self.command_template:
            cmd: List[str] = []
            has_placeholder = False
            for part in self.command_template:
                if "{prompt}" in part:
                    cmd.append(part.replace("{prompt}", prompt))
                    has_placeholder = True
                else:
                    cmd.append(part)
            if not has_placeholder:
                cmd.append(prompt)
            return cmd

        binary = self.resolve_binary()
        cmd = [binary]
        if self.extra_args:
            cmd.extend(self.extra_args)
        cmd.append(prompt)
        return cmd

    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> Dict[str, Any]:
        """Buffer and parse stdout/stderr lines and determine process outcome."""
        self.stdout_lines = stdout.splitlines()
        self.stderr_lines = stderr.splitlines()
        outcome = "done" if exit_code == 0 else "fail"
        return {
            "outcome": outcome,
            "usage": None,
            "changed_files": [],
            "handoff_note": None,
            "stdout_lines": list(self.stdout_lines),
            "stderr_lines": list(self.stderr_lines),
            "text": stdout,
        }
