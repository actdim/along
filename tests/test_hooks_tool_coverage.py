#!/usr/bin/env python3
"""
tests/test_hooks_tool_coverage.py - Tool-name coverage contract for the runtime adapters.

Regression suite for [bug--claude-adapter-unmapped-tools]: a runtime tool name that no
adapter maps used to fall through unchanged, match no gate, and be allowed, so Claude Code
`MultiEdit` bypassed every write gate and `Grep` never reached `fast_retrieval`.
All evaluations run against throwaway directories.
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

from alongkit.hooks import GateDecision, evaluate_event
from alongkit.hooks.adapters import claude as claude_adapter
from alongkit.hooks.adapters import codex as codex_adapter
from alongkit.hooks.adapters import generic as generic_adapter
from alongkit.hooks.adapters import normalize

#: Claude Code built-in tool names (Claude Code settings documentation, "Tools available to
#: Claude"). Extend this list when Claude Code adds a tool.
CLAUDE_DOCUMENTED_TOOLS = (
    "Agent", "Bash", "BashOutput", "Edit", "ExitPlanMode", "Glob", "Grep", "KillShell",
    "LS", "MultiEdit", "NotebookEdit", "Read", "SlashCommand", "Skill", "Task", "TodoWrite",
    "ToolSearch", "WebFetch", "WebSearch", "Write",
)


def _claude_event(tool_name, tool_input, cwd):
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input,
        "cwd": cwd,
    }
    return claude_adapter.ClaudeCodeAdapter().parse(json.dumps(payload))


class TestAdapterMapsAreCanonical(unittest.TestCase):
    def test_every_documented_claude_tool_is_mapped_or_exempt(self):
        missing = [
            t for t in CLAUDE_DOCUMENTED_TOOLS
            if t not in claude_adapter.TOOL_NAME_MAP and t not in claude_adapter.EXEMPT_TOOLS
        ]
        self.assertEqual(missing, [], f"Claude Code tools neither mapped nor exempt: {missing}")

    def test_adapter_maps_point_at_canonical_names(self):
        for module in (claude_adapter, codex_adapter, generic_adapter):
            for raw, canonical in module.TOOL_NAME_MAP.items():
                self.assertTrue(
                    normalize.is_canonical(canonical),
                    f"{module.__name__}: '{raw}' maps to non-canonical '{canonical}'",
                )


class TestFailClosedGates(unittest.TestCase):
    """A repository with no in-progress issue: every source mutation must be denied."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along-tool-coverage-")
        os.makedirs(os.path.join(self.root, ".along", "ISSUES"))
        os.makedirs(os.path.join(self.root, "src"))
        os.makedirs(os.path.join(self.root, "docs"))
        with open(os.path.join(self.root, "AGENTS.md"), "w", encoding="utf-8") as f:
            f.write("# fixture\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _decide(self, tool_name, tool_input):
        event = _claude_event(tool_name, tool_input, self.root)
        return evaluate_event(event, repo_root=self.root).decision

    def test_write_is_denied_baseline(self):
        target = os.path.join(self.root, "src", "a.py")
        self.assertEqual(self._decide("Write", {"file_path": target, "content": "x = 1\n"}),
                         GateDecision.DENY)

    def test_multiedit_is_denied(self):
        target = os.path.join(self.root, "src", "a.py")
        decision = self._decide("MultiEdit", {
            "file_path": target,
            "edits": [{"old_string": "a", "new_string": "b"}],
        })
        self.assertEqual(decision, GateDecision.DENY)

    def test_notebookedit_is_denied(self):
        target = os.path.join(self.root, "src", "n.ipynb")
        decision = self._decide("NotebookEdit", {"notebook_path": target, "new_source": "print(1)"})
        self.assertEqual(decision, GateDecision.DENY)

    def test_grep_over_docs_triggers_fast_retrieval(self):
        event = _claude_event("Grep", {"pattern": "x", "path": os.path.join(self.root, "docs")}, self.root)
        result = evaluate_event(event, repo_root=self.root)
        self.assertEqual(result.decision, GateDecision.DENY)
        self.assertIn("fast-retrieval", result.reason or "")

    def test_grep_over_source_is_allowed(self):
        event = _claude_event("Grep", {"pattern": "x", "path": os.path.join(self.root, "src")}, self.root)
        self.assertEqual(evaluate_event(event, repo_root=self.root).decision, GateDecision.ALLOW)

    def test_unknown_writing_tool_is_treated_as_a_write(self):
        target = os.path.join(self.root, "src", "a.py")
        decision = self._decide("FancyWriter", {"file_path": target, "content": "x = 1\n"})
        self.assertEqual(decision, GateDecision.DENY)

    def test_unknown_read_tool_is_allowed_and_audited(self):
        self.assertEqual(self._decide("Frobnicate", {"query": "x"}), GateDecision.ALLOW)
        audit = os.path.join(self.root, ".along", "diagnostics", "hooks_audit.jsonl")
        self.assertTrue(os.path.exists(audit), "unmapped tool was not audited")
        with open(audit, encoding="utf-8") as f:
            entries = [json.loads(line) for line in f if line.strip()]
        self.assertTrue(any(e.get("gate") == "unmapped_tool" and "Frobnicate" in (e.get("reason") or "")
                            for e in entries))


if __name__ == "__main__":
    unittest.main(verbosity=2)
