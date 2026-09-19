#!/usr/bin/env python3
"""
tests/test_inquiry_gate.py - Hermetic tests for Inquiry Read-Only Mode and Plan Approval Gate.

Verifies:
1. Safe read tools and inspection commands are permitted in all session phases.
2. Brain artifacts, session blackboards, and planning documents are writable in inquiry phase.
3. Repository file mutations prompt interactive ASK in Antigravity and DENY (code 2) in other runtimes.
4. Approved plans transition session phase and unlock mutating operations.
5. Hardened issue anchor prevents stale issue hijacking in inquiry mode.

All tests operate in hermetic temporary directories (tempfile.mkdtemp) without modifying repository state.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import session

from alongkit.hooks import (
    GateDecision,
    GateResult,
    HookEngine,
    HookEvent,
    HookEventType,
    HooksConfig,
)
from alongkit.hooks.predicates import (
    check_active_issue,
    check_mutation_authorization,
)


class TestInquiryGatePredicate(unittest.TestCase):
    """Hermetic unit tests for check_mutation_authorization predicate."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="along-inquiry-test-")
        os.makedirs(os.path.join(self.temp_dir, ".along", "ISSUES"), exist_ok=True)
        os.makedirs(os.path.join(self.temp_dir, ".along", ".session"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_safe_read_tools_allowed_in_inquiry_phase(self):
        session.set_session_phase(self.temp_dir, "inquiry", plan_approved=False)
        for tool in ("view_file", "grep_search", "find_by_name", "list_dir", "read_url_content"):
            event = HookEvent(
                event_type=HookEventType.PRE_TOOL_USE,
                tool_name=tool,
                tool_args={"path": "src/main.py"},
                workspace_root=self.temp_dir,
                runtime="generic",
            )
            result = check_mutation_authorization(event, self.temp_dir)
            self.assertIsNone(result, f"Expected {tool} to be allowed in inquiry phase")

    def test_safe_read_commands_allowed_in_inquiry_phase(self):
        session.set_session_phase(self.temp_dir, "inquiry", plan_approved=False)
        for cmd in ("git status", "git diff HEAD~1", "git log -n 5", "along test", "pytest -q", "python -m unittest"):
            event = HookEvent(
                event_type=HookEventType.PRE_TOOL_USE,
                tool_name="run_command",
                tool_args={"CommandLine": cmd},
                workspace_root=self.temp_dir,
                runtime="generic",
            )
            result = check_mutation_authorization(event, self.temp_dir)
            self.assertIsNone(result, f"Expected '{cmd}' to be allowed in inquiry phase")

    def test_brain_and_planning_artifacts_allowed_in_inquiry_phase(self):
        session.set_session_phase(self.temp_dir, "inquiry", plan_approved=False)
        allowed_targets = [
            os.path.join(self.temp_dir, ".along", ".session", "my-task", "plan.md"),
            os.path.join(self.temp_dir, ".along", ".session", "state.json"),
            os.path.join(self.temp_dir, "implementation_plan.md"),
            os.path.join(self.temp_dir, "walkthrough.md"),
            # Target outside repository root (e.g. brain artifacts)
            os.path.join(tempfile.gettempdir(), "brain", "artifact.md"),
        ]
        for target in allowed_targets:
            event = HookEvent(
                event_type=HookEventType.PRE_TOOL_USE,
                tool_name="write_to_file",
                tool_args={"TargetFile": target, "CodeContent": "# Plan\n"},
                workspace_root=self.temp_dir,
                runtime="generic",
            )
            result = check_mutation_authorization(event, self.temp_dir)
            self.assertIsNone(result, f"Expected '{target}' to be writable in inquiry phase")

    def test_repository_source_mutation_prompts_ask_in_antigravity(self):
        session.set_session_phase(self.temp_dir, "inquiry", plan_approved=False)
        target = os.path.join(self.temp_dir, "src", "engine.py")
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": target, "CodeContent": "x = 1\n"},
            workspace_root=self.temp_dir,
            runtime="antigravity",
        )
        result = check_mutation_authorization(event, self.temp_dir)
        self.assertIsInstance(result, GateResult)
        self.assertEqual(result.decision, GateDecision.ASK)
        self.assertIn("require-plan-approval", result.reason or "")

    def test_repository_source_mutation_denied_in_claude_and_codex(self):
        session.set_session_phase(self.temp_dir, "inquiry", plan_approved=False)
        target = os.path.join(self.temp_dir, "src", "engine.py")
        for r_name in ("claude", "codex", "generic"):
            event = HookEvent(
                event_type=HookEventType.PRE_TOOL_USE,
                tool_name="write_to_file",
                tool_args={"TargetFile": target, "CodeContent": "x = 1\n"},
                workspace_root=self.temp_dir,
                runtime=r_name,
            )
            result = check_mutation_authorization(event, self.temp_dir)
            self.assertIsInstance(result, str)
            self.assertIn("require-plan-approval", result)

    def test_mutating_shell_command_blocked_in_inquiry_phase(self):
        session.set_session_phase(self.temp_dir, "inquiry", plan_approved=False)
        cmd = "npm run build"
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": cmd},
            workspace_root=self.temp_dir,
            runtime="claude",
        )
        result = check_mutation_authorization(event, self.temp_dir)
        self.assertIsInstance(result, str)
        self.assertIn("require-plan-approval", result)

    def test_plan_approval_unlocks_mutations(self):
        session.set_session_phase(self.temp_dir, "inquiry", plan_approved=False)
        target = os.path.join(self.temp_dir, "src", "engine.py")
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": target, "CodeContent": "x = 1\n"},
            workspace_root=self.temp_dir,
            runtime="claude",
        )
        # Blocked before approval
        self.assertIsNotNone(check_mutation_authorization(event, self.temp_dir))

        # Approve plan
        session.approve_plan(self.temp_dir)

        # Allowed after approval
        self.assertIsNone(check_mutation_authorization(event, self.temp_dir))


class TestHookEngineInquiryIntegration(unittest.TestCase):
    """End-to-end integration tests through HookEngine evaluation pipeline."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="along-engine-inquiry-")
        os.makedirs(os.path.join(self.temp_dir, ".along", "ISSUES"), exist_ok=True)
        os.makedirs(os.path.join(self.temp_dir, ".along", ".session"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_engine_routes_ask_for_antigravity_and_deny_for_claude(self):
        # Create an in-progress issue so require_active_issue passes
        slug = "feature-in-progress"
        with open(os.path.join(self.temp_dir, ".along", "ISSUES", f"feat--{slug}.md"), "w", encoding="utf-8") as f:
            f.write("---\nstatus: in-progress\n---\n# Feature\n")

        session.init_session(self.temp_dir, slug, title="Feature")
        session.set_session_phase(self.temp_dir, "inquiry", slug=slug, plan_approved=False)

        config = HooksConfig(mode="enforce")
        engine = HookEngine(config=config, repo_root=self.temp_dir)

        target = os.path.join(self.temp_dir, "src", "core.py")

        # Antigravity receives ASK
        ag_event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": target, "CodeContent": "val = 42\n"},
            workspace_root=self.temp_dir,
            runtime="antigravity",
        )
        ag_res = engine.evaluate(ag_event, repo_root=self.temp_dir)
        self.assertEqual(ag_res.decision, GateDecision.ASK)

        # Claude Code receives DENY with exit code 2
        claude_event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": target, "CodeContent": "val = 42\n"},
            workspace_root=self.temp_dir,
            runtime="claude",
        )
        claude_res = engine.evaluate(claude_event, repo_root=self.temp_dir)
        self.assertEqual(claude_res.decision, GateDecision.DENY)
        self.assertEqual(claude_res.exit_code, 2)



class TestHardenedIssueAnchor(unittest.TestCase):
    """Hermetic tests for session-bound check_active_issue."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="along-anchor-test-")
        self.issues_dir = os.path.join(self.temp_dir, ".along", "ISSUES")
        os.makedirs(self.issues_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_inquiry_phase_without_bound_session_blocks_stale_issue_reuse(self):
        # Create an in-progress issue from earlier
        stale_issue = os.path.join(self.issues_dir, "feat--stale-task.md")
        with open(stale_issue, "w", encoding="utf-8") as f:
            f.write("---\nstatus: in-progress\n---\n# Stale Task\n")

        # In inquiry mode with no bound session, mutating source files must be blocked
        session.set_session_phase(self.temp_dir, "inquiry", plan_approved=False)
        target = os.path.join(self.temp_dir, "src", "app.py")
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": target, "CodeContent": "print(1)\n"},
            workspace_root=self.temp_dir,
            runtime="generic",
        )
        violation = check_active_issue(event, self.temp_dir)
        self.assertIsNotNone(violation)
        self.assertIn("require-active-issue", violation)

    def test_session_bound_issue_allows_modifications(self):
        # Create active session bound to active issue
        slug = "my-active-feature"
        issue_file = os.path.join(self.issues_dir, f"feat--{slug}.md")
        with open(issue_file, "w", encoding="utf-8") as f:
            f.write("---\nstatus: in-progress\n---\n# Active Feature\n")

        session.init_session(self.temp_dir, slug, title="Active Feature")
        session.approve_plan(self.temp_dir, slug)

        target = os.path.join(self.temp_dir, "src", "app.py")
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": target, "CodeContent": "print(1)\n"},
            workspace_root=self.temp_dir,
            runtime="generic",
        )
        violation = check_active_issue(event, self.temp_dir)
        self.assertIsNone(violation)


if __name__ == "__main__":
    unittest.main()
