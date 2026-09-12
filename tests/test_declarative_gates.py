#!/usr/bin/env python3
"""
tests/test_declarative_gates.py - Hermetic tests for Declarative Gate Engine and Predicates.
"""

from __future__ import annotations

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

from alongkit.hooks import (
    GateDecision,
    HookEvent,
    HookEventType,
    HookEngine,
)
from alongkit.hooks.declarative import (
    DeclarativeGate,
    DeclarativeGateDefinition,
    DeclarativeRule,
    load_gate_definitions,
    parse_gate_dict,
)
from alongkit.hooks.predicates import (
    check_active_issue,
    check_cli_safety,
    check_projection_protection,
    check_test_before_stop,
    check_typography,
    check_wrap_before_stop,
    record_tool_activity,
)


class TestDeclarativeGateEngine(unittest.TestCase):
    """Hermetic unit tests for declarative rule evaluation."""

    def test_parse_gate_dict_minimal(self):
        raw = {
            "id": "test_gate",
            "title": "Test Gate",
            "event": "PreToolUse",
            "tools": ["run_command"],
            "rule": {
                "type": "regex_match",
                "field": "CommandLine",
                "pattern": "^test",
                "error": "Must start with test",
            },
        }
        defn = parse_gate_dict(raw)
        self.assertEqual(defn.id, "test_gate")
        self.assertEqual(defn.event_type, HookEventType.PRE_TOOL_USE)
        self.assertEqual(defn.tools, ["run_command"])
        self.assertEqual(len(defn.rules), 1)
        self.assertEqual(defn.rules[0].rule_type, "regex_match")

    def test_regex_match_evaluates_correctly(self):
        raw = {
            "id": "commit_check",
            "event": "PreToolUse",
            "tools": ["run_command"],
            "rule": {
                "type": "regex_match",
                "field": "CommandLine",
                "pattern": r"\[[a-z]+--[a-z0-9-]+\]",
                "error": "Missing issue tag",
            },
        }
        gate = DeclarativeGate(parse_gate_dict(raw))

        # Rejects commit without issue tag
        bad_event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": "git commit -m 'initial commit'"},
        )
        res = gate.evaluate(bad_event)
        self.assertEqual(res.decision, GateDecision.DENY)
        self.assertIn("Missing issue tag", res.reason or "")

        # Allows commit with issue tag
        good_event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": "git commit -m '[feat--auth] initial commit'"},
        )
        res = gate.evaluate(good_event)
        self.assertEqual(res.decision, GateDecision.ALLOW)

    def test_regex_forbidden_rejects_stubs(self):
        raw = {
            "id": "anti_stub",
            "event": "PreToolUse",
            "tools": ["write_to_file"],
            "rule": {
                "type": "regex_forbidden",
                "field": "CodeContent",
                "pattern": r"(?i)//\s*\.\.\.\s*rest",
                "error": "Truncation stub forbidden",
            },
        }
        gate = DeclarativeGate(parse_gate_dict(raw))

        bad_event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"CodeContent": "function foo() {\n  // ... rest of code\n}"},
        )
        res = gate.evaluate(bad_event)
        self.assertEqual(res.decision, GateDecision.DENY)
        self.assertIn("Truncation stub forbidden", res.reason or "")

        good_event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"CodeContent": "function foo() {\n  return 42;\n}"},
        )
        res = gate.evaluate(good_event)
        self.assertEqual(res.decision, GateDecision.ALLOW)


class TestStatefulPredicates(unittest.TestCase):
    """Hermetic tests for stateful gate predicates using isolated tempfiles."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="along-predicates-")
        self.along_dir = os.path.join(self.tmp, ".along")
        os.makedirs(self.along_dir, exist_ok=True)
        self.issues_dir = os.path.join(self.along_dir, "ISSUES")
        os.makedirs(self.issues_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_check_active_issue_enforces_in_progress_issue(self):
        # 1. No issue exists in ISSUES/ -> editing source file is denied
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": "src/app.py", "CodeContent": "x = 1"},
            workspace_root=self.tmp,
        )
        err = check_active_issue(event, repo_root=self.tmp)
        self.assertIsNotNone(err)
        self.assertIn("require-active-issue", err or "")

        # 2. Excluded paths (e.g. creating the issue itself) are allowed
        issue_event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": ".along/ISSUES/feat--test.md", "CodeContent": "content"},
            workspace_root=self.tmp,
        )
        err = check_active_issue(issue_event, repo_root=self.tmp)
        self.assertIsNone(err)

        # 3. Create an active in-progress issue
        issue_path = os.path.join(self.issues_dir, "feat--test.md")
        with open(issue_path, "w", encoding="utf-8") as f:
            f.write("---\nstatus: in-progress\nslug: test\n---\n# Test\n")

        # Now editing source code is allowed
        err = check_active_issue(event, repo_root=self.tmp)
        self.assertIsNone(err)

    def test_check_test_before_stop(self):
        # Record file edit
        edit_event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": "src/app.py", "CodeContent": "x = 2"},
            workspace_root=self.tmp,
        )
        record_tool_activity(edit_event, repo_root=self.tmp)

        # Stop event before tests ran -> rejected
        stop_event = HookEvent(
            event_type=HookEventType.STOP,
            workspace_root=self.tmp,
        )
        err = check_test_before_stop(stop_event, repo_root=self.tmp)
        self.assertIsNotNone(err)
        self.assertIn("test-before-stop", err or "")

        # Record test run
        test_event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": "python .along/scripts/test.py"},
            workspace_root=self.tmp,
        )
        record_tool_activity(test_event, repo_root=self.tmp)

        # Stop event after tests ran -> allowed
        err = check_test_before_stop(stop_event, repo_root=self.tmp)
        self.assertIsNone(err)


if __name__ == "__main__":
    unittest.main()
