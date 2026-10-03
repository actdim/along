#!/usr/bin/env python3
"""
tests/test_session_bindings.py - Per-agent-session issue binding and plan approval.

Regression suite for [bug--session-state-cross-session-leak] and
[feat--plan-approval-exit-plan-mode]: parallel agent sessions in one repository resolve
their own issue and approval, never another session's, and a stale repository-level
pointer has no effect on sessions that carry an id.

All tests use throwaway directories and a cleared session environment.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import session
from alongkit.hooks import HookEvent, HookEventType
from alongkit.hooks import shellparse
from alongkit.hooks.predicates import (
    check_active_issue,
    check_mutation_authorization,
    record_tool_activity,
)

CLEAN_ENV = {k: v for k, v in os.environ.items() if k not in session.SESSION_ENV_VARS}


def _write_issue(root: str, slug: str, status: str = "in-progress") -> None:
    path = os.path.join(root, ".along", "ISSUES", f"feat--{slug}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"---\nslug: {slug}\ntype: feat\nstatus: {status}\n---\n\n# {slug}\n")


def _edit(root: str, sid: str, runtime: str = "claude") -> HookEvent:
    return HookEvent(
        event_type=HookEventType.PRE_TOOL_USE,
        tool_name="write_to_file",
        tool_args={"TargetFile": os.path.join(root, "src", "main.py"), "CodeContent": "x = 1\n"},
        workspace_root=root,
        runtime=runtime,
        conversation_id=sid,
    )


class SessionFixture(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, CLEAN_ENV, clear=True)
        self.env.start()
        self.root = tempfile.mkdtemp(prefix="along-bind-test-")
        os.makedirs(os.path.join(self.root, ".along", "ISSUES"))
        os.makedirs(os.path.join(self.root, ".along", ".session"))
        self.key_a = session.session_key("claude", "sess-a")
        self.key_b = session.session_key("claude", "sess-b")

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def start(self, slug: str, key: str, approved=None) -> None:
        _write_issue(self.root, slug)
        session.init_session(self.root, slug)
        session.bind_session(self.root, slug, key=key, approved=approved)
        if approved:
            session.update_state(self.root, slug, phase="execution", plan_approved=True)


class TestSessionKey(SessionFixture):
    def test_key_from_env(self):
        self.assertIsNone(session.current_session_key({}))
        self.assertEqual(session.current_session_key({"CLAUDE_CODE_SESSION_ID": "abc"}), "claude--abc")
        self.assertEqual(session.current_session_key({"ALONG_SESSION_ID": "x/y", "ALONG_SESSION_RUNTIME": "codex"}),
                         "codex--x_y")


class TestParallelSessions(SessionFixture):
    def test_two_sessions_resolve_their_own_issue(self):
        self.start("alpha", self.key_a)
        self.start("beta", self.key_b)
        self.assertEqual(session.resolve_active_session(self.root, self.key_a), ("alpha", "binding"))
        self.assertEqual(session.resolve_active_session(self.root, self.key_b), ("beta", "binding"))

    def test_approval_does_not_leak_between_sessions(self):
        self.start("alpha", self.key_a, approved=True)
        self.start("beta", self.key_b)
        self.assertIsNone(check_mutation_authorization(_edit(self.root, "sess-a"), self.root))
        self.assertIsNotNone(check_mutation_authorization(_edit(self.root, "sess-b"), self.root))

    def test_stale_repository_pointer_is_ignored_with_session_id(self):
        self.start("beta", self.key_b)
        session.save_global_session_state(self.root, {"active_slug": "beta", "phase": "execution",
                                                      "plan_approved": True})
        self.assertIsNotNone(check_mutation_authorization(_edit(self.root, "sess-new"), self.root))

    def test_unbound_session_does_not_adopt_another_sessions_issue(self):
        self.start("alpha", self.key_a, approved=True)
        self.assertEqual(session.resolve_active_session(self.root, self.key_b), (None, "none"))

    def test_ambiguous_without_binding(self):
        for slug in ("alpha", "beta"):
            _write_issue(self.root, slug)
            session.init_session(self.root, slug)
        slug, how = session.resolve_active_session(self.root, self.key_a)
        self.assertEqual((slug, how), (None, "ambiguous"))
        reason = check_active_issue(_edit(self.root, "sess-a"), self.root)
        self.assertIn("none is bound", reason)

    def test_single_unbound_blackboard_is_used(self):
        _write_issue(self.root, "alpha")
        session.init_session(self.root, "alpha")
        self.assertEqual(session.resolve_active_session(self.root, self.key_a), ("alpha", "single"))


class TestPlanApproval(SessionFixture):
    def test_exit_plan_mode_approves_this_session_only(self):
        self.start("alpha", self.key_a)
        self.start("beta", self.key_b)
        post = HookEvent(event_type=HookEventType.POST_TOOL_USE, tool_name="ask_question",
                         tool_args={}, workspace_root=self.root, runtime="claude",
                         conversation_id="sess-a", raw_payload={"tool_name": "ExitPlanMode"})
        record_tool_activity(post, self.root)
        self.assertTrue(session.is_plan_approved(self.root, key=self.key_a))
        self.assertEqual(session.get_session_phase(self.root, key=self.key_a), "execution")
        self.assertFalse(session.is_plan_approved(self.root, key=self.key_b))

    def test_approval_before_start_carries_to_first_slug_only(self):
        session.record_plan_approval(self.root, self.key_a)
        self.start("alpha", self.key_a)
        self.assertTrue(session.is_plan_approved(self.root, key=self.key_a))
        self.start("gamma", self.key_a)
        self.assertFalse(session.is_plan_approved(self.root, key=self.key_a))

    def test_along_state_commands_pass_the_plan_gate(self):
        for cmd in ("along issue create bug x-y --title T", "along start x-y",
                    "python scripts/along_exec.py issue sync", "along plan status && git status"):
            self.assertTrue(shellparse.is_along_state_command(cmd), cmd)
        for cmd in ("along commit -m x", "along bump patch", "along issue sync > out.txt",
                    "along start x && rm -rf src"):
            self.assertFalse(shellparse.is_along_state_command(cmd), cmd)
        event = HookEvent(event_type=HookEventType.PRE_TOOL_USE, tool_name="run_command",
                          tool_args={"CommandLine": "along issue create bug a-b --title T"},
                          workspace_root=self.root, runtime="claude", conversation_id="sess-a")
        self.assertIsNone(check_mutation_authorization(event, self.root))


class TestBindingLifecycle(SessionFixture):
    def test_purge_removes_bindings_and_matching_pointer(self):
        self.start("alpha", self.key_a)
        session.save_global_session_state(self.root, {"active_slug": "alpha"})
        self.assertTrue(session.purge_session(self.root, "alpha"))
        self.assertEqual(session.list_bindings(self.root), [])
        self.assertIsNone(session.load_global_session_state(self.root))

    def test_gc_removes_stale_and_orphaned(self):
        self.start("alpha", self.key_a)
        self.start("beta", self.key_b)
        shutil.rmtree(session.get_session_dir(self.root, "beta"))
        self.assertEqual(session.gc_bindings(self.root, dry_run=True), [self.key_b])
        future = datetime.now(timezone.utc) + timedelta(hours=session.BINDING_MAX_AGE_HOURS + 1)
        self.assertEqual(sorted(session.gc_bindings(self.root, now=future)), sorted([self.key_a, self.key_b]))
        self.assertEqual(session.list_bindings(self.root), [])

    def test_binding_file_is_json(self):
        self.start("alpha", self.key_a)
        path = os.path.join(session.bindings_dir(self.root), f"{self.key_a}.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["slug"], "alpha")
        self.assertNotIn("alpha", [e for e in os.listdir(os.path.join(self.root, ".along", ".session"))
                                   if e == session.BINDINGS_DIRNAME])


if __name__ == "__main__":
    unittest.main(verbosity=2)
