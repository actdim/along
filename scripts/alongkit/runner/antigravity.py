#!/usr/bin/env python3
"""alongkit.runner.antigravity - Antigravity runtime process supervisor and telemetry coordinator."""

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
import sys
from typing import Any, Dict, List, Optional
import uuid

from .. import entities, proc, repo, session
from ..telemetry.models import StatusCode
from ..telemetry.tracer import Tracer
from .stream import ChunkedStreamSupervisor


class AntigravityRunner:
    """Antigravity agent runtime process supervisor and telemetry coordinator."""

    def __init__(
        self,
        repo_root: Optional[str] = None,
        issue_slug: Optional[str] = None,
        run_id: Optional[str] = None,
        otel_endpoint: Optional[str] = None,
        binary_path: Optional[str] = None,
        dry_run: bool = False,
        extra_args: Optional[List[str]] = None,
    ) -> None:
        self.repo_root = os.path.abspath(repo_root) if repo_root else (repo.find_repo_root() or os.getcwd())
        self.issue_slug = issue_slug
        self.run_id = str(run_id) if run_id is not None else uuid.uuid4().hex
        self.otel_endpoint = otel_endpoint
        self.binary_path = binary_path
        self.dry_run = bool(dry_run)
        self.extra_args = list(extra_args) if extra_args is not None else []

    def resolve_binary(self) -> str:
        """Resolve path or executable name for Antigravity runtime."""
        if self.binary_path:
            return self.binary_path

        candidates = ["antigravity", "agy", "antigravity-ide"]
        for candidate in candidates:
            resolved = shutil.which(candidate)
            if resolved:
                return resolved

        if os.name == "nt":
            local_app_data = os.environ.get("LOCALAPPDATA")
            prog_files = os.environ.get("PROGRAMFILES")
            prog_files_x86 = os.environ.get("PROGRAMFILES(X86)")
            win_candidates: List[str] = []
            if local_app_data:
                win_candidates.extend([
                    os.path.join(local_app_data, "Programs", "antigravity", "antigravity.exe"),
                    os.path.join(local_app_data, "Programs", "Antigravity", "Antigravity.exe"),
                    os.path.join(local_app_data, "Programs", "agy", "agy.exe"),
                    os.path.join(local_app_data, "antigravity", "bin", "antigravity.exe"),
                    os.path.join(local_app_data, "Programs", "antigravity-ide", "antigravity-ide.exe"),
                ])
            if prog_files:
                win_candidates.extend([
                    os.path.join(prog_files, "Antigravity", "antigravity.exe"),
                    os.path.join(prog_files, "Antigravity", "bin", "antigravity.exe"),
                    os.path.join(prog_files, "antigravity-ide", "antigravity-ide.exe"),
                ])
            if prog_files_x86:
                win_candidates.extend([
                    os.path.join(prog_files_x86, "Antigravity", "antigravity.exe"),
                    os.path.join(prog_files_x86, "Antigravity", "bin", "antigravity.exe"),
                ])
            for win_path in win_candidates:
                try:
                    if os.path.isfile(win_path):
                        return win_path
                except OSError:
                    pass

        return "antigravity"

    def resolve_active_issue(self) -> str:
        """Resolve active issue slug from parameters, active session, or in-progress issues."""
        if self.issue_slug:
            found = entities.find_issue_by_slug(self.repo_root, self.issue_slug)
            if found:
                self.issue_slug = str(found["slug"])
                return self.issue_slug
            if not self.dry_run:
                raise RuntimeError(
                    f"Cannot run Antigravity: issue '{self.issue_slug}' not found in .along/ISSUES/."
                )
            return self.issue_slug

        active_slug = session.get_active_session_slug(self.repo_root)
        if active_slug:
            found = entities.find_issue_by_slug(self.repo_root, active_slug)
            if found:
                self.issue_slug = str(found["slug"])
                return self.issue_slug
            self.issue_slug = active_slug
            return self.issue_slug

        issues = entities.scan_issues(self.repo_root, include_done=False)
        in_progress = [iss for iss in issues if iss.get("status") == "in-progress"]
        if in_progress:
            self.issue_slug = str(in_progress[0]["slug"])
            return self.issue_slug

        if not self.dry_run:
            raise RuntimeError(
                "Cannot run Antigravity: no active in-progress issue found in .along/ISSUES/. Run 'along start <slug>' first."
            )
        return "adhoc"

    def build_env(self) -> Dict[str, str]:
        """Build execution environment for Antigravity child process."""
        if not self.run_id:
            self.run_id = uuid.uuid4().hex

        active_slug = self.resolve_active_issue()

        env = dict(os.environ)
        env.update(proc.UTF8_CHILD_ENV)
        env["ALONG_RUN_ID"] = str(self.run_id)
        env["ALONG_ISSUE_SLUG"] = str(active_slug)
        env["ALONG_REPO_ROOT"] = str(self.repo_root)
        env["ALONG_OBSERVABILITY_LEVEL"] = "complete"
        env["ALONG_OBSERVABILITY_SOURCES"] = "antigravity_hook,stdout_stream"
        if self.otel_endpoint:
            env["ALONG_OTEL_ENDPOINT"] = str(self.otel_endpoint)
        return env

    def run(self) -> int:
        """Run Antigravity session in dry-run or supervised mode."""
        binary = self.resolve_binary()
        try:
            env = self.build_env()
        except RuntimeError as exc:
            sys.stderr.write(f"[Error] {exc}\n")
            return 1

        if self.dry_run:
            details = {
                "binary": binary,
                "repo_root": self.repo_root,
                "issue_slug": self.issue_slug,
                "run_id": self.run_id,
                "extra_args": self.extra_args,
                "env": {
                    k: env[k]
                    for k in sorted(env)
                    if k.startswith("ALONG_") or k in ("PYTHONIOENCODING", "PYTHONUTF8")
                },
            }
            print(json.dumps(details, indent=2))
            return 0

        tracer_kwargs: Dict[str, Any] = {
            "repo_root": self.repo_root,
            "run_id": self.run_id,
            "issue_slug": self.issue_slug or "adhoc",
            "agent_name": "antigravity",
        }
        if self.otel_endpoint:
            from ..telemetry.otlp import OTLPExporter
            from ..telemetry.spool import Spooler

            spooler = Spooler(self.repo_root, self.run_id)
            tracer_kwargs["exporter"] = OTLPExporter(endpoint=self.otel_endpoint, spooler=spooler)

        tracer = Tracer(**tracer_kwargs)
        tracer.start_run(
            observability_level="complete",
            sources=["antigravity_hook", "stdout_stream"],
        )

        cmd = [binary, *self.extra_args]
        try:
            process = subprocess.Popen(
                cmd,
                cwd=self.repo_root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except (OSError, ValueError) as exc:
            sys.stderr.write(f"[Error] Failed to spawn Antigravity process {cmd}: {exc}\n")
            tracer.end_run(status=StatusCode.ERROR, message=str(exc))
            return 127

        supervisor = ChunkedStreamSupervisor(
            process,
            tracer=tracer,
            repo_root=self.repo_root,
            run_id=self.run_id,
        )
        try:
            supervisor.start()
            code = supervisor.wait()
        except (KeyboardInterrupt, SystemExit):
            try:
                process.kill()
            except OSError:
                pass
            tracer.end_run(status=StatusCode.ERROR, message="interrupted")
            raise
        except (OSError, RuntimeError) as exc:
            tracer.end_run(status=StatusCode.ERROR, message=str(exc))
            return 1

        tracer.end_run(status=StatusCode.OK if code == 0 else StatusCode.ERROR)
        return code
