#!/usr/bin/env python3
"""
tests/test_shell_classification.py - Segment-aware read-only command classification.

Regression suite for [bug--safe-command-prefix-bypass]: the plan-approval gate used to
treat a whole command line as a safe read when it merely started with `ls`/`echo` or
contained `pytest` anywhere.
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
from alongkit.hooks.adapters.claude import ClaudeCodeAdapter
from alongkit.hooks.shellparse import is_read_only_command, split_segments

READ_ONLY = (
    "ls",
    "ls -la src",
    "git status",
    "git diff HEAD~1",
    "git log -n 5",
    "along test",
    "along kb-search \"worktree isolation\"",
    "pytest -q",
    "python -m unittest",
    "python -m pytest -q tests",
    "python .along/scripts/test.py -q",
    "python .along\\scripts\\test.py",
    "uv run --python 3.12 --with ruamel.yaml python .along/scripts/test.py",
    "npm test",
    "npm run test:quiet",
    "cargo test -q",
    "dotnet test -v q",
    "cat README.md | head -20",
    "grep -rn foo src 2>/dev/null",
    "pytest -q 2>&1 | tail -5",
    "echo \"a; rm -rf src\"",
    "cd src && ls",
    "python --version",
    "python -c \"print(1)\"",
    "Get-ChildItem src",
    "dir",
    # [bug--shell-classifier-residual-bypasses]: no false positives from the new rules.
    "pytest -q 2>&1 | tail -5 &",
    "git log --oneline 2>&1",
    "git branch",
    "git branch -a -vv",
    "git branch --show-current",
    "git branch --list \"feat/*\"",
    "git diff --stat",
    "python -c \"print('a; b')\"",
    "python -c \"print(1 + 2, 'x')\"",
)

MUTATING = (
    "rm -rf src",
    "ls && rm -rf src",
    "rm -rf src; pytest",
    "ls || rm -rf src",
    "cat README.md | tee src/a.py",
    "echo hi > src/a.py",
    "echo hi >> src/a.py",
    "cat > src/a.py",
    "ls $(rm -rf src)",
    "ls `rm -rf src`",
    "echo \"$(rm -rf src)\"",
    "ls; Remove-Item -Recurse src",
    "Get-Content a.txt | Set-Content src/b.txt",
    "Get-Content a.txt | Out-File src/b.txt",
    "npm run build",
    "git commit -m x",
    "git push",
    "python scripts/mutate.py",
    "pytest -q\nrm -rf src",
    "echo 'unbalanced",
    # [bug--shell-classifier-residual-bypasses]
    "ls & rm -rf src",
    "dir & del /s /q src",
    "pytest -q & Remove-Item -Recurse src",
    "echo hi &> src/a.py",
    "python -c \"print(1); import shutil; shutil.rmtree('src')\"",
    "python -c \"print(__import__('os').remove('src/a.py'))\"",
    "python -c \"print(open('src/a.py', 'w').write('x'))\"",
    "python -c \"import os\"",
    "git branch -D main",
    "git branch -m old new",
    "git branch --delete main",
    "git branch --set-upstream-to=origin/main",
    "git branch new-branch",
    "git diff --output=src/a.py",
    "git log --output src/a.py",
    "git show --output=src/a.py HEAD",
)


class TestReadOnlyClassification(unittest.TestCase):
    def test_read_only_commands(self):
        for cmd in READ_ONLY:
            with self.subTest(cmd=cmd):
                self.assertTrue(is_read_only_command(cmd), f"expected read-only: {cmd!r}")

    def test_mutating_commands(self):
        for cmd in MUTATING:
            with self.subTest(cmd=cmd):
                self.assertFalse(is_read_only_command(cmd), f"expected mutating: {cmd!r}")

    def test_operators_inside_quotes_do_not_split(self):
        self.assertEqual(split_segments("echo \"a && b; c | d\""), ["echo \"a && b; c | d\""])
        self.assertEqual(split_segments("ls && pwd; git status"), ["ls", "pwd", "git status"])

    def test_single_ampersand_splits_but_redirect_ampersand_does_not(self):
        self.assertEqual(split_segments("ls & rm -rf src"), ["ls", "rm -rf src"])
        self.assertEqual(split_segments("pytest 2>&1"), ["pytest 2>&1"])
        self.assertEqual(split_segments("echo hi &> out.txt"), ["echo hi &> out.txt"])
        self.assertEqual(split_segments("echo \"a & b\""), ["echo \"a & b\""])


class TestPlanApprovalGateEndToEnd(unittest.TestCase):
    """Claude adapter + engine, repository in inquiry phase (no approved plan)."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along-shell-class-")
        os.makedirs(os.path.join(self.root, ".along", "ISSUES"))
        os.makedirs(os.path.join(self.root, "src"))
        with open(os.path.join(self.root, "AGENTS.md"), "w", encoding="utf-8") as f:
            f.write("# fixture\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _decide(self, command):
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                   "tool_input": {"command": command}, "cwd": self.root}
        event = ClaudeCodeAdapter().parse(json.dumps(payload))
        return evaluate_event(event, repo_root=self.root).decision

    def test_review_evidence_is_denied(self):
        for cmd in ("rm -rf src", "ls && rm -rf src", "rm -rf src; pytest", "echo hi > src/a.py",
                    "ls & rm -rf src", "git branch -D main",
                    "python -c \"print(1); import shutil; shutil.rmtree('src')\""):
            with self.subTest(cmd=cmd):
                self.assertEqual(self._decide(cmd), GateDecision.DENY)

    def test_plain_reads_are_allowed(self):
        for cmd in ("ls", "git status", "pytest -q"):
            with self.subTest(cmd=cmd):
                self.assertEqual(self._decide(cmd), GateDecision.ALLOW)


if __name__ == "__main__":
    unittest.main(verbosity=2)
