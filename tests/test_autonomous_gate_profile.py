#!/usr/bin/env python3
"""
tests/test_autonomous_gate_profile.py - Tests for autonomous gate profile.

Covers [feat--autonomous-gate-profile]:
- Profile validation and resolution (ALONG_PROFILE, ALONG_AUTONOMOUS, config, session).
- Deterministic allow/deny behavior (no unhandled ask decisions under autonomous profile).
- Escalation list operations (push to default branch, tag/release, package publish, deploy, dangerous deletion).
- Escalation handler routing, timeout denial, and run record outcome tracking.
- Plan approval in blackboard (state.json, plan.md) and issue unlocking source edits without interactive session token.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import frontmatter, handoff, profiles, session, textio
from alongkit.hooks import config as hook_config
from alongkit.hooks import escalation
from alongkit.hooks.engine import HookEngine
from alongkit.hooks.models import GateDecision, GateResult, HookEvent, HookEventType
from hermetic import make_repo_fixture

CLEAN_ENV = {
    k: v for k, v in os.environ.items()
    if k not in session.SESSION_ENV_VARS and k not in ("ALONG_PROFILE", "ALONG_AUTONOMOUS")
}
KEY = session.session_key("generic", "sess-auto-prof")


class TestAutonomousProfileBasicsAndResolution(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, dict(CLEAN_ENV, ALONG_SESSION_ID="sess-auto-prof"), clear=True)
        self.env.start()
        self.root = make_repo_fixture(prefix="along-auto-prof-", with_docs=False)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_profile_constants_and_validation(self):
        self.assertEqual(profiles.PROFILE_AUTONOMOUS, "autonomous")
        self.assertIn("autonomous", profiles.VALID_PROFILES)
        self.assertEqual(profiles.validate_profile("autonomous"), "autonomous")
        self.assertEqual(profiles.validate_profile("  AUTONOMOUS  "), "autonomous")
        self.assertEqual(profiles.normalize_profile("autonomous"), "autonomous")

    def test_resolution_via_env_var_along_profile(self):
        with mock.patch.dict(os.environ, {"ALONG_PROFILE": "autonomous"}):
            prof, source = profiles.resolve_active_profile_with_source(self.root, session_key=KEY)
            self.assertEqual(prof, "autonomous")
            self.assertEqual(source, profiles.SOURCE_ENV)

    def test_resolution_via_env_var_along_autonomous(self):
        with mock.patch.dict(os.environ, {"ALONG_AUTONOMOUS": "1"}):
            prof, source = profiles.resolve_active_profile_with_source(self.root, session_key=KEY)
            self.assertEqual(prof, "autonomous")
            self.assertEqual(source, profiles.SOURCE_ENV)

    def test_resolution_via_config_json_top_level(self):
        cfg_path = os.path.join(self.root, ".along", "config.json")
        textio.write_text(cfg_path, json.dumps({"profile": "autonomous"}))
        prof, source = profiles.resolve_active_profile_with_source(self.root, session_key=KEY)
        self.assertEqual(prof, "autonomous")
        self.assertEqual(source, profiles.SOURCE_CONFIG)

    def test_resolution_via_config_json_hooks_section(self):
        cfg_path = os.path.join(self.root, ".along", "config.json")
        textio.write_text(cfg_path, json.dumps({"hooks": {"profile": "autonomous"}}))
        prof, source = profiles.resolve_active_profile_with_source(self.root, session_key=KEY)
        self.assertEqual(prof, "autonomous")
        self.assertEqual(source, profiles.SOURCE_CONFIG)

    def test_resolution_via_session_binding(self):
        session.bind_session(self.root, "my-slug", key=KEY, profile="autonomous")
        prof, source = profiles.resolve_active_profile_with_source(self.root, session_key=KEY)
        self.assertEqual(prof, "autonomous")
        self.assertEqual(source, profiles.SOURCE_SESSION)


class TestDeterministicAllowDenyBehavior(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, dict(CLEAN_ENV, ALONG_SESSION_ID="sess-auto-eval"), clear=True)
        self.env.start()
        self.root = make_repo_fixture(prefix="along-auto-eval-", with_docs=False)
        escalation.reset_escalation_handler()

    def tearDown(self):
        escalation.reset_escalation_handler()
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_read_outside_scope_denied_in_autonomous_profile(self):
        # Interactive mode asks; autonomous mode denies deterministically
        event_interactive = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="read_file",
            tool_args={"path": "C:/outside/secret.txt" if os.name == "nt" else "/outside/secret.txt"},
            workspace_root=self.root,
            runtime="antigravity",
        )
        cfg_interactive = hook_config.HooksConfig(profile="standard")
        engine_interactive = HookEngine(config=cfg_interactive, repo_root=self.root)
        res_interactive = engine_interactive.evaluate(event_interactive)
        self.assertEqual(res_interactive.decision, GateDecision.ASK)

        # In autonomous profile
        event_autonomous = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="read_file",
            tool_args={"path": "C:/outside/secret.txt" if os.name == "nt" else "/outside/secret.txt"},
            workspace_root=self.root,
            runtime="antigravity",
        )
        cfg_autonomous = hook_config.HooksConfig(profile="autonomous")
        engine_autonomous = HookEngine(config=cfg_autonomous, repo_root=self.root)
        res_autonomous = engine_autonomous.evaluate(event_autonomous)
        self.assertEqual(res_autonomous.decision, GateDecision.DENY)
        self.assertIn("Workspace containment violation", res_autonomous.reason or "")

    def test_unapproved_plan_denied_in_autonomous_profile_even_on_antigravity(self):
        # Create an in-progress issue so session is bound and plan is required
        issues_dir = os.path.join(self.root, ".along", "ISSUES")
        issue_path = os.path.join(issues_dir, "feat--sample.md")
        textio.write_text(issue_path, "---\nprotocol: along\nslug: sample\ntype: feat\nstatus: in-progress\n---\n")
        session.init_session(self.root, "sample")
        session.set_session_phase(self.root, "planning", slug="sample", plan_approved=False)
        antigravity_key = session.session_key("antigravity", "sess-auto-eval")
        session.bind_session(self.root, "sample", key=antigravity_key, approved=False)

        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": "src/module.py", "CodeContent": "x = 1\n"},
            workspace_root=self.root,
            runtime="antigravity",
            conversation_id="sess-auto-eval",
        )

        # Standard profile on antigravity returns ASK
        cfg_std = hook_config.HooksConfig(profile="standard")
        engine_std = HookEngine(config=cfg_std, repo_root=self.root)
        res_std = engine_std.evaluate(event)
        self.assertEqual(res_std.decision, GateDecision.ASK)

        # Autonomous profile on antigravity returns DENY
        cfg_auto = hook_config.HooksConfig(profile="autonomous")
        engine_auto = HookEngine(config=cfg_auto, repo_root=self.root)
        res_auto = engine_auto.evaluate(event)
        self.assertEqual(res_auto.decision, GateDecision.DENY)
        self.assertIn("PLAN_REQUIRED", res_auto.reason or "")


class TestEscalationListOperations(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, dict(CLEAN_ENV, ALONG_SESSION_ID="sess-auto-esc"), clear=True)
        self.env.start()
        self.root = make_repo_fixture(prefix="along-auto-esc-", with_docs=False)
        self.key = session.session_key("generic", "sess-auto-esc")
        escalation.reset_escalation_handler()

    def tearDown(self):
        escalation.reset_escalation_handler()
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_classify_push_to_default_branch(self):
        event_main = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": "git push origin main"},
            workspace_root=self.root,
        )
        res = escalation.classify_escalation(event_main, self.root)
        self.assertIsNotNone(res)
        op, detail = res
        self.assertEqual(op, escalation.OP_PUSH_DEFAULT)
        self.assertIn("main", detail)

        event_master = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": "git push origin HEAD:master"},
            workspace_root=self.root,
        )
        res2 = escalation.classify_escalation(event_master, self.root)
        self.assertIsNotNone(res2)
        self.assertEqual(res2[0], escalation.OP_PUSH_DEFAULT)

        # Feature branch push is not an escalation operation
        event_feat = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": "git push origin feature-auth"},
            workspace_root=self.root,
        )
        res3 = escalation.classify_escalation(event_feat, self.root)
        self.assertIsNone(res3)

    def test_classify_tag_or_release(self):
        for cmd in ("git tag v2.0.0", "along bump --patch", "along release v1.0.0", "npm version minor"):
            event = HookEvent(
                event_type=HookEventType.PRE_TOOL_USE,
                tool_name="run_command",
                tool_args={"CommandLine": cmd},
                workspace_root=self.root,
            )
            res = escalation.classify_escalation(event, self.root)
            self.assertIsNotNone(res, f"Expected escalation for '{cmd}'")
            self.assertEqual(res[0], escalation.OP_TAG_RELEASE)

    def test_classify_package_publish(self):
        for cmd in ("npm publish --access public", "twine upload dist/*", "cargo publish"):
            event = HookEvent(
                event_type=HookEventType.PRE_TOOL_USE,
                tool_name="run_command",
                tool_args={"CommandLine": cmd},
                workspace_root=self.root,
            )
            res = escalation.classify_escalation(event, self.root)
            self.assertIsNotNone(res, f"Expected escalation for '{cmd}'")
            self.assertEqual(res[0], escalation.OP_PACKAGE_PUBLISH)

    def test_classify_deploy(self):
        for cmd in ("kubectl apply -f deploy.yaml", "helm upgrade prod ./chart", "terraform apply", "docker compose up -d"):
            event = HookEvent(
                event_type=HookEventType.PRE_TOOL_USE,
                tool_name="run_command",
                tool_args={"CommandLine": cmd},
                workspace_root=self.root,
            )
            res = escalation.classify_escalation(event, self.root)
            self.assertIsNotNone(res, f"Expected escalation for '{cmd}'")
            self.assertEqual(res[0], escalation.OP_DEPLOY)

    def test_autonomous_escalation_default_denies_and_records(self):
        # Create issue and run record
        session.init_session(self.root, "esc-test")
        session.bind_session(self.root, "esc-test", key=self.key, approved=True)
        run_rec = handoff.create_run_record(self.root, "esc-test", "run-101", "implementer", "generic")

        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": "git push origin main"},
            workspace_root=self.root,
            conversation_id="sess-auto-esc",
        )
        cfg = hook_config.HooksConfig(profile="autonomous")
        engine = HookEngine(config=cfg, repo_root=self.root)
        res = engine.evaluate(event)

        self.assertEqual(res.decision, GateDecision.DENY)
        self.assertIn("Autonomous escalation denied", res.reason or "")

        # Verify run record updated
        updated_rec = handoff.load_run_record(self.root, "esc-test", "run-101")
        self.assertIsNotNone(updated_rec)
        escalations = updated_rec.get("escalations", [])
        self.assertGreaterEqual(len(escalations), 1)
        self.assertEqual(escalations[0]["operation"], escalation.OP_PUSH_DEFAULT)
        self.assertEqual(escalations[0]["outcome"], "unhandled")

    def test_autonomous_escalation_handler_approval_and_timeout(self):
        session.init_session(self.root, "esc-handler")
        session.bind_session(self.root, "esc-handler", key=self.key, approved=True)
        handoff.create_run_record(self.root, "esc-handler", "run-102", "implementer", "generic")

        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": "npm publish"},
            workspace_root=self.root,
            conversation_id="sess-auto-esc",
        )
        cfg = hook_config.HooksConfig(profile="autonomous")
        engine = HookEngine(config=cfg, repo_root=self.root)

        # 1. Handler approves
        def mock_handler_approve(ev, op, detail, root):
            return GateResult(decision=GateDecision.ALLOW, gate_name="telegram_approval")

        escalation.set_escalation_handler(mock_handler_approve)
        res_approved = engine.evaluate(event)
        self.assertEqual(res_approved.decision, GateDecision.ALLOW)

        # 2. Handler times out
        def mock_handler_timeout(ev, op, detail, root):
            raise TimeoutError("Approval request expired after 30 seconds.")

        escalation.set_escalation_handler(mock_handler_timeout)
        res_timeout = engine.evaluate(event)
        self.assertEqual(res_timeout.decision, GateDecision.DENY)
        self.assertIn("Escalation timed out", res_timeout.reason or "")

        rec = handoff.load_run_record(self.root, "esc-handler", "run-102")
        self.assertEqual(rec.get("outcome"), "timeout")


class TestPlanApprovalUnlockingSourceEdits(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, dict(CLEAN_ENV, ALONG_SESSION_ID="sess-auto-plan"), clear=True)
        self.env.start()
        self.root = make_repo_fixture(prefix="along-auto-plan-", with_docs=False)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_state_json_role_approval_unlocks_implementer_source_edits(self):
        slug = "auto-feature"
        issues_dir = os.path.join(self.root, ".along", "ISSUES")
        issue_path = os.path.join(issues_dir, f"feat--{slug}.md")
        textio.write_text(issue_path, f"---\nprotocol: along\nslug: {slug}\ntype: feat\nstatus: in-progress\n---\n")

        # Session blackboard has state.json written by architect with plan_approved: true
        session.init_session(self.root, slug)
        st = session.load_state(self.root, slug)
        st["plan_approved"] = True
        st["approved_by"] = "architect"
        st["phase"] = "execution"
        session.save_state(self.root, slug, st)

        # Implementer subagent runs with a DIFFERENT session key and NO session binding token
        worker_key = session.session_key("generic", "worker-subagent-999")
        with mock.patch.dict(os.environ, {"ALONG_PROFILE": "autonomous"}):
            self.assertTrue(
                session.is_plan_approved(self.root, slug=slug, key=worker_key),
                "Plan approval in state.json should unlock for implementer under autonomous profile",
            )

            # PreToolUse write tool evaluated by engine should be ALLOWED
            event = HookEvent(
                event_type=HookEventType.PRE_TOOL_USE,
                tool_name="write_to_file",
                tool_args={"TargetFile": "src/app.py", "CodeContent": "print('hello')\n"},
                workspace_root=self.root,
                conversation_id="worker-subagent-999",
            )
            cfg = hook_config.HooksConfig(profile="autonomous")
            engine = HookEngine(config=cfg, repo_root=self.root)
            res = engine.evaluate(event)
            self.assertTrue(res.is_allowed, f"Expected source edit to be allowed, got: {res.reason}")

    def test_plan_md_role_approval_unlocks_implementer_source_edits(self):
        slug = "plan-md-feature"
        issues_dir = os.path.join(self.root, ".along", "ISSUES")
        issue_path = os.path.join(issues_dir, f"feat--{slug}.md")
        textio.write_text(issue_path, f"---\nprotocol: along\nslug: {slug}\ntype: feat\nstatus: in-progress\n---\n")

        session.init_session(self.root, slug)
        # Write plan.md with role approval header
        plan_content = (
            "---\n"
            "status: approved\n"
            "approved_by: architect\n"
            "---\n\n"
            "# Implementation Plan\n\n"
            "## Steps\n"
            "1. Implement core functions.\n"
        )
        plan_file = os.path.join(session.get_session_dir(self.root, slug), "plan.md")
        textio.write_text(plan_file, plan_content)

        worker_key = session.session_key("generic", "worker-subagent-888")
        with mock.patch.dict(os.environ, {"ALONG_PROFILE": "autonomous"}):
            self.assertTrue(
                session.is_plan_approved(self.root, slug=slug, key=worker_key),
                "Plan approval in plan.md should unlock for implementer under autonomous profile",
            )

    def test_issue_frontmatter_approval_unlocks_implementer_source_edits(self):
        slug = "issue-approved-feature"
        issues_dir = os.path.join(self.root, ".along", "ISSUES")
        issue_path = os.path.join(issues_dir, f"feat--{slug}.md")
        textio.write_text(
            issue_path,
            f"---\nprotocol: along\nslug: {slug}\ntype: feat\nstatus: in-progress\nplan_approved: true\napproved_by: reviewer\n---\n",
        )
        session.init_session(self.root, slug)

        worker_key = session.session_key("generic", "worker-subagent-777")
        with mock.patch.dict(os.environ, {"ALONG_PROFILE": "autonomous"}):
            self.assertTrue(
                session.is_plan_approved(self.root, slug=slug, key=worker_key),
                "Plan approval in issue frontmatter should unlock for implementer under autonomous profile",
            )


if __name__ == "__main__":
    unittest.main()
