#!/usr/bin/env python3
"""alongkit.runner.base - Base supervisor interface for headless agent CLI runtimes."""

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
import time
from typing import Any, Dict, List, Optional, Set
import uuid

from .. import entities, handoff, proc, repo, session


class RunResult:
    """Encapsulates captured execution metrics and artifacts for a runner invocation."""

    def __init__(
        self,
        run_id: str,
        outcome: str,
        exit_code: Optional[int] = None,
        stdout: str = "",
        stderr: str = "",
        duration_seconds: float = 0.0,
        changed_files: Optional[List[str]] = None,
        usage: Optional[Dict[str, Any]] = None,
        handoff_note: Optional[str] = None,
        record: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.run_id = run_id
        self.outcome = outcome
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.duration_seconds = duration_seconds
        self.changed_files = list(changed_files) if changed_files is not None else []
        self.usage = usage
        self.handoff_note = handoff_note
        self.record = record or {}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize run result to a standard dictionary."""
        return {
            "run_id": self.run_id,
            "outcome": self.outcome,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_seconds": self.duration_seconds,
            "changed_files": self.changed_files,
            "usage": self.usage,
            "handoff_note": self.handoff_note,
            "record": self.record,
        }


class BaseRunner:
    """Base supervisor interface for headless agent CLI runtimes."""

    runtime: str = "generic"
    runtime_label: str = "Generic CLI"
    default_binary: str = "bash"

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
    ) -> None:
        self.repo_root = os.path.abspath(repo_root) if repo_root else (repo.find_repo_root() or os.getcwd())
        self.issue_slug = issue_slug
        self.run_id = str(run_id) if run_id is not None else uuid.uuid4().hex
        self.model = model
        self.timeout = timeout
        self.binary_path = binary_path
        self.dry_run = bool(dry_run)
        self.extra_args = list(extra_args) if extra_args is not None else []
        self.env_overrides = dict(env_overrides) if env_overrides is not None else {}
        self.last_result: Optional[RunResult] = None

    def resolve_binary(self) -> str:
        """Resolve path or executable name for runtime CLI binary."""
        if self.binary_path:
            return self.binary_path
        resolved = shutil.which(self.default_binary)
        if resolved:
            return resolved
        return self.default_binary

    def resolve_active_issue(self) -> str:
        """Resolve active issue slug from parameters, active session, or in-progress issues."""
        if self.issue_slug:
            found = entities.find_issue_by_slug(self.repo_root, self.issue_slug)
            if found:
                self.issue_slug = str(found["slug"])
                return self.issue_slug
            session_dir = session.get_session_dir(self.repo_root, self.issue_slug)
            if os.path.isdir(session_dir):
                return self.issue_slug
            if not self.dry_run:
                raise RuntimeError(
                    f"Cannot run {self.runtime_label}: issue '{self.issue_slug}' not found in .along/ISSUES/."
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
                f"Cannot run {self.runtime_label}: no active in-progress issue found in .along/ISSUES/. Run 'along start <slug>' first."
            )
        return "adhoc"

    def build_command(self, prompt: str) -> List[str]:
        """Construct the subprocess argument list for a headless run."""
        binary = self.resolve_binary()
        cmd = [binary]
        if self.model:
            cmd.extend(["--model", self.model])
        if self.extra_args:
            cmd.extend(self.extra_args)
        cmd.append(prompt)
        return cmd

    def build_env(self) -> Dict[str, str]:
        """Construct execution environment for child runtime process."""
        active_slug = self.resolve_active_issue()
        env = dict(os.environ)
        env.update(proc.UTF8_CHILD_ENV)
        env["ALONG_RUN_ID"] = str(self.run_id)
        env["ALONG_ISSUE_SLUG"] = str(active_slug)
        env["ALONG_REPO_ROOT"] = str(self.repo_root)
        env["ALONG_OBSERVABILITY_LEVEL"] = "complete"
        env["ALONG_OBSERVABILITY_SOURCES"] = f"{self.runtime}_runner,stdout_stream"
        if self.env_overrides:
            env.update(self.env_overrides)
        return env

    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> Dict[str, Any]:
        """Parse runtime-specific output for usage metrics, changed files, and verdict."""
        outcome = "done" if exit_code == 0 else "fail"
        return {
            "outcome": outcome,
            "usage": None,
            "changed_files": [],
            "handoff_note": None,
            "text": stdout,
        }

    def _snapshot_git_status(self) -> Dict[str, str]:
        """Capture snapshot of working tree files via git status --porcelain."""
        try:
            res = proc.git(["status", "--porcelain"], cwd=self.repo_root)
            if not res.ok:
                return {}
            status_map: Dict[str, str] = {}
            for line in res.stdout.splitlines():
                line = line.strip()
                if len(line) >= 3:
                    status = line[:2].strip()
                    path = line[3:].strip()
                    if " -> " in path:
                        path = path.split(" -> ")[1].strip()
                    status_map[path] = status
            return status_map
        except (OSError, RuntimeError):
            return {}

    def _diff_git_status(self, before: Dict[str, str], after: Dict[str, str]) -> List[str]:
        """Find files modified, added, or deleted between two git status snapshots."""
        changed: List[str] = []
        for path, status in after.items():
            if path not in before or before[path] != status:
                changed.append(path)
        return sorted(changed)

    def execute_run(
        self,
        brief: str,
        role: str = "implementer",
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        step: Optional[int] = None,
        run_id: Optional[str] = None,
        handoff_note: Optional[str] = None,
        dry_run: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Launch headless runtime process, monitor execution, and record handoff run result."""
        slug = self.resolve_active_issue()
        effective_run_id = str(run_id) if run_id is not None else self.run_id
        self.run_id = effective_run_id
        effective_model = model if model is not None else self.model
        effective_timeout = timeout if timeout is not None else self.timeout
        is_dry_run = self.dry_run if dry_run is None else bool(dry_run)

        # 1. Initialize in-progress run record
        record = handoff.create_run_record(
            repo_root=self.repo_root,
            slug=slug,
            run_id=effective_run_id,
            role=role,
            runtime=self.runtime,
            model=effective_model,
            step=step,
        )

        cmd = self.build_command(brief)
        env = self.build_env()

        # 2. Handle dry-run preview
        if is_dry_run:
            dry_payload = {
                "dry_run": True,
                "command": cmd,
                "role": role,
                "runtime": self.runtime,
                "model": effective_model,
                "timeout": effective_timeout,
            }
            stdout = json.dumps(dry_payload, indent=2)
            stderr = ""
            record = handoff.finish_run_record(
                repo_root=self.repo_root,
                slug=slug,
                run_id=effective_run_id,
                outcome="done",
                exit_code=0,
                changed_files=[],
                usage=None,
                handoff_note=handoff_note,
            )
            self.last_result = RunResult(
                run_id=effective_run_id,
                outcome="done",
                exit_code=0,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=0.0,
                changed_files=[],
                usage=None,
                handoff_note=handoff_note,
                record=record,
            )
            return record

        # 3. Snapshot working tree prior to process launch
        before_git = self._snapshot_git_status()
        start_time = time.monotonic()

        # 4. Spawn child process
        try:
            proc_obj = subprocess.Popen(
                cmd,
                cwd=self.repo_root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except (FileNotFoundError, OSError) as exc:
            duration = time.monotonic() - start_time
            record = handoff.finish_run_record(
                repo_root=self.repo_root,
                slug=slug,
                run_id=effective_run_id,
                outcome="fail",
                exit_code=127,
                changed_files=[],
                usage=None,
                handoff_note=None,
            )
            self.last_result = RunResult(
                run_id=effective_run_id,
                outcome="fail",
                exit_code=127,
                stdout="",
                stderr=str(exc),
                duration_seconds=duration,
                changed_files=[],
                usage=None,
                handoff_note=None,
                record=record,
            )
            return record

        # 5. Supervise process completion with timeout
        timed_out = False
        try:
            stdout, stderr = proc_obj.communicate(timeout=effective_timeout)
            exit_code = proc_obj.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                proc_obj.kill()
            except OSError:
                pass
            stdout, stderr = proc_obj.communicate()
            exit_code = 124

        duration = time.monotonic() - start_time

        # 6. Parse output and determine outcome
        if timed_out:
            outcome = "timeout"
            parsed: Dict[str, Any] = {"usage": None, "changed_files": [], "handoff_note": None}
        else:
            parsed = self.parse_output(stdout, stderr, exit_code)
            candidate_outcome = parsed.get("outcome")
            if candidate_outcome in handoff.RUN_OUTCOMES:
                outcome = candidate_outcome
            else:
                outcome = "done" if exit_code == 0 else "fail"

        # 7. Collect changed files
        after_git = self._snapshot_git_status()
        git_files = self._diff_git_status(before_git, after_git)
        parsed_files = list(parsed.get("changed_files") or [])
        all_changed = sorted(set(git_files + parsed_files))

        # 8. Check for handoff note
        effective_note = handoff_note or parsed.get("handoff_note")
        if not effective_note:
            note_path = handoff.get_handoff_path(self.repo_root, slug)
            if os.path.isfile(note_path):
                effective_note = "handoff.md"

        # 9. Finalize run record
        record = handoff.finish_run_record(
            repo_root=self.repo_root,
            slug=slug,
            run_id=effective_run_id,
            outcome=outcome,
            exit_code=exit_code,
            changed_files=all_changed,
            usage=parsed.get("usage"),
            handoff_note=effective_note,
        )

        self.last_result = RunResult(
            run_id=effective_run_id,
            outcome=outcome,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
            changed_files=all_changed,
            usage=parsed.get("usage"),
            handoff_note=effective_note,
            record=record,
        )
        return record
