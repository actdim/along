#!/usr/bin/env python3
"""
tests/test_subagent_denials.py - Attribution of gate denials to subagents.

Regression test suite for [feat--gate-denials-subagent-attribution]:
- Adapters extract subagent id and role from runtime payloads;
- Audit logs and session ledger retain subagent provenance;
- format_denials, check_unresolved_denials, and along gates denials display subagent context;
- along gates stats compiles subagent breakdown for blocked gates.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import gatestats, session, textio
from alongkit.commands import gates as gates_cmd
from alongkit.hooks import HookEvent, HookEventType, HookMode
from alongkit.hooks.adapters.antigravity import AntigravityAdapter
from alongkit.hooks.adapters.claude import ClaudeCodeAdapter
from alongkit.hooks.config import record_audit_entry
from alongkit.hooks.models import GateDecision, GateResult
from alongkit.hooks.predicates import _record_denial_event, check_unresolved_denials
from hermetic import make_repo_fixture

_SAD_SLUG = "work"
_SAD_KEY = session.session_key("antigravity", "sess-test")
_SAD_ISSUE_TEXT = """---
protocol: along
slug: work
type: feat
status: in-progress
priority: medium
created: 2026-11-06
updated: 2026-11-06
---

# Subagent Denial Test Work
"""


class TestAdapterSubagentExtraction(unittest.TestCase):
    def test_antigravity_adapter_extracts_subagent_dict(self):
        adapter = AntigravityAdapter()
        payload = {
            "toolCall": {"name": "run_command", "args": {"CommandLine": "rm -rf /"}},
            "subagent": {"id": "sub-101", "role": "Codebase Researcher"},
        }
        event = adapter.parse(json.dumps(payload))
        self.assertEqual(event.subagent_id, "sub-101")
        self.assertEqual(event.subagent_role, "Codebase Researcher")

    def test_antigravity_adapter_extracts_camel_case_fields(self):
        adapter = AntigravityAdapter()
        payload = {
            "toolCall": {"name": "run_command", "args": {}},
            "subagentId": "sub-202",
            "agentRole": "Database Debugger",
        }
        event = adapter.parse(json.dumps(payload))
        self.assertEqual(event.subagent_id, "sub-202")
        self.assertEqual(event.subagent_role, "Database Debugger")

    def test_antigravity_adapter_extracts_subagent_string(self):
        adapter = AntigravityAdapter()
        payload = {
            "toolCall": {"name": "run_command", "args": {}},
            "subagent": "Image Generator",
        }
        event = adapter.parse(json.dumps(payload))
        self.assertIsNone(event.subagent_id)
        self.assertEqual(event.subagent_role, "Image Generator")

    def test_claude_adapter_extracts_subagent(self):
        adapter = ClaudeCodeAdapter()
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "npm test"},
            "subagent": {"id": "sub-303", "role": "Architect"},
        }
        event = adapter.parse(json.dumps(payload))
        self.assertEqual(event.subagent_id, "sub-303")
        self.assertEqual(event.subagent_role, "Architect")


class TestGateStatsSubagentAttribution(unittest.TestCase):
    def setUp(self):
        self.root = make_repo_fixture(prefix="along-subagent-stats-", with_docs=False)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_record_audit_entry_and_gatestats_collect(self):
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": "echo test"},
            workspace_root=self.root,
            runtime="antigravity",
            subagent_id="sub-1",
            subagent_role="Codebase Researcher",
        )
        result = GateResult(
            decision=GateDecision.DENY,
            reason="Command blocked",
            gate_name="cli_safety",
        )
        record_audit_entry(self.root, event, result, HookMode.ENFORCE)

        # Second denial from another subagent
        event2 = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            workspace_root=self.root,
            runtime="antigravity",
            subagent_role="Database Debugger",
        )
        record_audit_entry(self.root, event2, result, HookMode.ENFORCE)

        stats = {r.gate: r for r in gatestats.collect(self.root)}
        self.assertIn("cli_safety", stats)
        cli_stats = stats["cli_safety"]
        self.assertEqual(cli_stats.blocked, 2)
        self.assertEqual(cli_stats.subagents.get("Codebase Researcher"), 1)
        self.assertEqual(cli_stats.subagents.get("Database Debugger"), 1)

        table = gatestats.format_table(list(stats.values()))
        self.assertIn("subagents", table)
        self.assertIn("Codebase Researcher:1", table)
        self.assertIn("Database Debugger:1", table)


class TestSubagentDenialReporting(unittest.TestCase):
    def setUp(self):
        self.root = make_repo_fixture(prefix="along-subagent-denial-", with_docs=False)
        issue_path = os.path.join(self.root, ".along", "ISSUES", f"feat--{_SAD_SLUG}.md")
        textio.write_text(issue_path, _SAD_ISSUE_TEXT)
        session.init_session(self.root, _SAD_SLUG)
        self.env = mock.patch.dict(os.environ, {
            "ALONG_SESSION_KEY": _SAD_KEY,
            "ALONG_ISSUE_SLUG": _SAD_SLUG,
            "ALONG_RUNTIME": "antigravity",
            "ALONG_SESSION_ID": "sess-test",
        }, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_subagent_denial_trace_and_diagnostic_message(self):
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": "git push --force"},
            workspace_root=self.root,
            runtime="antigravity",
            subagent_id="sub-42",
            subagent_role="Codebase Researcher",
        )

        _record_denial_event(
            event=event,
            repo_root=self.root,
            key=_SAD_KEY,
            gate="destructive_command",
            reason="Force push is forbidden",
            procedural=False,
        )

        denials = session.denial_status(self.root, _SAD_SLUG)
        self.assertEqual(len(denials), 1)
        item = denials[0]
        self.assertEqual(item["agent"], "Codebase Researcher")
        self.assertEqual(item["subagent_role"], "Codebase Researcher")
        self.assertEqual(item["subagent_id"], "sub-42")

        formatted = session.format_denials(denials)
        self.assertIn("by subagent 'Codebase Researcher'", formatted)

        stop_event = HookEvent(
            event_type=HookEventType.STOP,
            workspace_root=self.root,
            runtime="antigravity",
        )
        msg = check_unresolved_denials(stop_event, self.root)
        self.assertIsNotNone(msg)
        self.assertIn("Turn Completion Rejected [gate: unresolved-gate-denial]", msg)
        self.assertIn("by subagent 'Codebase Researcher'", msg)

        # Test along gates denials output
        out = io.StringIO()
        with redirect_stdout(out):
            gates_cmd._handle_denials(self.root, "denials", ["--slug", _SAD_SLUG])
        self.assertIn("(subagent: Codebase Researcher)", out.getvalue())

        # Test along gates ack settles it
        out_ack = io.StringIO()
        with redirect_stdout(out_ack):
            gates_cmd._handle_denials(self.root, "ack", ["--slug", _SAD_SLUG, item["id"], "--note", "Told user"])
        self.assertEqual(len([d for d in session.denial_status(self.root, _SAD_SLUG) if d["state"] == "open"]), 0)


if __name__ == "__main__":
    unittest.main()
