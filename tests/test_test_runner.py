#!/usr/bin/env python3
"""tests/test_test_runner.py - Unit and regression tests for Along test runner and Pytest bridge."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import unittest

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_SCRIPT = os.path.join(REPO_ROOT, ".along", "scripts", "test.py")

# Dynamically import test.py helpers for direct unit testing
spec = importlib.util.spec_from_file_location("along_test_runner", TEST_SCRIPT)
test_runner = importlib.util.module_from_spec(spec)
sys.modules["along_test_runner"] = test_runner
spec.loader.exec_module(test_runner)


class DummyTestOne(unittest.TestCase):
    def test_alpha(self):
        pass

    def test_beta(self):
        pass


class DummyTestTwo(unittest.TestCase):
    def test_gamma(self):
        pass


class TestTestRunnerHelpers(unittest.TestCase):
    def test_normalize_target_pytest_double_colon(self):
        target = "tests/test_foo.py::TestClass::test_method"
        self.assertEqual(
            test_runner._normalize_test_target(target),
            "test_foo.TestClass.test_method"
        )

    def test_normalize_target_windows_backslashes(self):
        target = "tests\\test_foo.py::TestClass::test_method"
        self.assertEqual(
            test_runner._normalize_test_target(target),
            "test_foo.TestClass.test_method"
        )

    def test_normalize_target_colon_syntax(self):
        target = "test_foo.py:TestClass.test_method"
        self.assertEqual(
            test_runner._normalize_test_target(target),
            "test_foo.TestClass.test_method"
        )

    def test_normalize_target_class_only(self):
        target = "tests/test_foo.py::TestClass"
        self.assertEqual(
            test_runner._normalize_test_target(target),
            "test_foo.TestClass"
        )

    def test_normalize_target_raw_file(self):
        target = "tests/test_foo.py"
        self.assertEqual(
            test_runner._normalize_test_target(target),
            "test_foo.py"
        )

    def test_normalize_target_already_dotted(self):
        target = "test_foo.TestClass.test_method"
        self.assertEqual(
            test_runner._normalize_test_target(target),
            "test_foo.TestClass.test_method"
        )

    def test_filter_suite_by_pattern_exact_and_case_insensitive(self):
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(DummyTestOne)
        self.assertEqual(suite.countTestCases(), 2)

        # Filter for alpha
        filtered_alpha = test_runner._filter_suite_by_pattern(suite, "alpha")
        self.assertEqual(filtered_alpha.countTestCases(), 1)

        # Filter case-insensitive
        filtered_beta = test_runner._filter_suite_by_pattern(suite, "BETA")
        self.assertEqual(filtered_beta.countTestCases(), 1)

        # Filter with no match
        filtered_none = test_runner._filter_suite_by_pattern(suite, "nonexistent")
        self.assertEqual(filtered_none.countTestCases(), 0)

    def test_filter_nested_suite(self):
        loader = unittest.TestLoader()
        suite = unittest.TestSuite([
            loader.loadTestsFromTestCase(DummyTestOne),
            loader.loadTestsFromTestCase(DummyTestTwo),
        ])
        self.assertEqual(suite.countTestCases(), 3)

        filtered = test_runner._filter_suite_by_pattern(suite, "gamma")
        self.assertEqual(filtered.countTestCases(), 1)

    def test_filter_suite_retains_failed_test_import_errors(self):
        failed_test = unittest.loader._FailedTest("test_bad", Exception("Module failed to import"))
        suite = unittest.TestSuite([failed_test])
        filtered = test_runner._filter_suite_by_pattern(suite, "nonexistent_pattern_xyz")
        self.assertEqual(filtered.countTestCases(), 1)
        self.assertIn(failed_test, list(filtered))


class TestTestRunnerSubprocessExecution(unittest.TestCase):
    def _run_test_runner(self, args: list[str]) -> subprocess.CompletedProcess:
        cmd = [sys.executable, TEST_SCRIPT] + args
        env = dict(os.environ, ALONG_TEST_RUNNER="1")
        return subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_pytest_node_selector_execution(self):
        res = self._run_test_runner(["tests/test_cli_chdir.py::TestCliChdir::test_chdir_chained"])
        self.assertEqual(res.returncode, 0, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        self.assertIn("Ran 1 test", res.stdout + res.stderr)

    def test_colon_selector_execution(self):
        res = self._run_test_runner(["test_cli_chdir.py:TestCliChdir.test_chdir_chained"])
        self.assertEqual(res.returncode, 0, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        self.assertIn("Ran 1 test", res.stdout + res.stderr)

    def test_pattern_filtering_with_k_flag(self):
        res = self._run_test_runner(["test_cli_chdir.py", "-k", "test_chdir_chained"])
        self.assertEqual(res.returncode, 0, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        self.assertIn("Ran 1 test", res.stdout + res.stderr)

    def test_zero_test_safeguard_nonexistent_file_exits_1(self):
        res = self._run_test_runner(["nonexistent_test_module_xyz.py"])
        self.assertNotEqual(res.returncode, 0, "test.py must exit non-zero when 0 tests are collected")
        self.assertIn("No tests collected", res.stdout + res.stderr)

    def test_zero_test_safeguard_unmatched_pattern_exits_1(self):
        res = self._run_test_runner(["test_cli_chdir.py", "-k", "nonexistent_pattern_12345"])
        self.assertNotEqual(res.returncode, 0, "test.py must exit non-zero when pattern matches 0 tests")
        self.assertIn("No tests collected", res.stdout + res.stderr)


if __name__ == "__main__":
    unittest.main()
