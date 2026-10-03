#!/usr/bin/env python3
"""
tests/test_subproject_and_team_gates.py - Subproject boundary and along-team step gates.

Regression suite for [feat--subproject-boundary-by-active-issue] and
[feat--along-team-step-enforcement]. Throwaway directories, cleared session environment.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import session, textio
from alongkit.hooks import HookEvent, HookEventType
from alongkit.hooks.predicates import (
    check_active_issue,
    check_mutation_authorization,
    check_subproject_boundary,
    check_team_reviews_before_stop,
    check_team_step_active,
)

CLEAN_ENV = {k: v for k, v in os.environ.items() if k not in session.SESSION_ENV_VARS}
SID = "sess-1"
KEY = session.session_key("claude", SID)


def _put_issue(ctx: str, key: str, status: str = "in-progress", parent: str = "") -> None:
    itype, slug = key.split("--", 1)
    extra = f"parent: {parent}\n" if parent else ""
    textio.write_text(os.path.join(ctx, ".along", "ISSUES", f"{key}.md"),
                      f"---\nslug: {slug}\ntype: {itype}\nstatus: {status}\n{extra}---\n\n# {slug}\n")


def _write_event(root: str, rel: str, event_type=HookEventType.PRE_TOOL_USE) -> HookEvent:
    return HookEvent(event_type=event_type, tool_name="write_to_file",
                     tool_args={"TargetFile": os.path.join(root, rel), "CodeContent": "x = 1\n"},
                     workspace_root=root, runtime="claude", conversation_id=SID)


class Workspace(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, CLEAN_ENV, clear=True)
        self.env.start()
        self.root = tempfile.mkdtemp(prefix="along-sub-test-")
        self.web = os.path.join(self.root, "webapp")
        for ctx in (self.root, self.web):
            os.makedirs(os.path.join(ctx, ".along", "ISSUES"))
            os.makedirs(os.path.join(ctx, ".along", ".session"))
        os.makedirs(os.path.join(self.root, ".git"))

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def start(self, ctx: str, key: str, approved: bool = True, mode: str = "direct") -> None:
        slug = key.split("--", 1)[1]
        session.init_session(ctx, slug, execution_mode=mode, total_steps=2)
        session.bind_session(ctx, slug, key=KEY, approved=approved)
        if approved:
            session.update_state(ctx, slug, phase="execution", plan_approved=True)


class TestSubprojectBoundary(Workspace):
    def test_binding_lives_at_workspace_root(self):
        _put_issue(self.web, "feat--web-form")
        self.start(self.web, "feat--web-form")
        self.assertTrue(os.path.isfile(os.path.join(self.root, ".along", ".session", "bindings", f"{KEY}.json")))
        self.assertEqual(session.resolve_active_session(self.web, KEY), ("web-form", "binding"))
        self.assertEqual(session.resolve_active_session(self.root, KEY), (None, "elsewhere"))

    def test_subproject_issue_allows_its_files_and_plan_gate_sees_approval(self):
        _put_issue(self.web, "feat--web-form")
        self.start(self.web, "feat--web-form")
        edit = _write_event(self.root, "webapp/src/form.ts")
        self.assertIsNone(check_subproject_boundary(edit, self.root))
        self.assertIsNone(check_active_issue(edit, self.root))
        self.assertIsNone(check_mutation_authorization(edit, self.root))

    def test_root_issue_does_not_cover_subproject_files(self):
        _put_issue(self.root, "feat--root-task")
        self.start(self.root, "feat--root-task")
        reason = check_subproject_boundary(_write_event(self.root, "webapp/src/form.ts"), self.root)
        self.assertIn("subproject-boundary", reason)

    def test_umbrella_with_child_in_subproject(self):
        _put_issue(self.root, "feat--umbrella")
        _put_issue(self.web, "feat--web-part", status="open", parent="feat--umbrella")
        self.start(self.root, "feat--umbrella")
        self.assertIsNone(check_subproject_boundary(_write_event(self.root, "webapp/src/form.ts"), self.root))

    def test_subproject_session_may_not_edit_root_files(self):
        _put_issue(self.web, "feat--web-form")
        _put_issue(self.root, "feat--someone-else")
        self.start(self.web, "feat--web-form")
        reason = check_active_issue(_write_event(self.root, "server/main.py"), self.root)
        self.assertIn("outside that subproject", reason)


class TestTeamSteps(Workspace):
    def test_role_based_requires_in_progress_step(self):
        _put_issue(self.root, "feat--team-task")
        self.start(self.root, "feat--team-task", mode="role-based")
        edit = _write_event(self.root, "src/app.py")
        self.assertIn("team-step-active", check_team_step_active(edit, self.root))
        session.update_state(self.root, "team-task", current_step=1, step_status="in-progress")
        self.assertIsNone(check_team_step_active(edit, self.root))
        self.assertIsNone(check_team_step_active(_write_event(self.root, ".along/.session/team-task/plan.md"), self.root))

    def test_direct_mode_is_not_held_to_steps(self):
        _put_issue(self.root, "feat--quick-fix")
        self.start(self.root, "feat--quick-fix")
        self.assertIsNone(check_team_step_active(_write_event(self.root, "src/app.py"), self.root))

    def test_passed_step_needs_review_before_stop(self):
        _put_issue(self.root, "feat--team-task")
        self.start(self.root, "feat--team-task", mode="role-based")
        session.update_state(self.root, "team-task", current_step=1, step_status="passed")
        stop = HookEvent(event_type=HookEventType.STOP, tool_name="", tool_args={}, workspace_root=self.root,
                         runtime="claude", conversation_id=SID)
        self.assertIn("reviews/step-1.md", check_team_reviews_before_stop(stop, self.root))
        textio.write_text(session.review_file(self.root, "team-task", 1), "# Review\n\nVerdict: pass\n")
        self.assertIsNone(check_team_reviews_before_stop(stop, self.root))
        self.assertEqual(session.completion_problems(self.root, "team-task"), ["step 2 'Step 2' is pending"])

    def test_fallback_records_reason_and_lifts_enforcement(self):
        _put_issue(self.root, "feat--team-task")
        self.start(self.root, "feat--team-task", mode="role-based")
        session.record_fallback(self.root, "team-task", "one file, no parallel roles")
        self.assertIsNone(check_team_step_active(_write_event(self.root, "src/app.py"), self.root))
        trace = textio.read_text(os.path.join(session.get_session_dir(self.root, "team-task"),
                                              session.TRACE_FILENAME))
        self.assertIn("one file, no parallel roles", trace)


if __name__ == "__main__":
    unittest.main(verbosity=2)
