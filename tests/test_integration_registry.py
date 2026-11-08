#!/usr/bin/env python3
"""tests/test_integration_registry.py - Unit and parity tests for integration test registry."""

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
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_SCRIPT = os.path.join(REPO_ROOT, ".along", "scripts", "test.py")

from _integration import INTEGRATION_MODULES, INTEGRATION_TESTS

spec = importlib.util.spec_from_file_location("along_test_runner", TEST_SCRIPT)
test_runner = importlib.util.module_from_spec(spec)
sys.modules["along_test_runner"] = test_runner
spec.loader.exec_module(test_runner)


class TestIntegrationRegistry(unittest.TestCase):

    def test_all_registered_modules_exist(self):
        for mod in INTEGRATION_MODULES:
            path = os.path.join(TESTS_DIR, f"{mod}.py")
            self.assertTrue(
                os.path.isfile(path),
                f"Registry names module '{mod}', but {path} does not exist",
            )

    def test_all_registered_tests_exist(self):
        for tid in INTEGRATION_TESTS:
            parts = tid.split(".", 1)
            mod_name = parts[0]
            path = os.path.join(TESTS_DIR, f"{mod_name}.py")
            self.assertTrue(
                os.path.isfile(path),
                f"Registry names test '{tid}', but module {path} does not exist",
            )

    def test_filter_suite_exclude_integration(self):
        class _SampleUnit(unittest.TestCase):
            __module__ = "test_sample_unit"
            def test_quick(self):
                pass

        class _SampleIntegration(unittest.TestCase):
            __module__ = "test_sample_integration"
            def test_heavy(self):
                pass

        loader = unittest.TestLoader()
        suite = unittest.TestSuite([
            loader.loadTestsFromTestCase(_SampleUnit),
            loader.loadTestsFromTestCase(_SampleIntegration),
        ])
        self.assertEqual(suite.countTestCases(), 2)

        import _integration
        orig_mods = _integration.INTEGRATION_MODULES
        try:
            _integration.INTEGRATION_MODULES = frozenset({"test_sample_integration"})
            filtered = test_runner._filter_suite_exclude_integration(suite)
            self.assertEqual(filtered.countTestCases(), 1)
        finally:
            _integration.INTEGRATION_MODULES = orig_mods

    def test_unit_cli_flag_execution(self):
        cmd = [sys.executable, TEST_SCRIPT, "-q", "--unit", "test_cli_chdir.py"]
        env = dict(os.environ, ALONG_TEST_RUNNER="1")
        res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, env=env)
        self.assertEqual(res.returncode, 0, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        self.assertIn("Ran 9 tests", res.stdout + res.stderr)


if __name__ == "__main__":
    unittest.main()

