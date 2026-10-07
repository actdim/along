#!/usr/bin/env python3
"""
tests/test_lifecycle_test_evidence.py - [bug--lifecycle-test-false-pass].

Covers: runner output that shows zero executed tests failing `along test` (distill and raw
mode) and never being recorded green, .NET test detection requiring a solution or a test
project, a nested context running the enclosing context's hook, and documentation edits not
re-arming test-before-stop unless the gate sets `count_docs`. Throwaway directories only.
"""

from __future__ import annotations

import os
import shutil
import subprocess
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

from alongkit import lifecycle, session, testruns, textio
from alongkit.hooks import HookEvent, HookEventType
from alongkit.hooks import predicates

CLEAN_ENV = {k: v for k, v in os.environ.items() if k not in session.SESSION_ENV_VARS}


class TestExecutedTests(unittest.TestCase):
    """REQ-1: the runner summary decides; silence is unknown, not zero."""

    def test_counts(self):
        cases = {
            "Ran 0 tests in 0.000s\n\nOK\n": 0,
            "....\nRan 12 tests in 0.4s\n\nOK\n": 12,
            "===== no tests ran in 0.01s =====\n": 0,
            "===== 5 passed in 0.20s =====\n": 5,
            "Total tests: 0\n": 0,
            "Passed!  - Failed:     0, Passed:    12, Skipped:     0, Total:    12\n": 12,
            "running 0 tests\ntest result: ok.\nrunning 3 tests\n": 3,
            "No test files found, exiting with code 0\n": 0,
            "Build succeeded.\n": None,
            "": None,
        }
        for output, expected in cases.items():
            with self.subTest(output=output):
                self.assertEqual(lifecycle.executed_tests(output), expected)


class TestNoTestsIsNotAPass(unittest.TestCase):

    def setUp(self):
        self.env = mock.patch.dict(os.environ, CLEAN_ENV, clear=True)
        self.env.start()
        self.root = tempfile.mkdtemp(prefix="along_no_tests_")
        os.makedirs(os.path.join(self.root, ".along", "ISSUES"))
        subprocess.run(["git", "init", "-q", self.root], check=True)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def _cmd(self, text: str):
        return [sys.executable, "-c", f"print({text!r})"]

    def test_zero_tests_fail_in_both_modes_and_are_not_green(self):
        for mode in ("distill", "raw"):
            with self.subTest(mode=mode):
                code = lifecycle.run_lifecycle_command("test", self._cmd("Ran 0 tests in 0.000s"),
                                                       self.root, mode)
                self.assertEqual(code, lifecycle.NO_TESTS_EXIT_CODE)
                self.assertFalse(testruns.load_runs(self.root)[-1]["ok"])

    def test_real_run_stays_green(self):
        code = lifecycle.run_lifecycle_command("test", self._cmd("Ran 3 tests in 0.1s"), self.root, "distill")
        self.assertEqual(code, 0)
        self.assertTrue(testruns.load_runs(self.root)[-1]["ok"])


class TestDotnetDetection(unittest.TestCase):
    """REQ-2."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along_dotnet_")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_library_project_alone_detects_no_test_command(self):
        textio.write_text(os.path.join(self.root, "Lib.csproj"), "<Project Sdk=\"Microsoft.NET.Sdk\"/>\n")
        self.assertEqual(lifecycle.detect_lifecycle_action(self.root, "test"), (None, False))
        self.assertEqual(lifecycle.detect_lifecycle_action(self.root, "build"), ("dotnet build -v q", True))

    def test_test_project_or_solution_is_the_target(self):
        textio.write_text(os.path.join(self.root, "Lib.Tests.csproj"),
                          "<Project><ItemGroup><PackageReference Include=\"Microsoft.NET.Test.Sdk\"/>"
                          "</ItemGroup></Project>\n")
        self.assertEqual(lifecycle.detect_lifecycle_action(self.root, "test"),
                         ("dotnet test Lib.Tests.csproj -v q", True))
        textio.write_text(os.path.join(self.root, "App.sln"), "\n")
        self.assertEqual(lifecycle.detect_lifecycle_action(self.root, "test"), ("dotnet test App.sln -v q", True))


class TestEnclosingHook(unittest.TestCase):
    """REQ-3."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along_enclosing_")
        os.makedirs(os.path.join(self.root, ".git"))
        textio.write_text(os.path.join(self.root, ".along", "scripts", "test.py"), "print('ok')\n")
        os.makedirs(os.path.join(self.root, ".along", "ISSUES"))
        self.sub = os.path.join(self.root, "Lib")
        os.makedirs(os.path.join(self.sub, ".along", "ISSUES"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_nested_context_uses_enclosing_hook(self):
        ctx, script = lifecycle.enclosing_hook(self.sub, "test")
        self.assertEqual(os.path.normcase(ctx), os.path.normcase(os.path.abspath(self.root)))
        self.assertTrue(script.endswith(os.path.join(".along", "scripts", "test.py")))
        self.assertIsNone(lifecycle.enclosing_hook(self.root, "test"))

    def test_nested_repository_does_not_climb(self):
        os.makedirs(os.path.join(self.sub, ".git"))
        self.assertIsNone(lifecycle.enclosing_hook(self.sub, "test"))


class TestDocEditsAndTestBeforeStop(unittest.TestCase):
    """REQ-4."""

    def setUp(self):
        self.env = mock.patch.dict(os.environ, CLEAN_ENV, clear=True)
        self.env.start()
        self.tmp = tempfile.mkdtemp(prefix="along-doc-edits-")
        os.makedirs(os.path.join(self.tmp, ".along", "scripts"))

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _edit(self, rel: str) -> None:
        predicates.record_tool_activity(HookEvent(
            event_type=HookEventType.POST_TOOL_USE, tool_name="write_to_file",
            tool_args={"TargetFile": os.path.join(self.tmp, rel), "CodeContent": "x\n"},
            workspace_root=self.tmp), repo_root=self.tmp)

    def _stop(self, **options):
        return predicates.check_test_before_stop(
            HookEvent(event_type=HookEventType.STOP, workspace_root=self.tmp), repo_root=self.tmp,
            options={"enforce_unbound": True, **options})

    def test_classification(self):
        for rel in ("README.md", "docs/topic--x.md", "pkg/docs/diagram.svg", "CHANGELOG.md"):
            self.assertTrue(predicates.is_doc_edit(rel), rel)
            self.assertFalse(predicates.is_source_edit(rel), rel)
        for rel in ("src/app.py", ".along/ISSUES/feat--x.md", ".along/scripts/test.py"):
            self.assertFalse(predicates.is_doc_edit(rel), rel)

    def test_doc_edit_needs_no_test_run_unless_count_docs(self):
        self._edit("docs/topic--x.md")
        self.assertIsNone(self._stop())
        self.assertIn("test-before-stop", self._stop(count_docs=True))
        self._edit("src/app.py")
        self.assertIn("test-before-stop", self._stop())


if __name__ == "__main__":
    unittest.main()
