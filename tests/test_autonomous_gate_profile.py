#!/usr/bin/env python3
"""
tests/test_autonomous_gate_profile.py - Tests for autonomous gate profile.

Covers [feat--autonomous-gate-profile]:
- Profile validation and resolution (ALONG_PROFILE, ALONG_AUTONOMOUS, config, session).
- Deterministic allow/deny behavior (no unhandled ask decisions under autonomous profile).
- Escalation list operations (push to default branch, tag/release, package publish, deploy, dangerous deletion).
- Escalation handler routing, timeout denial, and run record outcome tracking.
- Plan approval recorded by `session.approve_plan` unlocking a runner's worker (ALONG_ISSUE_SLUG)
  without an interactive session token; agent-writable markers (plan.md, issue front-matter,
  state.json role keys, file-tool writes to approval records) never approve
  [bug--plan-approval-self-approval-bypass].
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
        self.assertEqual(prof, profiles.DEFAULT_PROFILE)
        self.assertEqual(source, profiles.SOURCE_DEFAULT)

    def test_resolution_via_config_json_hooks_section(self):
        cfg_path = os.path.join(self.root, ".along", "config.json")
        textio.write_text(cfg_path, json.dumps({"hooks": {"profile": "autonomous"}}))
        prof, source = profiles.resolve_active_profile_with_source(self.root, session_key=KEY)
        self.assertEqual(prof, profiles.DEFAULT_PROFILE)
        self.assertEqual(source, profiles.SOURCE_DEFAULT)

    def test_resolution_via_session_binding(self):
        session.bind_session(self.root, "my-slug", key=KEY, profile="autonomous")
        prof, source = profiles.resolve_active_profile_with_source(self.root, session_key=KEY)
        self.assertEqual(prof, profiles.DEFAULT_PROFILE)
        self.assertEqual(source, profiles.SOURCE_DEFAULT)

    def test_payload_profile_autonomous_ignored(self):
        from alongkit.hooks import containment
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="view_file",
            tool_args={"file_path": "README.md"},
            workspace_root=self.root,
            raw_payload={"profile": "autonomous"},
        )
        self.assertFalse(containment.is_autonomous(event, repo_root=self.root))

    def test_along_start_profile_autonomous_exits_2(self):
        from alongkit.commands import lifecycle
        issues_dir = os.path.join(self.root, ".along", "ISSUES")
        textio.write_text(os.path.join(issues_dir, "task--test-start.md"),
                          "---\nprotocol: along\nslug: test-start\ntype: task\nstatus: open\n---\n")
        with self.assertRaises((SystemExit, Exception)) as ctx:
            lifecycle.handle_start_command(self.root, ["test-start", "--profile", "autonomous"])
        code = getattr(ctx.exception, "code", getattr(ctx.exception, "exit_code", None))
        self.assertEqual(code, 2)


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
        with mock.patch.dict(os.environ, {"ALONG_PROFILE": "autonomous"}):
            cfg_auto = hook_config.HooksConfig(profile="autonomous")
            engine_auto = HookEngine(config=cfg_auto, repo_root=self.root)
            res_auto = engine_auto.evaluate(event)
            self.assertEqual(res_auto.decision, GateDecision.DENY)
            self.assertIn("PLAN_REQUIRED", res_auto.reason or "")

    def test_permission_mode_turns_ask_to_deny_but_does_not_skip_phase_check(self):
        issues_dir = os.path.join(self.root, ".along", "ISSUES")
        issue_path = os.path.join(issues_dir, "feat--pm-test.md")
        textio.write_text(issue_path, "---\nprotocol: along\nslug: pm-test\ntype: feat\nstatus: in-progress\n---\n")
        session.init_session(self.root, "pm-test")
        session.set_session_phase(self.root, "planning", slug="pm-test", plan_approved=True)
        key = session.session_key("antigravity", "sess-pm-eval")
        session.bind_session(self.root, "pm-test", key=key, approved=True)

        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": "src/module.py", "CodeContent": "x = 1\n"},
            workspace_root=self.root,
            runtime="antigravity",
            conversation_id="sess-pm-eval",
            raw_payload={"permission_mode": "bypassPermissions"},
        )
        engine = HookEngine(config=hook_config.HooksConfig(profile="standard"), repo_root=self.root)
        res = engine.evaluate(event)
        self.assertEqual(res.decision, GateDecision.DENY)
        self.assertIn("PLAN_REQUIRED", res.reason or "")

    def test_review_phase_blocks_source_write_in_standard_profile(self):
        """Plan approval in non-edit phase (e.g. review) does not unlock source writes."""
        self.assertTrue(set(session.EDIT_PHASES).issubset(set(session.SESSION_PHASES)))

        issues_dir = os.path.join(self.root, ".along", "ISSUES")
        issue_path = os.path.join(issues_dir, "feat--phase-test.md")
        textio.write_text(issue_path, "---\nprotocol: along\nslug: phase-test\ntype: feat\nstatus: in-progress\n---\n")
        session.init_session(self.root, "phase-test")
        session.approve_plan(self.root, "phase-test")

        # Mutate phase to 'review' via save_state
        state = session.load_state(self.root, "phase-test")
        state["phase"] = "review"
        session.save_state(self.root, "phase-test", state)

        key = session.session_key("generic", "sess-phase-eval")
        session.bind_session(self.root, "phase-test", key=key, approved=True)

        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": "src/module.py", "CodeContent": "x = 1\n"},
            workspace_root=self.root,
            runtime="generic",
            conversation_id="sess-phase-eval",
            raw_payload={},
        )
        engine = HookEngine(config=hook_config.HooksConfig(profile="standard"), repo_root=self.root)
        res = engine.evaluate(event)
        self.assertEqual(res.decision, GateDecision.DENY)
        self.assertIn("require-plan-approval", (res.reason or "").lower())


class TestEscalationListOperations(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(
            os.environ,
            dict(CLEAN_ENV, ALONG_SESSION_ID="sess-auto-esc", ALONG_PROFILE="autonomous"),
            clear=True,
        )
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

        for cmd in ("git push origin +main", "git push origin HEAD:main", "git push origin +refs/heads/main", "git push origin master"):
            ev = HookEvent(
                event_type=HookEventType.PRE_TOOL_USE,
                tool_name="run_command",
                tool_args={"CommandLine": cmd},
                workspace_root=self.root,
            )
            res = escalation.classify_escalation(ev, self.root)
            self.assertIsNotNone(res, f"Expected push escalation for '{cmd}'")
            self.assertEqual(res[0], escalation.OP_PUSH_DEFAULT)

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
        for cmd in (
            "git tag v2.0.0",
            "git tag -a v1.0 -m release",
            "along bump --patch",
            "along release v1.0.0",
            "npm version minor",
            "python scripts/along_exec.py version-bump",
            "gh release create v1",
            "git push --tags",
            "git push origin refs/tags/v1.0",
            "git push origin v1.0",
        ):
            event = HookEvent(
                event_type=HookEventType.PRE_TOOL_USE,
                tool_name="run_command",
                tool_args={"CommandLine": cmd},
                workspace_root=self.root,
            )
            res = escalation.classify_escalation(event, self.root)
            self.assertIsNotNone(res, f"Expected escalation for '{cmd}'")
            self.assertEqual(res[0], escalation.OP_TAG_RELEASE)

        for cmd in ("git tag -l", "git tag --list 'v*'", "git tag --contains HEAD", "git tag"):
            event = HookEvent(
                event_type=HookEventType.PRE_TOOL_USE,
                tool_name="run_command",
                tool_args={"CommandLine": cmd},
                workspace_root=self.root,
            )
            res = escalation.classify_escalation(event, self.root)
            self.assertIsNone(res, f"Tag listing command '{cmd}' must not be an escalation")

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

    def test_containment_deny_stays_deny_even_when_escalation_handler_allows(self):
        def mock_handler_approve(ev, op, detail, root):
            return GateResult(decision=GateDecision.ALLOW, gate_name="telegram_approval")

        escalation.set_escalation_handler(mock_handler_approve)
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": "git push origin main", "Cwd": os.path.expanduser("~/.ssh")},
            workspace_root=self.root,
            conversation_id="sess-auto-esc",
        )
        cfg = hook_config.HooksConfig(profile="autonomous")
        engine = HookEngine(config=cfg, repo_root=self.root)
        res = engine.evaluate(event)
        self.assertFalse(res.is_allowed, "Containment denial must not be overridden by escalation handler")
        self.assertIn("containment", (res.reason or "").lower())

    def test_post_tool_use_never_evaluates_or_records_escalation(self):
        session.init_session(self.root, "esc-post")
        session.bind_session(self.root, "esc-post", key=self.key, approved=True)
        handoff.create_run_record(self.root, "esc-post", "run-post", "implementer", "generic")

        event = HookEvent(
            event_type=HookEventType.POST_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": "git push origin main"},
            workspace_root=self.root,
            conversation_id="sess-auto-esc",
        )
        cfg = hook_config.HooksConfig(profile="autonomous")
        engine = HookEngine(config=cfg, repo_root=self.root)
        res = engine.evaluate(event)
        self.assertTrue(res.is_allowed)

        rec = handoff.load_run_record(self.root, "esc-post", "run-post")
        self.assertEqual(len(rec.get("escalations", [])), 0)


class TestPlanApprovalUnlockingSourceEdits(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, dict(CLEAN_ENV, ALONG_SESSION_ID="sess-auto-plan"), clear=True)
        self.env.start()
        self.root = make_repo_fixture(prefix="along-auto-plan-", with_docs=False)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def _issue(self, slug: str, extra: str = "") -> None:
        issue_path = os.path.join(self.root, ".along", "ISSUES", f"feat--{slug}.md")
        textio.write_text(issue_path, f"---\nprotocol: along\nslug: {slug}\ntype: feat\nstatus: in-progress\n{extra}---\n")

    def _write_event(self, target: str, conversation_id: str) -> HookEvent:
        return HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": target, "CodeContent": "{}\n"},
            workspace_root=self.root,
            conversation_id=conversation_id,
        )

    def test_state_json_role_approval_unlocks_implementer_source_edits(self):
        slug = "auto-feature"
        self._issue(slug)

        # The orchestrator approved the plan through session.approve_plan
        session.init_session(self.root, slug)
        session.approve_plan(self.root, slug=slug)

        # Implementer subagent runs with a DIFFERENT session key and NO session binding token;
        # the runner hands it the slug through ALONG_ISSUE_SLUG (runner/base.py).
        worker_key = session.session_key("generic", "worker-subagent-999")
        with mock.patch.dict(os.environ, {"ALONG_PROFILE": "autonomous", "ALONG_ISSUE_SLUG": slug}):
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

    def test_plan_md_role_approval_does_not_approve(self):
        slug = "plan-md-feature"
        self._issue(slug)

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
        for env in ({"ALONG_ISSUE_SLUG": slug}, {"ALONG_PROFILE": "autonomous", "ALONG_ISSUE_SLUG": slug}):
            with self.subTest(env=env), mock.patch.dict(os.environ, env):
                self.assertFalse(
                    session.is_plan_approved(self.root, slug=slug, key=worker_key),
                    "Approval text an agent writes into plan.md must not approve the plan",
                )

    def test_issue_frontmatter_approval_does_not_approve(self):
        slug = "issue-approved-feature"
        self._issue(slug, "plan_approved: true\napproved_by: reviewer\nplan_approval:\n  approved: true\n")
        session.init_session(self.root, slug)

        worker_key = session.session_key("generic", "worker-subagent-777")
        for env in ({"ALONG_ISSUE_SLUG": slug}, {"ALONG_PROFILE": "autonomous", "ALONG_ISSUE_SLUG": slug}):
            with self.subTest(env=env), mock.patch.dict(os.environ, env):
                self.assertFalse(
                    session.is_plan_approved(self.root, slug=slug, key=worker_key),
                    "Approval markers in the issue front-matter must not approve the plan",
                )

    def test_state_json_role_keys_without_plan_approved_do_not_approve(self):
        slug = "role-keys-feature"
        self._issue(slug)
        session.init_session(self.root, slug)
        st = session.load_state(self.root, slug)
        st["approved_by"] = "architect"
        st["plan_approval"] = {"approved": True}
        session.save_state(self.root, slug, st)

        worker_key = session.session_key("generic", "worker-subagent-666")
        for env in ({"ALONG_ISSUE_SLUG": slug}, {"ALONG_PROFILE": "autonomous", "ALONG_ISSUE_SLUG": slug}):
            with self.subTest(env=env), mock.patch.dict(os.environ, env):
                self.assertFalse(session.is_plan_approved(self.root, slug=slug, key=worker_key))

    def test_autonomous_approval_requires_session_ownership(self):
        slug = "owned-feature"
        self._issue(slug)
        session.init_session(self.root, slug)
        session.approve_plan(self.root, slug=slug)

        worker_key = session.session_key("generic", "worker-subagent-555")
        for env in ({"ALONG_PROFILE": "autonomous"},
                    {"ALONG_PROFILE": "autonomous", "ALONG_ISSUE_SLUG": "other-feature"}):
            with self.subTest(env=env), mock.patch.dict(os.environ, env):
                self.assertFalse(
                    session.is_plan_approved(self.root, slug=slug, key=worker_key),
                    "A session that does not own the slug must not inherit its blackboard approval",
                )

    def test_issue_frontmatter_marker_does_not_unlock_source_edit_in_standard_profile(self):
        slug = "self-approved-feature"
        self._issue(slug, "plan_approved: true\n")
        key = session.session_key("generic", "sess-self-approve")
        session.init_session(self.root, slug)
        session.bind_session(self.root, slug, key=key)
        # The phase alone (no plan_approved) is what an agent could also have written
        st = session.load_state(self.root, slug)
        st["phase"] = "execution"
        session.save_state(self.root, slug, st)

        engine = HookEngine(config=hook_config.HooksConfig(profile="standard"), repo_root=self.root)
        res = engine.evaluate(self._write_event("src/app.py", "sess-self-approve"))
        self.assertFalse(res.is_allowed, "An agent-written front-matter marker must not approve the plan")
        self.assertIn("require-plan-approval", res.reason or "")

    def test_file_tool_writes_to_approval_records_are_denied(self):
        slug = "records-feature"
        self._issue(slug)
        session.init_session(self.root, slug)
        bound_key = session.session_key("generic", "sess-records")
        session.bind_session(self.root, slug, key=bound_key)

        engine = HookEngine(config=hook_config.HooksConfig(profile="standard"), repo_root=self.root)
        targets = (
            f".along/.session/bindings/{bound_key}.json",
            f".along/.session/{slug}/state.json",
        )
        for conversation_id in ("sess-records", "sess-unbound"):
            for target in targets:
                with self.subTest(session=conversation_id, target=target):
                    res = engine.evaluate(self._write_event(target, conversation_id))
                    self.assertFalse(res.is_allowed, f"Write to approval record '{target}' must be denied")
                    self.assertIn("approval record", res.reason or "")

        # Planning artifacts stay writable
        for target in (f".along/.session/{slug}/plan.md", f".along/ISSUES/feat--{slug}.md"):
            with self.subTest(target=target):
                res = engine.evaluate(self._write_event(target, "sess-records"))
                self.assertTrue(res.is_allowed, f"Expected '{target}' to stay writable, got: {res.reason}")


class TestApprovalRecordShellGuardAndRevocation(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, dict(CLEAN_ENV, ALONG_SESSION_ID="sess-shell-guard"), clear=True)
        self.env.start()
        self.root = make_repo_fixture(prefix="along-shell-guard-", with_docs=False)
        self.key = session.session_key("generic", "sess-shell-guard")

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def _shell_event(self, cmd: str, conv_id: str = "sess-shell-guard") -> HookEvent:
        return HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": cmd},
            workspace_root=self.root,
            conversation_id=conv_id,
        )

    def test_shell_writes_to_approval_records_denied(self):
        slug = "shell-guard-test"
        issues_dir = os.path.join(self.root, ".along", "ISSUES")
        textio.write_text(os.path.join(issues_dir, f"feat--{slug}.md"),
                          f"---\nprotocol: along\nslug: {slug}\ntype: feat\npriority: medium\nstatus: in-progress\n---\n")
        session.init_session(self.root, slug)
        session.bind_session(self.root, slug, key=self.key, approved=False)
        engine = HookEngine(config=hook_config.HooksConfig(profile="standard"), repo_root=self.root)

        targets = (
            f".along/.session/{slug}/state.json",
            f".along/.session/bindings/{self.key}.json",
            f".along/.session/{slug}/events.jsonl",
            ".along/.session/plan-approvals.jsonl",
            f".along/diagnostics/activity/{self.key}.json",
        )

        for target in targets:
            # 1. Redirections
            redirs = [
                f"echo {{}} > {target}",
                f"echo {{}} >> {target}",
                f"echo {{}} 1> {target}",
                f"echo {{}} &> {target}",
            ]
            for cmd in redirs:
                with self.subTest(cmd=cmd):
                    res = engine.evaluate(self._shell_event(cmd))
                    self.assertFalse(res.is_allowed, f"Expected denial for: {cmd}")
                    self.assertIn("approval record", res.reason or "")

            # 2. File utilities: cp, mv, install, rm, truncate, sed -i, dd of=, tee
            commands = [
                f"cp foo.json {target}",
                f"mv foo.json {target}",
                f"install foo.json {target}",
                f"rm {target}",
                f"truncate -s 0 {target}",
                f"sed -i 's/a/b/' {target}",
                f"dd if=/dev/zero of={target}",
                f"echo {{}} | tee {target}",
            ]
            for cmd in commands:
                with self.subTest(cmd=cmd):
                    res = engine.evaluate(self._shell_event(cmd))
                    self.assertFalse(res.is_allowed, f"Expected denial for: {cmd}")
                    self.assertIn("approval record", res.reason or "")

            # 3. PowerShell cmdlets
            pwsh_cmds = [
                f"Set-Content -Path {target} -Value '{{}}'",
                f"Add-Content -Path {target} -Value '{{}}'",
                f"'{{}}' | Out-File {target}",
                f"Copy-Item src/file.json {target}",
                f"Move-Item src/file.json {target}",
                f"Remove-Item {target}",
                f"New-Item -Path {target} -ItemType File",
                f"Clear-Content {target}",
            ]
            for cmd in pwsh_cmds:
                with self.subTest(cmd=cmd):
                    res = engine.evaluate(self._shell_event(cmd))
                    self.assertFalse(res.is_allowed, f"Expected denial for: {cmd}")
                    self.assertIn("approval record", res.reason or "")

            # 4. .NET reflection
            dotnet_cmds = [
                f"[System.IO.File]::WriteAllText('{target}', '{{}}')",
                f"[IO.File]::WriteAllText('{target}', '{{}}')",
            ]
            for cmd in dotnet_cmds:
                with self.subTest(cmd=cmd):
                    res = engine.evaluate(self._shell_event(cmd))
                    self.assertFalse(res.is_allowed, f"Expected denial for: {cmd}")
                    self.assertIn("approval record", res.reason or "")

            # 5. Inline interpreters
            interp_cmds = [
                f"python -c \"open('{target}', 'w').write('{{}}')\"",
                f"py -c \"open('{target}', 'w').write('{{}}')\"",
                f"node -e \"fs.writeFileSync('{target}', '{{}}')\"",
                f"pwsh -c \"Set-Content {target} '{{}}'\"",
                f"powershell -Command \"Set-Content {target} '{{}}'\"",
            ]
            for cmd in interp_cmds:
                with self.subTest(cmd=cmd):
                    res = engine.evaluate(self._shell_event(cmd))
                    self.assertFalse(res.is_allowed, f"Expected denial for: {cmd}")
                    self.assertIn("approval record", res.reason or "")

    def test_windows_backslash_spelling_denied(self):
        slug = "bs-test"
        session.init_session(self.root, slug)
        engine = HookEngine(config=hook_config.HooksConfig(profile="standard"), repo_root=self.root)
        cmd = f"echo {{}} > .along\\.session\\{slug}\\state.json"
        res = engine.evaluate(self._shell_event(cmd))
        self.assertFalse(res.is_allowed)
        self.assertIn("approval record", res.reason or "")

    def test_shell_reads_allowed(self):
        slug = "read-test"
        session.init_session(self.root, slug)
        target = f".along/.session/{slug}/state.json"
        engine = HookEngine(config=hook_config.HooksConfig(profile="standard"), repo_root=self.root)

        read_cmds = [
            f"cat {target}",
            f"Get-Content {target}",
            f"type .along\\.session\\{slug}\\state.json",
            f"jq . {target}",
            f"grep 'plan' {target}",
            "echo x > src/a.txt",
        ]
        for cmd in read_cmds:
            with self.subTest(cmd=cmd):
                res = engine.evaluate(self._shell_event(cmd))
                self.assertTrue(res.is_allowed, f"Expected '{cmd}' to be allowed, got: {res.reason}")

    def test_stop_time_revocation_of_forged_approval(self):
        slug = "forge-test"
        issues_dir = os.path.join(self.root, ".along", "ISSUES")
        textio.write_text(os.path.join(issues_dir, f"feat--{slug}.md"),
                          f"---\nprotocol: along\nslug: {slug}\ntype: feat\npriority: medium\nstatus: in-progress\n---\n")
        session.init_session(self.root, slug)
        session.bind_session(self.root, slug, key=self.key, approved=False)
        engine = HookEngine(config=hook_config.HooksConfig(profile="standard"), repo_root=self.root)

        # Baseline on prompt submit
        submit_event = HookEvent(
            event_type=HookEventType.USER_PROMPT_SUBMIT,
            workspace_root=self.root,
            conversation_id="sess-shell-guard",
        )
        engine.evaluate(submit_event)

        # Agent forged approval indirectly
        st = session.load_state(self.root, slug)
        st["plan_approved"] = True
        session.save_state(self.root, slug, st)

        # Stop event
        stop_event = HookEvent(
            event_type=HookEventType.STOP,
            workspace_root=self.root,
            conversation_id="sess-shell-guard",
        )
        res_stop = engine.evaluate(stop_event)
        self.assertFalse(res_stop.is_allowed)
        self.assertIn("PLAN_REQUIRED", res_stop.reason or "")
        self.assertIn("the approval was revoked", res_stop.reason or "")

        # Verify revoked
        self.assertFalse(session.is_plan_approved(self.root, slug=slug, key=self.key))
        st_after = session.load_state(self.root, slug)
        self.assertFalse(st_after.get("plan_approved", False))
        self.assertEqual(st_after.get("phase"), "planning")

    def test_stop_time_legitimate_approval_passes(self):
        slug = "legit-test"
        issues_dir = os.path.join(self.root, ".along", "ISSUES")
        textio.write_text(os.path.join(issues_dir, f"feat--{slug}.md"),
                          f"---\nprotocol: along\nslug: {slug}\ntype: feat\npriority: medium\nstatus: in-progress\n---\n")
        session.init_session(self.root, slug)
        session.bind_session(self.root, slug, key=self.key, approved=False)
        engine = HookEngine(config=hook_config.HooksConfig(profile="standard"), repo_root=self.root)

        # Baseline on prompt submit
        submit_event = HookEvent(
            event_type=HookEventType.USER_PROMPT_SUBMIT,
            workspace_root=self.root,
            conversation_id="sess-shell-guard",
        )
        engine.evaluate(submit_event)

        # Legitimate approval records an event in ledger
        session.record_accepted_plan(self.root, self.key, "# Plan")

        # Stop event
        stop_event = HookEvent(
            event_type=HookEventType.STOP,
            workspace_root=self.root,
            conversation_id="sess-shell-guard",
        )
        res_stop = engine.evaluate(stop_event)
        self.assertTrue(res_stop.is_allowed, f"Expected stop to be allowed, got: {res_stop.reason}")
        self.assertTrue(session.is_plan_approved(self.root, slug=slug, key=self.key))


if __name__ == "__main__":
    unittest.main()
