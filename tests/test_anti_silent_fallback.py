#!/usr/bin/env python3
"""
tests/test_anti_silent_fallback.py - A tool call a gate denied is redone or disclosed, never
silently dropped. Regression suite for [feat--anti-silent-fallback-gate]:

- an enforced denial of a bound session's tool call is a `deny` event in the issue ledger
  (once per gate and target while open), and an open denial in the session's activity trace;
- an allowed retry on the same target settles it (`resolve`, via retry); a procedural gate's
  denial settles on a later plan approval;
- the Stop gate `unresolved_gate_denial` holds a turn with open denials of that turn until they
  are retried or acknowledged (`along gates ack`);
- closeout, `along wrap` and `along issue done` refuse open denials and acknowledgements the
  user has not replied to; `--force-reason` passes only under the bypass rules.
"""

from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import closeout, lifecycle, session
from alongkit.commands import gates as gates_cmd
from alongkit.commands import issue as issue_cmd
from alongkit.hooks import HookEngine, HookEvent, HookEventType, HooksConfig
from alongkit.hooks.declarative import get_all_declarative_gates
from alongkit.hooks.gates import BaseGate
from alongkit.hooks.models import GateDecision, GateResult
from alongkit.hooks.predicates import check_unresolved_denials, load_activity_trace

SLUG = "work"
PAST = "2000-01-01T00:00:00Z"
FUTURE = "2999-01-01T00:00:00Z"

ISSUE_TEXT = """---
protocol: along
slug: work
type: feat
status: in-progress
priority: medium
created: 2026-10-23
updated: 2026-10-23
---

# Work

## Goal
Deliver the work item so the denial lifecycle can be exercised end to end.

## Acceptance Criteria
- [x] The work item is delivered and verified.
"""


class _DenyTarget(BaseGate):
    """Denies every tool call whose target contains `needle`."""

    def __init__(self, name: str, needle: str, procedural: bool = False):
        self.name = name
        self.needle = needle
        if procedural:
            self.defn = mock.Mock(options={"denial": "procedural"})

    def evaluate(self, event: HookEvent) -> GateResult:
        args = event.tool_args or {}
        target = str(args.get("TargetFile") or args.get("CommandLine") or "")
        if event.event_type == HookEventType.PRE_TOOL_USE and self.needle in target:
            return GateResult(decision=GateDecision.DENY, reason=f"{self.name} holds {self.needle}",
                              gate_name=self.name, exit_code=2)
        return GateResult(decision=GateDecision.ALLOW, gate_name=self.name)


def _write_text(path: str, text: str = "") -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


class _BoundSession(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along-denials-")
        _write_text(os.path.join(self.root, ".along", "ISSUES.md"), "# Active Issues\n")
        self.issue = _write_text(os.path.join(self.root, ".along", "ISSUES", f"feat--{SLUG}.md"), ISSUE_TEXT)
        os.makedirs(os.path.join(self.root, ".along", "ISSUES", "done"), exist_ok=True)
        self.key = session.session_key("claude", "sess-1")
        session.init_session(self.root, SLUG)
        session.bind_session(self.root, SLUG, key=self.key)
        _write_text(session.plan_path(self.root, SLUG), "# Living Plan: work\n\nDo the work.\n")
        self.env = mock.patch.dict(os.environ, {"ALONG_SESSION_KEY": self.key})
        self.env.start()
        session.record_user_prompt(self.root, self.key, when=PAST)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def _engine(self, *gates: BaseGate) -> HookEngine:
        return HookEngine(gates=list(gates), config=HooksConfig(), repo_root=self.root)

    def _write(self, target: str, event_type=HookEventType.PRE_TOOL_USE) -> HookEvent:
        return HookEvent(event_type=event_type, tool_name="write_to_file",
                         tool_args={"TargetFile": target, "CodeContent": "x = 1\n"},
                         workspace_root=self.root, runtime="claude", conversation_id="sess-1")

    def _cmd(self, cmd: str) -> HookEvent:
        return HookEvent(event_type=HookEventType.PRE_TOOL_USE, tool_name="run_command",
                         tool_args={"CommandLine": cmd}, workspace_root=self.root, runtime="claude",
                         conversation_id="sess-1")

    def _stop(self) -> HookEvent:
        return HookEvent(event_type=HookEventType.STOP, tool_name="", tool_args={},
                         workspace_root=self.root, runtime="claude", conversation_id="sess-1")

    def _deny_push(self) -> str:
        engine = self._engine(_DenyTarget("push_guard", "git push"))
        self.assertFalse(engine.evaluate(self._cmd("git push --force")).is_allowed)
        items = session.denial_status(self.root, SLUG)
        self.assertEqual(len(items), 1)
        return items[0]["id"]

    def _cli(self, fn, *args) -> int:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = fn(*args)
            except SystemExit as exc:
                code = exc.code
        self.output = out.getvalue() + err.getvalue()
        return int(code or 0)


class TestRecording(_BoundSession):
    def test_denial_is_a_ledger_event_and_an_open_denial(self):
        did = self._deny_push()
        events = [e for e in session.load_events(self.root, SLUG) if e["kind"] == "deny"]
        self.assertEqual(events[0]["gate"], "push_guard")
        self.assertEqual(events[0]["target"], "git push --force")
        self.assertEqual(events[0]["id"], did)
        trace = load_activity_trace(self.root, self.key)
        self.assertEqual([d["id"] for d in trace["open_denials"]], [did])

    def test_repeated_identical_denial_is_recorded_once(self):
        engine = self._engine(_DenyTarget("push_guard", "git push"))
        for _ in range(3):
            engine.evaluate(self._cmd("git push --force"))
        self.assertEqual(len(session.denial_status(self.root, SLUG)), 1)

    def test_unbound_session_records_nothing(self):
        session.unbind_slug(self.root, SLUG)
        engine = self._engine(_DenyTarget("push_guard", "git push"))
        engine.evaluate(self._cmd("git push --force"))
        self.assertEqual(session.denial_status(self.root, SLUG), [])

    def test_stop_denials_are_not_tool_denials(self):
        engine = self._engine(_DenyTarget("push_guard", "git push"))
        engine.evaluate(self._stop())
        self.assertEqual(session.denial_status(self.root, SLUG), [])


class TestResolution(_BoundSession):
    def test_allowed_retry_of_the_same_command_resolves(self):
        did = self._deny_push()
        self._engine().evaluate(self._cmd("git push --force"))
        (item,) = session.denial_status(self.root, SLUG)
        self.assertEqual((item["id"], item["state"], item["via"]), (did, "resolved", "retry"))
        self.assertEqual(load_activity_trace(self.root, self.key).get("open_denials"), [])

    def test_a_different_command_does_not_resolve(self):
        self._deny_push()
        self._engine().evaluate(self._cmd("git status"))
        self.assertEqual(session.denial_status(self.root, SLUG)[0]["state"], "open")

    def test_write_resolves_only_once_it_succeeded(self):
        target = os.path.join(self.root, "src", "a.py")
        engine = self._engine(_DenyTarget("write_guard", "a.py"))
        engine.evaluate(self._write(target))
        allowed = self._engine()
        allowed.evaluate(self._write(target))
        self.assertEqual(session.denial_status(self.root, SLUG)[0]["state"], "open")
        allowed.evaluate(self._write(target, HookEventType.POST_TOOL_USE))
        self.assertEqual(session.denial_status(self.root, SLUG)[0]["state"], "resolved")

    def test_procedural_denial_settles_on_approval(self):
        engine = self._engine(_DenyTarget("plan_guard", "a.py", procedural=True))
        engine.evaluate(self._write(os.path.join(self.root, "src", "a.py")))
        self.assertEqual(session.denial_status(self.root, SLUG)[0]["state"], "open")
        self.assertEqual(load_activity_trace(self.root, self.key).get("open_denials") or [], [])
        session.record_accepted_plan(self.root, self.key, "# Plan\n\nDo the work.\n")
        (item,) = session.denial_status(self.root, SLUG)
        self.assertEqual((item["state"], item["via"]), ("resolved", "approve"))

    def test_catalogue_marks_the_plan_and_issue_gates_procedural(self):
        procedural = {g.name for g in get_all_declarative_gates()
                      if (getattr(g, "defn", None) and g.defn.options.get("denial") == "procedural")}
        self.assertEqual(procedural, {"require_plan_approval", "require_active_issue"})


class TestStopGate(_BoundSession):
    def test_open_denial_of_this_turn_holds_the_stop(self):
        did = self._deny_push()
        reason = check_unresolved_denials(self._stop(), self.root)
        self.assertIn(did, reason or "")
        self.assertIn("along gates ack", reason)

    def test_denial_before_the_users_last_message_does_not_hold_the_turn(self):
        self._deny_push()
        session.record_user_prompt(self.root, self.key, when=FUTURE)
        self.assertIsNone(check_unresolved_denials(self._stop(), self.root))

    def test_ack_releases_the_stop(self):
        did = self._deny_push()
        self.assertEqual(self._cli(gates_cmd._handle_denials, self.root, "ack",
                                   [did, "--note", "push not done: force push is held"]), 0)
        self.assertIsNone(check_unresolved_denials(self._stop(), self.root))

    def test_ack_needs_a_note(self):
        did = self._deny_push()
        self.assertEqual(self._cli(gates_cmd._handle_denials, self.root, "ack", [did]), 2)
        self.assertEqual(session.denial_status(self.root, SLUG)[0]["state"], "open")

    def test_catalogue_profiles(self):
        (gate,) = [g for g in get_all_declarative_gates() if g.name == "unresolved_gate_denial"]
        self.assertEqual(gate.defn.profiles, {"strict": "block", "standard": "block", "light": "warn"})
        self.assertEqual(gate.defn.event_type, HookEventType.STOP)

    def test_light_profile_only_warns(self):
        self._deny_push()
        (gate,) = [g for g in get_all_declarative_gates(repo_root=self.root) if g.name == "unresolved_gate_denial"]
        engine = HookEngine(gates=[gate], config=HooksConfig(profile="light"), repo_root=self.root)
        with redirect_stderr(io.StringIO()):
            self.assertTrue(engine.evaluate(self._stop()).is_allowed)
        strict = HookEngine(gates=[gate], config=HooksConfig(profile="strict"), repo_root=self.root)
        self.assertFalse(strict.evaluate(self._stop()).is_allowed)


class TestCloseout(_BoundSession):
    def _reasons(self):
        (item,) = [i for i in closeout.closeout_status(self.root)["items"] if i["slug"] == SLUG]
        return [r for r in item["reasons"] if "denial" in r]

    def test_open_denial_blocks_closeout(self):
        self._deny_push()
        self.assertTrue(any("unresolved" in r for r in self._reasons()))

    def test_ack_waits_for_the_users_reply(self):
        did = self._deny_push()
        self._cli(gates_cmd._handle_denials, self.root, "ack", [did, "--note", "told the user"])
        self.assertTrue(any("awaiting the user's reply" in r for r in self._reasons()))
        session.record_user_prompt(self.root, self.key, when=FUTURE)
        self.assertEqual(self._reasons(), [])

    def test_resolved_denial_does_not_block(self):
        self._deny_push()
        self._engine().evaluate(self._cmd("git push --force"))
        self.assertEqual(self._reasons(), [])

    def test_session_log_lists_unsettled_denials(self):
        did = self._deny_push()
        self._cli(gates_cmd._handle_denials, self.root, "ack", [did, "--note", "push left to the user"])
        text = session.render_blackboard_markdown(self.root, SLUG)
        self.assertIn("### Disclosed Gate Denials", text)
        self.assertIn(f"{did} [push_guard] git push --force (acknowledged): push left to the user", text)


class TestWrapAndIssueDone(_BoundSession):
    def _issue_done(self, *extra: str) -> int:
        return self._cli(issue_cmd.handle_issue_command, self.root, ["done", SLUG, *extra])

    def test_wrap_refuses_open_denials(self):
        self._deny_push()
        code = self._cli(lifecycle.execute_wrap, self.root, f"feat--{SLUG}")
        self.assertEqual(code, 2)
        self.assertIn("gate denials", self.output)

    def test_wrap_force_needs_the_users_reply_after_the_failure(self):
        self._deny_push()
        self._cli(lifecycle.execute_wrap, self.root, f"feat--{SLUG}")
        code = self._cli(lambda: lifecycle.execute_wrap(self.root, f"feat--{SLUG}", force_reason="user accepts",
                                                        guard_bypass=True))
        self.assertEqual(code, 2)
        self.assertIn("Bypass refused", self.output)

    def test_issue_done_refuses_open_denials(self):
        self._deny_push()
        self.assertEqual(self._issue_done(), 2)
        self.assertTrue(os.path.isfile(self.issue))

    def test_issue_done_cancel_is_not_held(self):
        self._deny_push()
        self.assertEqual(self._issue_done("--status", "cancelled"), 0)

    def test_issue_done_force_passes_after_the_users_reply(self):
        self._deny_push()
        self.assertEqual(self._issue_done(), 2)
        self.assertEqual(self._issue_done("--force-reason", "user accepts the push left out"), 2)
        session.record_user_prompt(self.root, self.key, when=FUTURE)
        self.assertEqual(self._issue_done("--force-reason", "user accepts the push left out"), 0)
        self.assertIn("Bypass of [wrap-checks] recorded (verified)", self.output)
        self.assertFalse(os.path.isfile(self.issue))


if __name__ == "__main__":
    unittest.main()
