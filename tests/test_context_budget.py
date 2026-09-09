#!/usr/bin/env python3
"""
tests/test_context_budget.py - Tests for context budget measurement and CLI tooling.

Ensures that:
1. alongkit.budget correctly measures files, tokens, and context categories.
2. `along context-budget --json` outputs compliant JSON.
3. `along context-budget --check` returns correct exit codes based on compliance.
4. The test respects hermetic invariants (no REPO_ROOT in command list literals).
"""

from __future__ import annotations

import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import budget, proc
from tests import hermetic


class TestContextBudgetEngine(unittest.TestCase):

    def test_estimate_tokens_ratio(self):
        chars = 380
        self.assertEqual(budget.estimate_tokens(chars), 100)

    def test_measure_file_nonexistent(self):
        self.assertIsNone(budget.measure_file("/nonexistent/file/path.md"))

    def test_measure_file_real(self):
        with hermetic.repo_fixture() as fixture:
            sample_path = os.path.join(fixture, "AGENTS.md")
            info = budget.measure_file(sample_path, fixture)
            self.assertIsNotNone(info)
            self.assertEqual(info["path"], "AGENTS.md")
            self.assertGreater(info["bytes"], 0)
            self.assertGreater(info["chars"], 0)
            self.assertGreater(info["tokens"], 0)
            self.assertGreater(info["lines"], 0)

    def test_measure_context_fixture(self):
        with hermetic.repo_fixture() as fixture:
            report = budget.measure_context(fixture)
            self.assertEqual(report["protocol"], "along")
            self.assertIn("auto_loaded", report["categories"])
            self.assertIn("mandatory_session_start", report["categories"])
            self.assertIn("per_skill", report["categories"])
            self.assertIn("checks", report)
            self.assertTrue(isinstance(report["all_passed"], bool))

    def test_live_repo_budget_compliance(self):
        """Guard against context overhead creep in the live repository (REQ-2)."""
        report = budget.measure_context(REPO_ROOT)
        for name, check in report["checks"].items():
            self.assertTrue(
                check["passed"],
                f"Context budget violation on {name}: actual {check['actual']} B exceeds limit {check['limit']} B"
            )
        self.assertTrue(report["all_passed"], "Live repo must satisfy all context budget limits")

    def test_agents_md_hard_size_limit(self):
        """AGENTS.md MUST stay under 14 KB (REQ-4 of debt--agents-md-context-budget-pruning)."""
        agents_md = os.path.join(REPO_ROOT, "AGENTS.md")
        size = os.path.getsize(agents_md)
        self.assertLess(
            size, 14336,
            f"AGENTS.md is {size} bytes, exceeds 14 KB budget ceiling (14336 B)"
        )

    def test_protocol_md_hard_size_limit(self):
        """Canonical template MUST stay under 14 KB (REQ-4)."""
        protocol_md = os.path.join(REPO_ROOT, "skills", "along-init", "protocol.md")
        size = os.path.getsize(protocol_md)
        self.assertLess(
            size, 14336,
            f"protocol.md is {size} bytes, exceeds 14 KB budget ceiling (14336 B)"
        )


class TestContextBudgetCLI(unittest.TestCase):

    def test_cli_human_readable_output(self):
        with hermetic.repo_fixture() as fixture:
            exec_script = os.path.join(SCRIPTS_DIR, "along_exec.py")
            res = proc.run_python([exec_script, "context-budget"], cwd=fixture)
            self.assertTrue(res.ok, f"context-budget failed: {res.stderr}")
            self.assertIn("Along Context Budget Report", res.stdout)
            self.assertIn("Auto-loaded files", res.stdout)
            self.assertIn("Mandatory Session-Start", res.stdout)

    def test_cli_json_output(self):
        with hermetic.repo_fixture() as fixture:
            exec_script = os.path.join(SCRIPTS_DIR, "along_exec.py")
            res = proc.run_python([exec_script, "context-budget", "--json"], cwd=fixture)
            self.assertTrue(res.ok, f"context-budget --json failed: {res.stderr}")
            parsed = json.loads(res.stdout)
            self.assertEqual(parsed["protocol"], "along")
            self.assertIn("categories", parsed)
            self.assertIn("auto_loaded", parsed["categories"])

    def test_cli_check_mode_exit_codes(self):
        with hermetic.repo_fixture() as fixture:
            exec_script = os.path.join(SCRIPTS_DIR, "along_exec.py")
            # Fixture is small and should pass default budget checks
            res = proc.run_python([exec_script, "context-budget", "--check"], cwd=fixture)
            self.assertEqual(res.returncode, 0, f"check failed: {res.stderr}\n{res.stdout}")

            # Artificially blow up ISSUES.md in fixture to trigger check failure
            huge_board = os.path.join(fixture, ".along", "ISSUES.md")
            with open(huge_board, "w", encoding="utf-8") as f:
                f.write("# Huge Board\n" + ("- [x] item\n" * 1000))

            res_fail = proc.run_python([exec_script, "context-budget", "--check"], cwd=fixture)
            self.assertEqual(res_fail.returncode, 1, "check should have failed with exit code 1")


if __name__ == "__main__":
    unittest.main()
