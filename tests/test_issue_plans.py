#!/usr/bin/env python3
"""
tests/test_issue_plans.py - Plans kept with their issue and approved ahead of the work.

Covers [feat--pre-approved-plans]:
- The plan of an issue lives in `.along/ISSUES/<key>/plan.md` (committed with the ticket) and
  moves with it; the blackboard reads and writes that file.
- `along plan approve <slug>` before `along start` approves the plan ahead: ticket
  `plan_status: approved` plus a CLI-only approval event in `.along/.session/plan-approvals.jsonl`;
  `along start` then runs it with no second approval.
- `plan_status: approved` without an approval event on this machine (hand-written, or approved
  elsewhere) is not trusted; `needs-rework` keeps the session in planning.
- Only the CLI sets `approved`: a file-tool edit that sets it is denied, a shell write is
  reported at Stop, the approval log is closed to file tools.
- Corrections during work are revisions of the same file (`along plan revise`); the
  orchestrator uses an approved plan instead of its architect.
"""

from __future__ import annotations

import contextlib
import io
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

import along_exec
from alongkit import entities, frontmatter, orchestrator, proc, session, textio
from alongkit.hooks import config as hook_config
from alongkit.hooks.engine import HookEngine
from alongkit.hooks.models import HookEvent, HookEventType
from alongkit.hooks.predicates import record_tool_activity
from alongkit.runner import BaseRunner, RunResult
from hermetic import make_repo_fixture

CLEAN_ENV = {
    k: v for k, v in os.environ.items()
    if k not in session.SESSION_ENV_VARS and k not in ("ALONG_PROFILE", "ALONG_AUTONOMOUS")
}
SID = "sess-plans"
KEY = session.session_key("claude", SID)
PLAN = "# Plan\n\n- Step 1: Add the helper\n- Step 2: Wire it into the CLI\n"


class PlanFixture(unittest.TestCase):
    git = False

    def setUp(self):
        self.env = mock.patch.dict(os.environ, CLEAN_ENV, clear=True)
        self.env.start()
        self.root = make_repo_fixture(prefix="along-issue-plans-", with_docs=False)
        if self.git:
            for cmd in (["git", "init", "-q"], ["git", "config", "user.email", "t@example.com"],
                        ["git", "config", "user.name", "T"], ["git", "add", "-A"],
                        ["git", "commit", "-q", "-m", "init"]):
                proc.run_capture(cmd, cwd=self.root)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def issue(self, slug: str, extra: str = "", status: str = "open") -> str:
        path = os.path.join(self.root, ".along", "ISSUES", f"feat--{slug}.md")
        textio.write_text(path, f"---\nprotocol: along\nslug: {slug}\ntype: feat\nstatus: {status}\n"
                                f"priority: medium\ncreated: 2026-10-01\nupdated: 2026-10-01\n{extra}---\n\n"
                                f"# {slug}\n\nWhy and what.\n\n## Requirements\n- REQ-1: The tool MUST work.\n",
                          newline="\n")
        return path

    def plan_file(self, text: str = PLAN, name: str = "draft-plan.md") -> str:
        path = os.path.join(self.root, name)
        textio.write_text(path, text, newline="\n")
        return path

    def run_cli(self, handler, args):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"ALONG_SESSION_ID": SID, "ALONG_SESSION_RUNTIME": "claude"}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                handler(self.root, args)
                code = 0
            except SystemExit as exc:
                code = int(exc.code or 0)
        return code, out.getvalue(), err.getvalue()

    def status_of(self, slug: str):
        iss = entities.find_issue_by_slug(self.root, slug)
        return (iss.get("frontmatter") or {}).get("plan_status")

    def issue_plan(self, slug: str) -> str:
        return os.path.join(self.root, ".along", "ISSUES", f"feat--{slug}", "plan.md")


class TestApproveAheadThenStart(PlanFixture):
    def test_approve_ahead_then_start_runs_without_asking(self):
        self.issue("alpha")
        code, out, err = self.run_cli(along_exec.handle_plan_command,
                                      ["approve", "alpha", "--plan-file", self.plan_file()])
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.status_of("alpha"), "approved")
        self.assertIn("Step 1: Add the helper", textio.read_text(self.issue_plan("alpha")))
        self.assertIsNone(session.load_state(self.root, "alpha"), "approving ahead must not start the issue")
        self.assertTrue(session.plan_approval_confirmed(self.root, "alpha"))

        code, out, err = self.run_cli(along_exec.handle_start_command, ["alpha"])
        self.assertEqual(code, 0, out + err)
        self.assertIn("approved plan", out)
        self.assertTrue(session.is_plan_approved(self.root, slug="alpha", key=KEY))
        self.assertEqual(session.get_session_phase(self.root, slug="alpha", key=KEY), "execution")
        self.assertEqual(os.path.normcase(session.plan_path(self.root, "alpha")),
                         os.path.normcase(self.issue_plan("alpha")))
        self.assertIn("Step 2: Wire it into the CLI", session.read_plan(self.root, "alpha"))

    def test_no_recorded_user_message_is_unverified(self):
        self.issue("alpha")
        code, out, err = self.run_cli(along_exec.handle_plan_command,
                                      ["approve", "alpha", "--plan-file", self.plan_file()])
        self.assertEqual(code, 0, out + err)
        events = session.plan_approval_events(self.root, "alpha")
        self.assertEqual(events[-1]["via"], session.APPROVED_VIA_CLI_UNVERIFIED)

    def test_plan_newer_than_the_users_last_message_is_refused(self):
        self.issue("alpha")
        session.record_user_prompt(self.root, KEY, when="2020-01-01T00:00:00Z")
        code, _out, err = self.run_cli(along_exec.handle_plan_command,
                                       ["approve", "alpha", "--plan-file", self.plan_file()])
        self.assertEqual(code, 2)
        self.assertIn("plan changed after the user's last message", err)
        self.assertNotEqual(self.status_of("alpha"), "approved")
        self.assertFalse(session.plan_approval_confirmed(self.root, "alpha"))

    def test_plan_accepted_in_plan_mode_is_approved_ahead(self):
        self.issue("alpha")
        session.record_accepted_plan(self.root, KEY, PLAN)
        code, out, err = self.run_cli(along_exec.handle_plan_command, ["approve", "alpha"])
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.status_of("alpha"), "approved")
        self.assertIn("Add the helper", textio.read_text(self.issue_plan("alpha")))
        self.assertEqual(session.plan_approval_events(self.root, "alpha")[-1]["via"],
                         session.APPROVED_VIA_EXIT_PLAN_MODE)


class TestStartWithoutTrustedApproval(PlanFixture):
    def test_hand_written_approved_status_is_not_trusted(self):
        self.issue("alpha", "plan_status: approved\n")
        os.makedirs(os.path.dirname(self.issue_plan("alpha")))
        textio.write_text(self.issue_plan("alpha"), PLAN, newline="\n")
        code, out, err = self.run_cli(along_exec.handle_start_command, ["alpha"])
        self.assertEqual(code, 0, out + err)
        self.assertFalse(session.is_plan_approved(self.root, slug="alpha", key=KEY))
        self.assertIn("not confirmed", out)

    def test_needs_rework_stays_in_planning(self):
        self.issue("alpha")
        self.run_cli(along_exec.handle_plan_command, ["approve", "alpha", "--plan-file", self.plan_file()])
        code, out, err = self.run_cli(along_exec.handle_plan_command,
                                      ["rework", "alpha", "--reason", "REQ-1 cannot be met as written"])
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.status_of("alpha"), "needs-rework")
        self.assertFalse(session.plan_approval_confirmed(self.root, "alpha"))
        self.assertIn("REQ-1 cannot be met as written", textio.read_text(self.issue_plan("alpha")))
        code, out, err = self.run_cli(along_exec.handle_start_command, ["alpha"])
        self.assertEqual(code, 0, out + err)
        self.assertFalse(session.is_plan_approved(self.root, slug="alpha", key=KEY))

    def test_no_plan_starts_in_planning(self):
        self.issue("alpha")
        code, out, err = self.run_cli(along_exec.handle_start_command, ["alpha"])
        self.assertEqual(code, 0, out + err)
        self.assertFalse(session.is_plan_approved(self.root, slug="alpha", key=KEY))
        self.assertFalse(os.path.exists(self.issue_plan("alpha")), "no scaffold is written into the issue folder")


class TestLivingPlan(PlanFixture):
    def test_revise_appends_a_revision_and_keeps_the_approval(self):
        self.issue("alpha")
        self.run_cli(along_exec.handle_plan_command, ["approve", "alpha", "--plan-file", self.plan_file()])
        self.run_cli(along_exec.handle_start_command, ["alpha"])
        revised = self.plan_file("- Step 1: Add the helper\n- Step 2: Wire it\n- Step 3: Cover the edge case\n",
                                 name="revised.md")
        code, out, err = self.run_cli(along_exec.handle_plan_command,
                                      ["revise", "alpha", "--plan-file", revised,
                                       "--reason", "the CLI needs an extra branch"])
        self.assertEqual(code, 0, out + err)
        text = textio.read_text(self.issue_plan("alpha"))
        self.assertIn("## Revision 2 (", text)
        self.assertIn("the CLI needs an extra branch", text)
        self.assertIn("Step 1: Add the helper", text, "earlier revisions stay")
        self.assertEqual(self.status_of("alpha"), "approved")
        self.assertTrue(session.is_plan_approved(self.root, slug="alpha", key=KEY))

    def test_team_blackboard_uses_the_issue_plan(self):
        self.issue("alpha", status="in-progress")
        session.init_session(self.root, "alpha", execution_mode="role-based")
        session.record_plan(self.root, "alpha", PLAN, "architect")
        self.assertIn("Add the helper", textio.read_text(self.issue_plan("alpha")))
        self.assertFalse(os.path.exists(os.path.join(session.get_session_dir(self.root, "alpha"), "plan.md")))

    def test_blackboard_without_issue_keeps_its_own_plan(self):
        session.init_session(self.root, "scratch-only")
        self.assertEqual(os.path.normcase(session.plan_path(self.root, "scratch-only")),
                         os.path.normcase(os.path.join(session.get_session_dir(self.root, "scratch-only"),
                                                       "plan.md")))


class TestPlanFolderMovesWithTicket(PlanFixture):
    def test_done_reopen_and_rename_move_the_folder(self):
        self.issue("alpha")
        self.run_cli(along_exec.handle_plan_command, ["approve", "alpha", "--plan-file", self.plan_file()])
        issues = os.path.join(self.root, ".along", "ISSUES")

        code, out, err = self.run_cli(along_exec.handle_issue_command, ["done", "alpha", "--status", "cancelled"])
        self.assertEqual(code, 0, out + err)
        self.assertTrue(os.path.isfile(os.path.join(issues, "done", "feat--alpha", "plan.md")))
        self.assertFalse(os.path.exists(os.path.join(issues, "feat--alpha")))

        code, out, err = self.run_cli(along_exec.handle_issue_command, ["reopen", "alpha"])
        self.assertEqual(code, 0, out + err)
        self.assertTrue(os.path.isfile(self.issue_plan("alpha")))

        entities.rename_issue(self.root, "feat--alpha", "feat--beta-task")
        self.assertTrue(os.path.isfile(os.path.join(issues, "feat--beta-task", "plan.md")))
        self.assertFalse(os.path.exists(os.path.join(issues, "feat--alpha")))

    def test_board_shows_plan_status(self):
        self.issue("alpha")
        self.run_cli(along_exec.handle_plan_command, ["approve", "alpha", "--plan-file", self.plan_file()])
        board = entities.compile_issues_board(self.root)
        self.assertIn("plan ready", board)


class TestApprovedStatusIsCliOnly(PlanFixture):
    def _event(self, target: str, tool: str, args: dict) -> HookEvent:
        return HookEvent(event_type=HookEventType.PRE_TOOL_USE, tool_name=tool,
                         tool_args=dict(args, TargetFile=target), workspace_root=self.root,
                         conversation_id=SID)

    def test_file_tool_cannot_set_approved(self):
        path = self.issue("alpha", "plan_status: needs-approval\n")
        engine = HookEngine(config=hook_config.HooksConfig(profile="standard"), repo_root=self.root)
        rel = ".along/ISSUES/feat--alpha.md"
        content = textio.read_text(path).replace("plan_status: needs-approval", "plan_status: approved")
        for tool, args in (("write_to_file", {"CodeContent": content}),
                           ("replace_file_content", {"TargetContent": "plan_status: needs-approval",
                                                     "ReplacementContent": "plan_status: approved"})):
            with self.subTest(tool=tool):
                res = engine.evaluate(self._event(rel, tool, args))
                self.assertFalse(res.is_allowed, "Setting plan_status: approved by a file tool must be denied")
                self.assertIn("along plan approve", res.reason or "")

        res = engine.evaluate(self._event(rel, "replace_file_content",
                                          {"TargetContent": "plan_status: needs-approval",
                                           "ReplacementContent": "plan_status: needs-rework"}))
        self.assertTrue(res.is_allowed, res.reason)

    def test_file_tool_cannot_write_the_approval_log(self):
        self.issue("alpha")
        engine = HookEngine(config=hook_config.HooksConfig(profile="standard"), repo_root=self.root)
        res = engine.evaluate(self._event(".along/.session/plan-approvals.jsonl", "write_to_file",
                                          {"CodeContent": '{"slug": "alpha", "event": "approve"}\n'}))
        self.assertFalse(res.is_allowed)
        self.assertIn("approval record", res.reason or "")


class TestShellWrittenApprovalAtStop(PlanFixture):
    git = True

    def _prompt(self):
        record_tool_activity(HookEvent(event_type=HookEventType.USER_PROMPT_SUBMIT, tool_name="",
                                       tool_args={}, workspace_root=self.root, runtime="claude",
                                       conversation_id=SID), self.root)

    def _stop(self):
        engine = HookEngine(config=hook_config.HooksConfig(profile="standard"), repo_root=self.root)
        return engine.evaluate(HookEvent(event_type=HookEventType.STOP, tool_name="", tool_args={},
                                         workspace_root=self.root, runtime="claude", conversation_id=SID))

    def test_status_written_outside_the_cli_is_reported(self):
        path = self.issue("alpha", "plan_status: needs-approval\n")
        proc.run_capture(["git", "add", "-A"], cwd=self.root)
        proc.run_capture(["git", "commit", "-q", "-m", "issue"], cwd=self.root)
        self._prompt()
        textio.write_text(path, textio.read_text(path).replace("needs-approval", "approved"), newline="\n")
        res = self._stop()
        self.assertFalse(res.is_allowed, "An approved status with no approval event must be reported")
        self.assertIn("plan_status", res.reason or "")

    def test_status_set_by_the_cli_passes(self):
        self.issue("alpha", "plan_status: needs-approval\n")
        os.makedirs(os.path.dirname(self.issue_plan("alpha")))
        textio.write_text(self.issue_plan("alpha"), PLAN, newline="\n")
        proc.run_capture(["git", "add", "-A"], cwd=self.root)
        proc.run_capture(["git", "commit", "-q", "-m", "issue"], cwd=self.root)
        self._prompt()
        session.record_user_prompt(self.root, KEY, when="2999-01-01T00:00:00Z")
        code, out, err = self.run_cli(along_exec.handle_plan_command, ["approve", "alpha"])
        self.assertEqual(code, 0, out + err)
        session.record_user_prompt(self.root, KEY, when="2000-01-01T00:00:00Z")
        res = self._stop()
        self.assertNotIn("plan_status", res.reason or "")


class _Runner(BaseRunner):
    def __init__(self, calls, **kwargs):
        super().__init__(**kwargs)
        self.calls = calls

    def execute_run(self, brief, role="implementer", model=None, timeout=None, step=None,
                    run_id=None, handoff_note=None, dry_run=None):
        self.calls.append(role)
        # A step passes only on a valid verdict; this reviewer prints it on stdout.
        # [bug--orchestrator-review-fail-open]
        stdout = "---\nverdict: pass\ndefects: []\n---\n" if role == "reviewer" else ""
        self.last_result = RunResult(run_id="r", outcome="done", exit_code=0, stdout=stdout, stderr="",
                                     changed_files=[], handoff_note=None, record={})
        return {"outcome": "done", "exit_code": 0, "changed_files": []}


class TestOrchestratorUsesApprovedPlan(PlanFixture):
    def _orch(self, calls):
        orch = orchestrator.CrossRuntimeOrchestrator(repo_root=self.root, slug="alpha")
        orch._instantiate_runner = lambda role: _Runner(calls, repo_root=self.root, issue_slug="alpha")
        return orch

    def test_approved_plan_skips_the_architect(self):
        self.issue("alpha", status="in-progress")
        self.run_cli(along_exec.handle_plan_command, ["approve", "alpha", "--plan-file", self.plan_file()])
        calls = []
        res = self._orch(calls).orchestrate(skip_scout=True)
        self.assertNotIn("architect", calls)
        self.assertEqual(res.get("status"), "completed", res)
        st = session.load_state(self.root, "alpha")
        self.assertEqual(st.get("total_steps"), 2)
        self.assertTrue(st.get("plan_approved"))

    def test_unconfirmed_approved_plan_needs_input(self):
        self.issue("alpha", "plan_status: approved\n", status="in-progress")
        os.makedirs(os.path.dirname(self.issue_plan("alpha")))
        textio.write_text(self.issue_plan("alpha"), PLAN, newline="\n")
        calls = []
        res = self._orch(calls).orchestrate(skip_scout=True)
        self.assertEqual(res.get("status"), "needs-input", res)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
