#!/usr/bin/env python3
"""
tests/test_orchestrator_telemetry.py - Hermetic tests for orchestrator telemetry instrumentation and OTel spans.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import orchestrator, session
from alongkit.runner.base import BaseRunner, RunResult
from alongkit.telemetry.models import StatusCode


class MockTestRunner(BaseRunner):
    runtime = "mock-runner"
    runtime_label = "MockRunner"

    def __init__(self, *args, **kwargs):
        kwargs.pop("runtime", None)
        super().__init__(*args, **kwargs)

    def execute_run(self, brief: str, role: str, step: int | None = None, dry_run: bool = False) -> dict:
        # Simulate successful role execution
        if role == "scout":
            session_dir = session.get_session_dir(self.repo_root, self.issue_slug)
            os.makedirs(session_dir, exist_ok=True)
            with open(os.path.join(session_dir, "research.md"), "w", encoding="utf-8") as f:
                f.write("# Research\nFound symbols and facts.")
            return {"outcome": "done", "exit_code": 0}

        if role == "architect":
            plan_file = session.plan_path(self.repo_root, self.issue_slug)
            os.makedirs(os.path.dirname(plan_file), exist_ok=True)
            with open(plan_file, "w", encoding="utf-8") as f:
                f.write("# Plan\n- Step 1: Initialize module\n- Step 2: Implement logic\n")
            return {"outcome": "done", "exit_code": 0}

        if role == "implementer":
            return {"outcome": "done", "exit_code": 0, "changed_files": ["lib.py"]}

        if role == "reviewer":
            review_dir = os.path.join(session.get_session_dir(self.repo_root, self.issue_slug), "reviews")
            os.makedirs(review_dir, exist_ok=True)
            rev_file = os.path.join(review_dir, f"step-{step}.md")
            with open(rev_file, "w", encoding="utf-8") as f:
                f.write("---\nverdict: PASS\n---\nAll criteria satisfied.")
            return {"outcome": "done", "exit_code": 0}

        return {"outcome": "done", "exit_code": 0}


class TestOrchestratorTelemetry(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = self.tmpdir.name

        # Create basic issue structure
        issues_dir = os.path.join(self.repo_root, ".along", "ISSUES")
        os.makedirs(issues_dir, exist_ok=True)
        self.slug = "test-task"
        issue_file = os.path.join(issues_dir, f"feat--{self.slug}.md")
        with open(issue_file, "w", encoding="utf-8") as f:
            f.write(
                f"---\nslug: {self.slug}\ntype: feat\nstatus: in-progress\npriority: medium\n---\n# Test Task\n"
            )

        # Allow architect self approval for test
        os.environ["ALONG_ARCHITECT_SELF_APPROVAL"] = "1"

    def tearDown(self) -> None:
        os.environ.pop("ALONG_ARCHITECT_SELF_APPROVAL", None)
        self.tmpdir.cleanup()

    def test_orchestrator_initializes_tracer_and_emits_phase_spans(self) -> None:
        def runner_factory(**kwargs):
            return MockTestRunner(**kwargs)

        orch = orchestrator.CrossRuntimeOrchestrator(
            repo_root=self.repo_root,
            slug=self.slug,
            runner_factory=runner_factory,
            profile="cross-tiered",
        )

        self.assertIsNotNone(orch.tracer)
        self.assertEqual(orch.profile_name, "cross-tiered")

        # Mock exporter export to capture spans
        captured_spans = []
        if orch.tracer and orch.tracer.exporter:
            orch.tracer.exporter.export = lambda spans, **kw: captured_spans.extend(spans) or True

        result = orch.orchestrate()
        self.assertEqual(result.get("status"), "completed")

        # Verify emitted spans
        span_names = [s.name if hasattr(s, "name") else s.get("name") for s in captured_spans]
        self.assertIn("along.agent.run", span_names)
        self.assertIn("phase.scout", span_names)
        self.assertIn("phase.architect", span_names)
        self.assertIn("phase.step.1", span_names)
        self.assertIn("phase.reviewer.1", span_names)

        # Verify root span attributes
        root_spans = [s for s in captured_spans if (s.name if hasattr(s, "name") else s.get("name")) == "along.agent.run"]
        self.assertTrue(len(root_spans) > 0)
        root = root_spans[0]
        attrs = root.attributes if hasattr(root, "attributes") else root.get("attributes", {})
        self.assertEqual(attrs.get("along.issue.slug"), self.slug)
        self.assertEqual(attrs.get("along.orchestration.profile"), "cross-tiered")

    def test_orchestrator_fails_open_when_telemetry_fails(self) -> None:
        def runner_factory(**kwargs):
            return MockTestRunner(**kwargs)

        orch = orchestrator.CrossRuntimeOrchestrator(
            repo_root=self.repo_root,
            slug=self.slug,
            runner_factory=runner_factory,
            profile="direct",
        )

        # Force exporter to fail and simulate unreachable backend
        if orch.tracer and orch.tracer.exporter:
            def failing_export(spans, **kw):
                raise OSError("Connection refused by OpenObserve")
            orch.tracer.exporter.export = failing_export

        # Orchestration must succeed despite telemetry network failure
        result = orch.orchestrate()
        self.assertEqual(result.get("status"), "completed")


if __name__ == "__main__":
    unittest.main()
