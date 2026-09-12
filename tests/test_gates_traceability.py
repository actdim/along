#!/usr/bin/env python3
"""
tests/test_gates_traceability.py - Integration and hermetic tests for Gate Traceability.
"""

from __future__ import annotations

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

from alongkit.hooks.traceability import (
    audit_traceability,
    format_traceability_report,
    scan_prose_anchors,
)


class TestRepositoryGateTraceability(unittest.TestCase):
    """Verifies that the live repository satisfies bi-directional gate traceability."""

    def test_live_repository_traceability_is_clean(self):
        report = audit_traceability(REPO_ROOT)
        report_output = format_traceability_report(report)

        self.assertGreaterEqual(
            report.total_gates,
            11,
            f"Expected at least 11 default gates, found {report.total_gates}\n{report_output}",
        )
        self.assertEqual(
            report.dangling_references,
            [],
            f"Dangling gate references found in prose:\n{report_output}",
        )
        self.assertEqual(
            report.schema_errors,
            [],
            f"Gate schema or predicate handler errors found:\n{report_output}",
        )
        self.assertTrue(report.is_clean, f"Traceability report failed:\n{report_output}")


class TestHermeticTraceabilityScanner(unittest.TestCase):
    """Hermetic unit tests for the scanner's ability to catch defects."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="along-trace-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_catches_dangling_gate_reference(self):
        # Create a dummy skill with an invalid gate badge
        skills_dir = os.path.join(self.tmp, "skills", "fake-skill")
        os.makedirs(skills_dir, exist_ok=True)
        doc_path = os.path.join(skills_dir, "SKILL.md")
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write("# Fake Skill\nRule [gate: ghost-gate-not-in-yaml] must be observed.\n")

        report = audit_traceability(self.tmp)
        self.assertFalse(report.is_clean)
        self.assertEqual(len(report.dangling_references), 1)
        self.assertEqual(report.dangling_references[0].gate_id, "ghost-gate-not-in-yaml")


if __name__ == "__main__":
    unittest.main()
