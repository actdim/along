#!/usr/bin/env python3
"""tests/test_orchestrator.py - Unit tests for cross-runtime supervisor orchestrator."""

from __future__ import annotations

import json
import os
import shutil
import sys
import unittest

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

import hermetic
from alongkit import handoff, orchestrator, session, textio
from alongkit.commands.orchestrator import handle_orchestrate_command, handle_team_command
from alongkit.runner import BaseRunner, RunResult


class MockRunner(BaseRunner):
    """Hermetic simulated runner for orchestrator unit tests."""

    def __init__(
        self,
        outcome: str = "done",
        changed_files: list | None = None,
        exit_code: int = 0,
        on_execute: callable | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.outcome = outcome
        self.changed_files = changed_files or []
        self.mock_exit_code = exit_code
        self.on_execute = on_execute
        self.invocations: list = []

    def execute_run(
        self,
        brief: str,
        role: str = "implementer",
        model: str | None = None,
        timeout: int | None = None,
        step: int | None = None,
        run_id: str | None = None,
        handoff_note: str | None = None,
        dry_run: bool | None = None,
    ) -> dict:
        eff_run_id = str(run_id or self.run_id)
        self.invocations.append({
            "role": role,
            "step": step,
            "brief": brief,
            "run_id": eff_run_id,
        })
        if self.on_execute:
            self.on_execute(self, role, step, brief)

        record = handoff.create_run_record(
            repo_root=self.repo_root,
            slug=self.issue_slug or "test-task",
            run_id=eff_run_id,
            role=role,
            runtime=self.runtime,
            step=step,
        )
        record = handoff.finish_run_record(
            repo_root=self.repo_root,
            slug=self.issue_slug or "test-task",
            run_id=eff_run_id,
            outcome=self.outcome,
            exit_code=self.mock_exit_code,
            changed_files=self.changed_files,
            handoff_note=handoff_note,
        )
        self.last_result = RunResult(
            run_id=eff_run_id,
            outcome=self.outcome,
            exit_code=self.mock_exit_code,
            stdout="mock runner stdout",
            stderr="",
            changed_files=self.changed_files,
            handoff_note=handoff_note,
            record=record,
        )
        return record


class TestRoleConfiguration(unittest.TestCase):
    """Verify loading and precedence of role-to-runtime mapping configurations."""

    def setUp(self) -> None:
        self.repo = hermetic.make_repo_fixture(prefix="along-test-orch-cfg-")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_default_role_configuration(self) -> None:
        cfg = orchestrator.load_role_config(self.repo)
        for role in ("scout", "architect", "implementer", "reviewer"):
            self.assertIn(role, cfg)
            self.assertEqual(cfg[role]["runtime"], "claude-code")

    def test_load_from_yaml_config(self) -> None:
        along_dir = os.path.join(self.repo, ".along")
        os.makedirs(along_dir, exist_ok=True)
        yaml_path = os.path.join(along_dir, "config.yaml")
        yaml_content = (
            "orchestration:\n"
            "  scout:\n"
            "    runtime: opencode\n"
            "    model: ollama/qwen2.5\n"
            "  architect:\n"
            "    runtime: claude-code\n"
            "    model: claude-3-7-sonnet\n"
            "  implementer: codex\n"
            "  reviewer:\n"
            "    runtime: claude-code\n"
        )
        textio.write_text(yaml_path, yaml_content, newline="\n")

        cfg = orchestrator.load_role_config(self.repo)
        self.assertEqual(cfg["scout"]["runtime"], "opencode")
        self.assertEqual(cfg["scout"]["model"], "ollama/qwen2.5")
        self.assertEqual(cfg["architect"]["runtime"], "claude-code")
        self.assertEqual(cfg["architect"]["model"], "claude-3-7-sonnet")
        self.assertEqual(cfg["implementer"]["runtime"], "codex")
        self.assertEqual(cfg["reviewer"]["runtime"], "claude-code")

    def test_load_from_json_config(self) -> None:
        along_dir = os.path.join(self.repo, ".along")
        os.makedirs(along_dir, exist_ok=True)
        json_path = os.path.join(along_dir, "config.json")
        json_content = json.dumps({
            "orchestration": {
                "scout": {"runtime": "antigravity"},
                "architect": {"runtime": "antigravity"},
                "implementer": {"runtime": "generic"},
                "reviewer": {"runtime": "generic"},
            }
        })
        textio.write_text(json_path, json_content, newline="\n")

        cfg = orchestrator.load_role_config(self.repo)
        self.assertEqual(cfg["scout"]["runtime"], "antigravity")
        self.assertEqual(cfg["architect"]["runtime"], "antigravity")
        self.assertEqual(cfg["implementer"]["runtime"], "generic")
        self.assertEqual(cfg["reviewer"]["runtime"], "generic")

    def test_cli_overrides_precedence(self) -> None:
        along_dir = os.path.join(self.repo, ".along")
        os.makedirs(along_dir, exist_ok=True)
        json_path = os.path.join(along_dir, "config.json")
        textio.write_text(json_path, json.dumps({
            "orchestration": {
                "implementer": {"runtime": "generic"},
                "reviewer": {"runtime": "generic"},
            }
        }), newline="\n")

        overrides = {
            "implementer": "claude-code",
            "reviewer": "opencode",
            "model": "claude-3-5-haiku",
            "timeout": 450,
        }
        cfg = orchestrator.load_role_config(self.repo, overrides=overrides)
        self.assertEqual(cfg["implementer"]["runtime"], "claude-code")
        self.assertEqual(cfg["reviewer"]["runtime"], "opencode")
        self.assertEqual(cfg["implementer"]["model"], "claude-3-5-haiku")
        self.assertEqual(cfg["reviewer"]["timeout"], 450)


class TestPhasedExecutionFlow(unittest.TestCase):
    """Verify phased execution lifecycle: Scout -> Architect -> Implementer -> Reviewer."""

    def setUp(self) -> None:
        self.repo = hermetic.make_repo_fixture(prefix="along-test-orch-flow-")
        self.slug = "fixture-sample-task"
        session.init_session(self.repo, self.slug, title="Fixture Sample Task")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_phased_lifecycle_success(self) -> None:
        session_dir = session.get_session_dir(self.repo, self.slug)

        def on_scout(runner, role, step, brief):
            research_path = os.path.join(session_dir, "research.md")
            research_body = (
                "# Research: fixture-sample-task\n\n"
                "## Findings\nTarget files identified in src/auth.py.\n"
            )
            textio.write_text(research_path, research_body, newline="\n")

        def on_architect(runner, role, step, brief):
            plan_path = os.path.join(session_dir, "plan.md")
            plan_body = (
                "# Living Plan: fixture-sample-task\n\n"
                "## Steps\n"
                "- [ ] Step 1: Implement auth token verification\n"
                "- [ ] Step 2: Add test coverage\n"
            )
            textio.write_text(plan_path, plan_body, newline="\n")

        def on_implementer(runner, role, step, brief):
            handoff.write_handoff_note(
                self.repo,
                self.slug,
                done=f"Finished step {step} implementation.",
                remaining="Pending next step.",
            )

        def on_reviewer(runner, role, step, brief):
            handoff.write_review_verdict(
                self.repo,
                self.slug,
                step=step,
                verdict="pass",
                defects=[],
                body=f"Step {step} review audit passed without defects.",
            )

        def custom_runner_factory(runtime, **kwargs):
            role = kwargs.get("extra_args", [])
            # Route behavior by role
            runner = MockRunner(**kwargs)
            return runner

        orch = orchestrator.CrossRuntimeOrchestrator(
            repo_root=self.repo,
            slug=self.slug,
            max_retries=3,
        )

        # 1. Scout Phase
        scout_runner = MockRunner(repo_root=self.repo, issue_slug=self.slug, on_execute=on_scout)
        orch._instantiate_runner = lambda role: scout_runner
        res_scout = orch.run_scout_phase()
        self.assertEqual(res_scout["status"], "done")
        self.assertTrue(os.path.isfile(os.path.join(session_dir, "research.md")))

        # 2. Architect Phase
        arch_runner = MockRunner(repo_root=self.repo, issue_slug=self.slug, on_execute=on_architect)
        orch._instantiate_runner = lambda role: arch_runner
        res_arch = orch.run_architect_phase()
        self.assertEqual(res_arch["status"], "done")

        st = session.load_state(self.repo, self.slug)
        self.assertTrue(st["plan_approved"])
        self.assertEqual(st["phase"], "execution")
        self.assertEqual(st["total_steps"], 2)

        # 3. Step Loop Phase
        def step_runner_factory(role):
            if role == "implementer":
                return MockRunner(
                    repo_root=self.repo,
                    issue_slug=self.slug,
                    changed_files=["src/auth.py"],
                    on_execute=on_implementer,
                )
            elif role == "reviewer":
                return MockRunner(
                    repo_root=self.repo,
                    issue_slug=self.slug,
                    on_execute=on_reviewer,
                )
            return MockRunner(repo_root=self.repo, issue_slug=self.slug)

        orch._instantiate_runner = step_runner_factory
        res_loop = orch.run_step_loop()
        self.assertEqual(res_loop["status"], "completed")

        final_st = session.load_state(self.repo, self.slug)
        self.assertEqual(final_st["status"], "completed")
        self.assertEqual(final_st["current_step"], 2)


class TestReviewVerdictBranchingAndRetryLoop(unittest.TestCase):
    """Verify reviewer verdict parsing, defects feeding, and fix-retry loop."""

    def setUp(self) -> None:
        self.repo = hermetic.make_repo_fixture(prefix="along-test-orch-verdict-")
        self.slug = "fixture-sample-task"
        session.init_session(self.repo, self.slug, title="Fixture Sample Task")
        session.approve_plan(self.repo, self.slug)

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_review_fail_triggers_retry_and_feeds_defects(self) -> None:
        orch = orchestrator.CrossRuntimeOrchestrator(
            repo_root=self.repo,
            slug=self.slug,
            max_retries=3,
        )

        review_attempts = 0
        captured_implementer_briefs = []

        def on_implement(runner, role, step, brief):
            captured_implementer_briefs.append(brief)

        def on_review(runner, role, step, brief):
            nonlocal review_attempts
            review_attempts += 1
            if review_attempts == 1:
                # First attempt: review fails with blocking defect
                handoff.write_review_verdict(
                    self.repo,
                    self.slug,
                    step=step,
                    verdict="fail",
                    defects=[{
                        "severity": "blocking",
                        "description": "Token signature verification is skipped.",
                        "file": "src/auth.py",
                        "line": 42,
                    }],
                )
            else:
                # Second attempt: review passes
                handoff.write_review_verdict(
                    self.repo,
                    self.slug,
                    step=step,
                    verdict="pass",
                    defects=[],
                )

        def runner_factory(role):
            if role == "implementer":
                return MockRunner(repo_root=self.repo, issue_slug=self.slug, on_execute=on_implement)
            return MockRunner(repo_root=self.repo, issue_slug=self.slug, on_execute=on_review)

        orch._instantiate_runner = runner_factory
        res = orch.run_step_loop()

        self.assertEqual(res["status"], "completed")
        self.assertEqual(review_attempts, 2)
        self.assertEqual(len(captured_implementer_briefs), 2)

        # Verify second implementer prompt contained the review defect
        second_brief = captured_implementer_briefs[1]
        self.assertIn("Token signature verification is skipped", second_brief)

    def test_retry_exhaustion_halts_with_failure(self) -> None:
        orch = orchestrator.CrossRuntimeOrchestrator(
            repo_root=self.repo,
            slug=self.slug,
            max_retries=2,
        )

        def on_review(runner, role, step, brief):
            handoff.write_review_verdict(
                self.repo,
                self.slug,
                step=step,
                verdict="fail",
                defects=[{"severity": "blocking", "description": "Persistent syntax error"}],
            )

        def runner_factory(role):
            return MockRunner(repo_root=self.repo, issue_slug=self.slug, on_execute=on_review)

        orch._instantiate_runner = runner_factory
        res = orch.run_step_loop()

        self.assertEqual(res["status"], "failed")
        self.assertIn("Retry limit (2) exhausted", res.get("reason", ""))

        st = session.load_state(self.repo, self.slug)
        self.assertEqual(st["status"], "failed")


class TestNeedsInputAndTimeoutHandling(unittest.TestCase):
    """Verify graceful handling when child processes timeout or request operator input."""

    def setUp(self) -> None:
        self.repo = hermetic.make_repo_fixture(prefix="along-test-orch-needs-input-")
        self.slug = "fixture-sample-task"
        session.init_session(self.repo, self.slug, title="Fixture Sample Task")
        session.approve_plan(self.repo, self.slug)

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_needs_input_halts_step_loop(self) -> None:
        orch = orchestrator.CrossRuntimeOrchestrator(
            repo_root=self.repo,
            slug=self.slug,
        )
        needs_input_runner = MockRunner(
            repo_root=self.repo,
            issue_slug=self.slug,
            outcome="needs-input",
        )
        orch._instantiate_runner = lambda role: needs_input_runner

        res = orch.run_step_loop()
        self.assertEqual(res["status"], "needs-input")

        st = session.load_state(self.repo, self.slug)
        self.assertEqual(st["status"], "needs-input")

    def test_open_question_halts_step_loop(self) -> None:
        orch = orchestrator.CrossRuntimeOrchestrator(
            repo_root=self.repo,
            slug=self.slug,
        )

        def on_implement(runner, role, step, brief):
            handoff.create_question(
                self.repo,
                self.slug,
                question="Should we support RS256 or HS256 tokens?",
                options=["RS256", "HS256"],
            )

        runner = MockRunner(
            repo_root=self.repo,
            issue_slug=self.slug,
            outcome="done",
            on_execute=on_implement,
        )
        orch._instantiate_runner = lambda role: runner

        res = orch.run_step_loop()
        self.assertEqual(res["status"], "needs-input")

    def test_timeout_halts_step_loop(self) -> None:
        orch = orchestrator.CrossRuntimeOrchestrator(
            repo_root=self.repo,
            slug=self.slug,
        )
        timeout_runner = MockRunner(
            repo_root=self.repo,
            issue_slug=self.slug,
            outcome="timeout",
            exit_code=124,
        )
        orch._instantiate_runner = lambda role: timeout_runner

        res = orch.run_step_loop()
        self.assertEqual(res["status"], "timeout")

        st = session.load_state(self.repo, self.slug)
        self.assertEqual(st["status"], "failed")


class TestCliOrchestratorCommands(unittest.TestCase):
    """Verify CLI routing for along orchestrate and along team."""

    def setUp(self) -> None:
        self.repo = hermetic.make_repo_fixture(prefix="along-test-orch-cli-")
        self.slug = "fixture-sample-task"
        session.init_session(self.repo, self.slug, title="Fixture Sample Task")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_orchestrate_dry_run_command(self) -> None:
        code = handle_orchestrate_command(self.repo, [self.slug, "--dry-run", "--json"])
        self.assertEqual(code, 0)

    def test_team_orchestrate_dry_run_command(self) -> None:
        code = handle_team_command(self.repo, ["orchestrate", self.slug, "--dry-run"])
        self.assertEqual(code, 0)

    def test_team_status_command(self) -> None:
        code = handle_team_command(self.repo, ["status", self.slug])
        self.assertEqual(code, 0)

    def test_team_unknown_subcommand(self) -> None:
        code = handle_team_command(self.repo, ["invalid-subcommand"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
