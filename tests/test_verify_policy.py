#!/usr/bin/env python3
"""
tests/test_verify_policy.py - Declared test policy and the shared test gate.

Covers [bug--test-gate-no-tests-policy]: `verify.tests` = required | none in
`.along/config.json`, a misconfigured hook reported as such (not as failing tests), counting
executed tests from coloured output, and the documentation-only commit skip. Every test runs
in a throwaway fixture; fake hooks stand in for npm / vitest.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import gates, lifecycle, textio, verify
from hermetic import make_repo_fixture

COMMIT = os.path.join(SCRIPTS_DIR, "along_commit.py")
DEBT = """---
protocol: along
slug: add-tests
type: debt
status: open
priority: low
created: 2026-10-11
updated: 2026-10-11
---

# Add tests
"""


class _Fixture(unittest.TestCase):
    def setUp(self):
        self.root = make_repo_fixture(prefix="along-verify-", with_docs=False)
        textio.write_text(os.path.join(self.root, "package.json"),
                          json.dumps({"name": "fixture", "version": "1.0.0", "scripts": {"build": "tsc"}}) + "\n")
        textio.write_text(os.path.join(self.root, ".along", "ISSUES", "debt--add-tests.md"), DEBT)
        self.scripts = os.path.join(self.root, ".along", "scripts")
        os.makedirs(self.scripts, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def hook(self, name, body):
        textio.write_text(os.path.join(self.scripts, f"{name}.py"), "import sys\n" + body + "\n")

    def policy(self, **verify_block):
        textio.write_text(os.path.join(self.root, ".along", "config.json"),
                          json.dumps({"verify": verify_block}) + "\n")

    def missing_npm_script_hook(self):
        # Fixture A: the generated hook runs `npm test` and there is no test script.
        self.hook("test", "print('-> Running: npm test')\n"
                          "sys.stderr.write('npm error Missing script: \"test\"\\n')\nsys.exit(1)")

    def build_hook(self):
        marker = os.path.join(self.root, "build-ran.txt").replace("\\", "/")
        self.hook("build", f"open('{marker}', 'w').write('ok')")
        return marker


class TestPolicyNone(_Fixture):
    def test_none_with_tracking_issue_runs_checks_instead_of_tests(self):
        self.missing_npm_script_hook()
        marker = self.build_hook()
        self.policy(tests="none", reason="prototype without tests", tracked_by="debt--add-tests", checks=["build"])
        self.assertEqual(gates.run_test_gate(self.root, "T"), gates.TESTS_PASSED)
        self.assertTrue(os.path.isfile(marker))

    def test_failing_check_fails_the_gate(self):
        self.hook("build", "sys.exit(2)")
        self.policy(tests="none", reason="r", tracked_by="debt--add-tests", checks=["build"])
        self.assertEqual(gates.run_test_gate(self.root, "T"), gates.TESTS_FAILED)

    def test_none_without_reason_or_tracking_issue_is_invalid(self):
        for block in ({"tests": "none", "tracked_by": "debt--add-tests"},
                      {"tests": "none", "reason": "r"},
                      {"tests": "none", "reason": "r", "tracked_by": "debt--nowhere"},
                      {"tests": "sometimes"}):
            with self.subTest(block=block):
                self.policy(**block)
                self.assertEqual(gates.run_test_gate(self.root, "T"), gates.TESTS_POLICY_INVALID)

    def test_describe_names_reason_and_issue(self):
        self.policy(tests="none", reason="prototype", tracked_by="debt--add-tests")
        self.assertEqual(verify.load_policy(self.root).describe(), "tests: none - prototype (debt--add-tests)")


class TestPolicyRequired(_Fixture):
    def test_missing_npm_script_is_a_misconfiguration_with_a_hint(self):
        self.missing_npm_script_hook()
        self.assertEqual(gates.run_test_gate(self.root, "T"), gates.TESTS_MISCONFIGURED)
        self.assertIn("verify.tests", verify.misconfiguration_message("x"))
        self.assertEqual(verify.misconfiguration('npm error Missing script: "test"', 1), 'npm script "test" not found')

    def test_coloured_silent_vitest_summary_is_counted(self):
        # Fixture B: `npm test -- --silent` with vitest, colour codes around the counts.
        self.hook("test", "print('-> Running: npm test -- --silent')\n"
                          "print('\\x1b[32m Test Files \\x1b[39m 2 passed (2)')\n"
                          "print('\\x1b[32m      Tests \\x1b[39m\\x1b[1m\\x1b[32m 5 passed\\x1b[39m\\x1b[22m (5)')")
        self.assertEqual(gates.run_test_gate(self.root, "T"), gates.TESTS_PASSED)
        self.assertEqual(lifecycle.executed_tests("\x1b[32m5 passed\x1b[39m"), 5)

    def test_zero_executed_tests_fail(self):
        self.hook("test", "print('Ran 0 tests in 0.000s')")
        self.assertEqual(gates.run_test_gate(self.root, "T"), gates.TESTS_NONE_EXECUTED)

    def test_silent_npm_script_resolving_to_a_known_runner_counts_as_none(self):
        textio.write_text(os.path.join(self.root, "package.json"),
                          json.dumps({"scripts": {"test": "vitest run"}}) + "\n")
        self.assertEqual(lifecycle.tests_ran(["npm", "test"], "", self.root), 0)
        self.assertIsNone(lifecycle.tests_ran(["npm", "test"], ""))

    def test_declared_required_without_any_test_command_is_misconfigured(self):
        self.policy(tests="required")
        self.assertEqual(gates.run_test_gate(self.root, "T"), gates.TESTS_MISCONFIGURED)

    def test_undeclared_policy_without_tests_keeps_the_old_skip(self):
        self.assertEqual(gates.run_test_gate(self.root, "T"), gates.TESTS_SKIPPED)

    def test_node_detection_drops_silent_and_needs_a_test_script(self):
        self.assertNotEqual(lifecycle.detect_lifecycle_action(self.root, "test")[0], "npm test")
        textio.write_text(os.path.join(self.root, "package.json"), json.dumps({"scripts": {"test": "vitest run"}}))
        self.assertEqual(lifecycle.detect_lifecycle_action(self.root, "test"), ("npm test", True))


class TestDocsOnlyChange(unittest.TestCase):
    def test_classification(self):
        self.assertTrue(verify.docs_only_change(".", ["README.md", "docs/a.png", ".along/ISSUES/x.md", "llms.txt"]))
        self.assertFalse(verify.docs_only_change(".", ["README.md", "src/app.ts"]))
        self.assertFalse(verify.docs_only_change(".", [".along/scripts/test.py"]))
        self.assertFalse(verify.docs_only_change(".", []))
        self.assertFalse(verify.docs_only_change(".", ["requirements.txt"]))
        self.assertFalse(verify.docs_only_change(".", ["constraints.txt"]))
        self.assertFalse(verify.docs_only_change(".", ["CMakeLists.txt"]))
        self.assertFalse(verify.is_doc_only_path("requirements.txt"))
        self.assertFalse(verify.is_doc_only_path("constraints.txt"))
        self.assertTrue(verify.is_doc_only_path("llms.txt"))
        self.assertTrue(verify.is_doc_only_path("llms-full.txt"))

    def test_nested_along_paths(self):
        # [bug--wrap-docs-only-test-skip] REQ-2: Any .along/ path segment counts as Along state (except .along/scripts/)
        self.assertTrue(verify.is_doc_only_path("apps/server/.along/ISSUES.md"))
        self.assertTrue(verify.is_doc_only_path("apps/server/.along/config.json"))
        self.assertTrue(verify.is_doc_only_path("packages/webmold/.along"))
        self.assertTrue(verify.is_doc_only_path(".along/ISSUES/x.md"))
        self.assertTrue(verify.is_doc_only_path("./.along/config.json"))
        self.assertFalse(verify.is_doc_only_path("apps/server/.along/scripts/test.py"))
        self.assertFalse(verify.is_doc_only_path("apps/server/.along/scripts"))
        self.assertFalse(verify.is_doc_only_path(".along/scripts/test.py"))
        self.assertFalse(verify.is_doc_only_path(".along/scripts"))
        self.assertFalse(verify.is_doc_only_path("src/app.ts"))

        self.assertTrue(verify.docs_only_change(".", ["apps/server/.along/config.json", "docs/guide.md"]))
        self.assertFalse(verify.docs_only_change(".", ["apps/server/.along/scripts/test.py"]))

        # Exclusions: skills, protocol, AGENTS.md, package code are NOT doc-only
        self.assertFalse(verify.is_doc_only_path("skills/along-team/SKILL.md"))
        self.assertFalse(verify.is_doc_only_path("AGENTS.md"))
        self.assertFalse(verify.is_doc_only_path("CLAUDE.md"))
        self.assertFalse(verify.is_doc_only_path("skills/along-init/protocol.md"))
        self.assertFalse(verify.is_doc_only_path("packages/dashboard-ui/README.md"))
        self.assertFalse(verify.is_doc_only_path("scripts/README.md"))
        self.assertTrue(verify.is_doc_only_path("docs/topic--architecture.md"))
        self.assertTrue(verify.is_doc_only_path("README.md"))

    def test_version_only_package_json(self):
        bump = '--- a/package.json\n+++ b/package.json\n@@\n-  "version": "1.0.0",\n+  "version": "1.0.1",\n'
        dep = bump + '+  "left-pad": "1.0.0",\n'
        self.assertTrue(verify.docs_only_change(".", ["package.json", "CHANGELOG.md"], lambda _p: bump))
        self.assertFalse(verify.docs_only_change(".", ["package.json"], lambda _p: dep))


class TestCommitUnderPolicy(_Fixture):
    def setUp(self):
        super().setUp()
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"],
                     ["config", "core.autocrlf", "false"]):
            subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)
        textio.write_text(os.path.join(self.root, "src", "app.js"), "console.log(1);\n")

    def commit(self):
        return subprocess.run([sys.executable, COMMIT, "-i", "add-tests", "-a", "-m", "chore: x"],
                              cwd=self.root, capture_output=True, text=True, encoding="utf-8")

    def test_fixture_a_with_policy_none_commits_without_no_verify(self):
        self.missing_npm_script_hook()
        marker = self.build_hook()
        self.policy(tests="none", reason="prototype", tracked_by="debt--add-tests", checks=["build"])
        res = self.commit()
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertTrue(os.path.isfile(marker))

    def test_fixture_a_without_policy_names_the_misconfiguration(self):
        self.missing_npm_script_hook()
        res = self.commit()
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Test hook misconfigured", res.stderr)
        self.assertIn("verify.tests", res.stderr)
        self.assertNotIn("Fix failing tests", res.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
