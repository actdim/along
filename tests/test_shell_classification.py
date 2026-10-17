#!/usr/bin/env python3
"""
tests/test_shell_classification.py - Shell commands are judged by result, not predicted.

[debt--gate-simplification]: require_plan_approval never classifies a shell command before it
runs (the former classifier asked the user about `git`, `python`, `findstr` ... and still
missed scripts that delete files). Instead the working tree is snapshotted at the user's
message and compared at Stop: files the turn changed without an approved plan are held then.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import session
from alongkit.hooks import GateDecision, evaluate_event
from alongkit.hooks.adapters.claude import ClaudeCodeAdapter
from alongkit.hooks.shellparse import SUBSTITUTION, split_segments, words

#: Commands the former classifier held or asked about; none may raise a plan-gate event now.
SHELL_COMMANDS = (
    "ls -la src",
    "git status",
    "git log -n 5",
    "python scripts/analyze.py",
    "python -c \"import os\"",
    "powershell -NoProfile -Command Get-ChildItem",
    "node tools/report.js",
    "findstr /s needle *.md",
    "Get-Item README.md | Format-Table",
    "(Get-ChildItem src).Count",
    "Get-Content a.txt | Where-Object { $_ -match 'x' }",
    "npm run build",
    "echo hi > src/a.py",
    "git commit -m x",
    "git push",
    "sort -o out.txt names.txt",
)


def _git_run(root, *args):
    subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
                   cwd=root, check=True, capture_output=True)


class TestSplitSegments(unittest.TestCase):
    def test_operators_inside_quotes_do_not_split(self):
        self.assertEqual(split_segments("echo \"a && b; c | d\""), ["echo \"a && b; c | d\""])
        self.assertEqual(split_segments("ls && pwd; git status"), ["ls", "pwd", "git status"])

    def test_single_ampersand_splits_but_redirect_ampersand_does_not(self):
        self.assertEqual(split_segments("ls & rm -rf src"), ["ls", "rm -rf src"])
        self.assertEqual(split_segments("pytest 2>&1"), ["pytest 2>&1"])
        self.assertEqual(split_segments("echo hi &> out.txt"), ["echo hi &> out.txt"])

    def test_substitution_becomes_a_placeholder_word(self):
        self.assertEqual(split_segments("rm -rf $(pwd)/x"), [f"rm -rf {SUBSTITUTION}/x"])
        self.assertEqual(split_segments("echo `date`; ls"), [f"echo {SUBSTITUTION}", "ls"])
        self.assertIsNone(split_segments("echo 'unbalanced"))
        self.assertIsNone(split_segments("echo $(unterminated"))

    def test_words_keep_windows_paths(self):
        self.assertEqual(words("rd /s /q C:\\tmp\\x"), ["rd", "/s", "/q", "C:\\tmp\\x"])


class _GitFixture(unittest.TestCase):
    """Git repository with an unbound session held to plan approval (enforce_unbound)."""

    SESSION = "sess-shell-1"

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along-shell-result-")
        os.makedirs(os.path.join(self.root, ".along", "ISSUES"))
        os.makedirs(os.path.join(self.root, ".along", "rules"))
        os.makedirs(os.path.join(self.root, "src"))
        self._write("AGENTS.md", "# fixture\n")
        self._write("src/app.py", "x = 1\n")
        self._write(".along/rules/gates.yaml",
                    "version: 1\ngates:\n  - id: require_plan_approval\n    enforce_unbound: true\n"
                    "  - id: require_active_issue\n    enabled: false\n")
        _git_run(self.root, "init", "-q")
        _git_run(self.root, "add", "-A")
        _git_run(self.root, "commit", "-q", "-m", "init")
        self._env = {k: os.environ.get(k) for k in session.SESSION_ENV_VARS}
        for k in self._env:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._env.items():
            if v is not None:
                os.environ[k] = v
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def _hook(self, payload):
        payload = {"session_id": self.SESSION, "cwd": self.root, **payload}
        event = ClaudeCodeAdapter().parse(json.dumps(payload))
        return evaluate_event(event, repo_root=self.root)

    def _prompt(self):
        return self._hook({"hook_event_name": "UserPromptSubmit", "prompt": "go"})

    def _stop(self):
        return self._hook({"hook_event_name": "Stop", "stop_hook_active": False})

    def _audit_gates(self):
        path = os.path.join(self.root, ".along", "diagnostics", "hooks_audit.jsonl")
        if not os.path.isfile(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(line)["gate"] for line in f if line.strip()]


class TestShellNeverHeldUpFront(_GitFixture):
    def test_shell_commands_raise_no_plan_gate_event(self):
        for cmd in SHELL_COMMANDS:
            with self.subTest(cmd=cmd):
                self._hook({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                            "tool_input": {"command": cmd}})
        self.assertNotIn("require_plan_approval", self._audit_gates())

    def test_file_tool_write_is_still_held_by_path(self):
        result = self._hook({"hook_event_name": "PreToolUse", "tool_name": "Write",
                             "tool_input": {"file_path": os.path.join(self.root, "src", "b.py"),
                                            "content": "y = 2\n"}})
        self.assertEqual(result.decision, GateDecision.DENY)
        self.assertIn("PLAN_REQUIRED", result.reason)


class TestShellChangesCaughtAtStop(_GitFixture):
    def test_turn_that_changed_source_is_held_at_stop(self):
        self._prompt()
        self._write("src/new.py", "z = 3\n")
        self._write("src/app.py", "x = 2\n")
        result = self._stop()
        self.assertEqual(result.decision, GateDecision.DENY)
        self.assertIn("PLAN_REQUIRED", result.reason)
        self.assertIn("src/new.py", result.reason)
        self.assertIn("src/app.py", result.reason)

    def test_files_dirty_before_the_turn_are_not_attributed(self):
        self._write("src/app.py", "x = 99\n")
        self._prompt()
        self.assertEqual(self._stop().decision, GateDecision.ALLOW)

    def test_file_dirty_before_and_changed_again_is_attributed(self):
        self._write("src/app.py", "x = 99\n")
        self._prompt()
        self._write("src/app.py", "x = 100\n")
        self.assertEqual(self._stop().decision, GateDecision.DENY)

    def test_along_state_and_planning_artifacts_are_not_attributed(self):
        self._prompt()
        self._write(".along/.session/x/plan.md", "# plan\n")
        self._write(".along/HISTORY.md", "- line\n")
        self._write(".along/diagnostics/x.json", "{}\n")
        self._write("docs/INDEX.md", "# Index\n")
        self._write("llms.txt", "x\n")
        result = self._stop()
        self.assertEqual(result.decision, GateDecision.ALLOW, result.reason)

    def test_lifecycle_scripts_under_along_are_code(self):
        self._prompt()
        self._write(".along/scripts/test.py", "print(1)\n")
        self.assertEqual(self._stop().decision, GateDecision.DENY)

    def test_no_baseline_no_hold(self):
        # Runtimes without UserPromptSubmit give no baseline; nothing can be attributed.
        self._write("src/new.py", "z = 3\n")
        self.assertEqual(self._stop().decision, GateDecision.ALLOW)

    def test_stop_hook_active_reports_instead_of_blocking_again(self):
        self._prompt()
        self._write("src/new.py", "z = 3\n")
        payload = {"session_id": self.SESSION, "cwd": self.root, "hook_event_name": "Stop",
                   "stop_hook_active": True}
        adapter = ClaudeCodeAdapter()
        event = adapter.parse(json.dumps(payload))
        code, out = adapter.format_response(evaluate_event(event, repo_root=self.root))
        self.assertEqual(code, 0)
        self.assertIn("PLAN_REQUIRED", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
