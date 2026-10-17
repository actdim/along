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
    check_entity_deletion_protection,
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

    def test_default_gates_drop_prediction_gates(self):
        # [debt--gate-simplification]: no gate predicts harm from command text or search paths.
        from alongkit.hooks.declarative import DEFAULT_GATES_FILE, load_gate_definitions
        defns = {d.id: d for d in load_gate_definitions(DEFAULT_GATES_FILE)}
        self.assertNotIn("fast_retrieval", defns)
        self.assertNotIn("circuit_breaker", defns)
        plan = defns["require_plan_approval"]
        self.assertEqual(plan.event_type, HookEventType.PRE_TOOL_USE)
        self.assertEqual(plan.extra_events, [HookEventType.STOP])

    def test_event_list_runs_gate_on_each_event(self):
        gate = DeclarativeGate(parse_gate_dict({
            "id": "two_events", "event": ["PreToolUse", "Stop"],
            "rule": {"type": "regex_match", "field": "never", "pattern": "x", "error": "held"},
        }))
        for etype in (HookEventType.PRE_TOOL_USE, HookEventType.STOP):
            with self.subTest(event=etype):
                self.assertEqual(gate.evaluate(HookEvent(event_type=etype)).decision, GateDecision.DENY)
        self.assertEqual(gate.evaluate(HookEvent(event_type=HookEventType.POST_TOOL_USE)).decision,
                         GateDecision.ALLOW)


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
            event_type=HookEventType.POST_TOOL_USE,
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
        err = check_test_before_stop(stop_event, repo_root=self.tmp, options={"enforce_unbound": True})
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
        err = check_test_before_stop(stop_event, repo_root=self.tmp, options={"enforce_unbound": True})
        self.assertIsNone(err)

    def test_check_entity_deletion_protection_blocks_untracked_issue_deletion(self):
        # Create an untracked issue file
        untracked_issue = os.path.join(self.issues_dir, "bug--uncommitted-fix.md")
        with open(untracked_issue, "w", encoding="utf-8") as f:
            f.write("---\nstatus: open\nslug: uncommitted-fix\n---\n# Uncommitted\n")

        # 1. delete_file tool targeting untracked issue is denied
        event_delete_tool = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="delete_file",
            tool_args={"TargetFile": untracked_issue},
            workspace_root=self.tmp,
        )
        err = check_entity_deletion_protection(event_delete_tool, repo_root=self.tmp)
        self.assertIsNotNone(err)
        self.assertIn("entity-reference-integrity", err or "")
        self.assertIn("along issue supersede", err or "")
        self.assertIn("along issue rename", err or "")
        self.assertIn("split: supersede into several keys", err or "")

        # 2. remove_file tool targeting untracked issue is denied
        event_remove_tool = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="remove_file",
            tool_args={"path": untracked_issue},
            workspace_root=self.tmp,
        )
        err = check_entity_deletion_protection(event_remove_tool, repo_root=self.tmp)
        self.assertIsNotNone(err)

        # 3. unlink tool targeting untracked issue is denied
        event_unlink_tool = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="unlink",
            tool_args={"file_path": untracked_issue},
            workspace_root=self.tmp,
        )
        err = check_entity_deletion_protection(event_unlink_tool, repo_root=self.tmp)
        self.assertIsNotNone(err)

        # 4. shell command rm targeting untracked issue is denied
        event_rm_cmd = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": f"rm {untracked_issue}"},
            workspace_root=self.tmp,
        )
        err = check_entity_deletion_protection(event_rm_cmd, repo_root=self.tmp)
        self.assertIsNotNone(err)
        self.assertIn("along issue supersede", err or "")

        # 5. shell command git rm targeting untracked issue is denied
        event_git_rm = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="bash",
            tool_args={"CommandLine": "git rm .along/ISSUES/bug--uncommitted-fix.md"},
            workspace_root=self.tmp,
        )
        err = check_entity_deletion_protection(event_git_rm, repo_root=self.tmp)
        self.assertIsNotNone(err)

        # 6. PowerShell Remove-Item targeting entity is denied
        event_pwsh_rm = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": "Remove-Item -Force .along\\DECISIONS\\ADR-1.md"},
            workspace_root=self.tmp,
        )
        err = check_entity_deletion_protection(event_pwsh_rm, repo_root=self.tmp)
        self.assertIsNotNone(err)

        # 7. Non-deletion command referencing issue file is allowed
        event_cat = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": f"cat {untracked_issue}"},
            workspace_root=self.tmp,
        )
        err = check_entity_deletion_protection(event_cat, repo_root=self.tmp)
        self.assertIsNone(err)

        # 8. Deleting non-entity file is allowed by this gate
        event_del_source = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="delete_file",
            tool_args={"TargetFile": os.path.join(self.tmp, "src", "temp.txt")},
            workspace_root=self.tmp,
        )
        err = check_entity_deletion_protection(event_del_source, repo_root=self.tmp)
        self.assertIsNone(err)

    def test_duplicate_gate_id_rejected(self):
        """Duplicate gate IDs must raise DuplicateGateError at load time."""
        from alongkit.hooks.declarative import DuplicateGateError, load_gate_entries

        dup_yaml = (
            "version: 1\n"
            "gates:\n"
            "  - id: sample_gate\n"
            "    event: PreToolUse\n"
            "    tools: [run_command]\n"
            "    rule:\n"
            "      type: regex_forbidden\n"
            "      pattern: 'foo'\n"
            "  - id: sample_gate\n"
            "    event: Stop\n"
            "    rule:\n"
            "      type: regex_forbidden\n"
            "      pattern: 'bar'\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write(dup_yaml)
            tmp_yaml_path = f.name
        try:
            with self.assertRaises(DuplicateGateError):
                load_gate_entries(tmp_yaml_path)
        finally:
            if os.path.exists(tmp_yaml_path):
                os.remove(tmp_yaml_path)

    def test_both_entity_integrity_gates_coexist(self):
        """PreToolUse entity_deletion_protection and Stop entity_reference_integrity must both load."""
        from alongkit.hooks.declarative import get_all_declarative_gates

        gates = get_all_declarative_gates(repo_root=REPO_ROOT)
        gate_names = {g.name for g in gates}
        self.assertIn("entity_deletion_protection", gate_names)
        self.assertIn("entity_reference_integrity", gate_names)

        del_gate = next(g for g in gates if g.name == "entity_deletion_protection")
        self.assertEqual(del_gate.defn.event_type, HookEventType.PRE_TOOL_USE)

        stop_gate = next(g for g in gates if g.name == "entity_reference_integrity")
        self.assertEqual(stop_gate.defn.event_type, HookEventType.STOP)


if __name__ == "__main__":
    unittest.main()
