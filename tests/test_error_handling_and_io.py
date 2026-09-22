#!/usr/bin/env python3
"""
tests/test_error_handling_and_io.py - Regression tests for CLI error handling,
BOM normalization, and gate constants deduplication.
"""

import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import proc, version
from alongkit.hooks import gates, predicates


class TestCliErrorHandlingAndIo(unittest.TestCase):
    """Hermetic tests for CLI argument validation and file I/O consistency."""

    EXEC = os.path.join(REPO_ROOT, "scripts", "along_exec.py")

    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="along-err-io-")
        self.along_dir = os.path.join(self.repo, ".along")
        self.issues = os.path.join(self.along_dir, "ISSUES")
        self.done = os.path.join(self.issues, "done")
        os.makedirs(self.done, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_01_invalid_numeric_cli_args_exit_code_1(self):
        """Invalid numeric CLI arguments must produce non-zero exit codes and stderr error messages."""
        # --steps expects integer
        res = proc.run_capture(
            [sys.executable, self.EXEC, "scratch", "init", "err-test", "--steps", "abc"],
            cwd=self.repo,
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("--steps expects an integer", res.stderr)

        # --step expects integer
        res = proc.run_capture(
            [sys.executable, self.EXEC, "scratch", "update", "err-test", "--step", "xyz"],
            cwd=self.repo,
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("--step expects an integer", res.stderr)

        # --plan-rev expects integer
        res = proc.run_capture(
            [sys.executable, self.EXEC, "scratch", "update", "err-test", "--plan-rev", "not-a-number"],
            cwd=self.repo,
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("--plan-rev expects an integer", res.stderr)

        # --class expects integer
        res = proc.run_capture(
            [sys.executable, self.EXEC, "circuit", "trip", "--class", "invalid-class"],
            cwd=self.repo,
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("--class expects an integer", res.stderr)

    def test_02_along_issue_done_strips_bom_bytes(self):
        """along issue done must strip leading UTF-8 BOM bytes on disk."""
        issue_content = (
            "\ufeff---\n"
            "protocol: along\n"
            "protocol_version: \"3.9.4\"\n"
            "slug: bom-strip-test\n"
            "type: bug\n"
            "status: in-progress\n"
            "priority: medium\n"
            "created: 2026-09-21\n"
            "updated: 2026-09-21\n"
            "tags: [test]\n"
            "---\n\n"
            "# BOM Strip Test\n\n"
            "Body content.\n"
        )
        src_file = os.path.join(self.issues, "bug--bom-strip-test.md")
        with open(src_file, "w", encoding="utf-8") as f:
            f.write(issue_content)

        res = proc.run_capture(
            [sys.executable, self.EXEC, "issue", "done", "bom-strip-test"],
            cwd=self.repo,
        )
        self.assertEqual(res.returncode, 0, f"{res.stdout}\n{res.stderr}")

        dest_file = os.path.join(self.done, "bug--bom-strip-test.md")
        self.assertTrue(os.path.isfile(dest_file))
        with open(dest_file, "rb") as f:
            raw_bytes = f.read()

        self.assertFalse(raw_bytes.startswith(b"\xef\xbb\xbf"), "BOM bytes must not be present in closed issue")

    def test_03_gate_constants_deduplicated(self):
        """alongkit.hooks.gates must share identical constant definitions with predicates."""
        self.assertEqual(gates.TypographyGate.GOVERNED_SUFFIXES, predicates.GOVERNED_TYPOGRAPHY_SUFFIXES)
        self.assertEqual(gates.ProjectionProtectionGate.PROTECTED_PROJECTIONS, predicates.PROTECTED_PROJECTIONS)
        self.assertEqual(gates.CliSafetyGate.DANGEROUS_PATTERNS, predicates.DANGEROUS_CLI_PATTERNS)

    def test_04_version_threshold_constants_defined(self):
        """Milestone version comparison constants must be defined and correct."""
        self.assertEqual(version.V2_0_0, (2, 0, 0))
        self.assertEqual(version.V2_2_9, (2, 2, 9))
        self.assertEqual(version.V2_2_26, (2, 2, 26))
        self.assertEqual(version.V3_0_0, (3, 0, 0))
        self.assertEqual(version.V3_1_0, (3, 1, 0))


if __name__ == "__main__":
    unittest.main()
