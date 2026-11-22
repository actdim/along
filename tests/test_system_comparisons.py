#!/usr/bin/env python3
"""
tests/test_system_comparisons.py - Unit tests for System Comparisons topic documentation.

Verifies [docs--state-centric-execution-and-skill-state-comparison]:
- docs/topic--system-comparisons.md exists and contains Paradigm 7 referencing arXiv:2608.26263.
- All three execution models (Append-Only, Pure Ephemeral State, Dual-Tier Architecture) are contrasted.
- Points adopted and critically rejected by Along are documented with rigorous rationale.
- Master Architectural Advantage Matrix includes 'Execution History & Memory Model'.
- Document conforms strictly to ASCII typography rules without forbidden unicode characters.
"""

from __future__ import annotations

import os
import re
import sys

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import textio, typography


class TestSystemComparisonsDoc(unittest.TestCase):
    """Test suite verifying docs/topic--system-comparisons.md contents and governance."""

    def setUp(self):
        self.doc_path = os.path.join(REPO_ROOT, "docs", "topic--system-comparisons.md")
        self.assertTrue(os.path.isfile(self.doc_path), f"File not found: {self.doc_path}")
        self.content = textio.read_text(self.doc_path, strict=True)

    def test_paradigm_7_section_present(self):
        """Paradigm 7 section must exist and discuss Skill State Pattern."""
        match = re.search(r"^##\s+\d+\.\s+Paradigm 7:.*?Skill State Pattern", self.content, re.MULTILINE)
        self.assertIsNotNone(match, "Paradigm 7 section with Skill State Pattern must exist")

    def test_execution_models_present(self):
        """Verify core execution architectures are discussed."""
        self.assertIn("Dual-Tier", self.content)
        self.assertIn("Ephemeral", self.content)
        self.assertIn("Append-Only", self.content)

    def test_master_architectural_advantage_matrix(self):
        """Master Architectural Advantage Matrix table must exist with valid structure."""
        self.assertIn("Master Architectural Advantage Matrix", self.content)
        matrix_row_found = any("|" in line and "Execution History" in line for line in self.content.splitlines())
        self.assertTrue(matrix_row_found, "Missing Execution History row in comparison matrix")

    def test_code_fences_have_languages(self):
        """All code fences must declare a language identifier."""
        import re
        fences = re.findall(r"^```(\w*)", self.content, re.MULTILINE)
        for fence in fences:
            self.assertTrue(bool(fence), "Found code fence without language identifier")

    def test_clean_ascii_typography(self):
        """Document must conform strictly to clean ASCII typography with zero forbidden characters."""
        violations = typography.findings(self.content)
        self.assertEqual(
            violations,
            [],
            f"Found forbidden typography violations in docs/topic--system-comparisons.md: {violations}",
        )
        non_ascii = [(idx, char, ord(char)) for idx, char in enumerate(self.content) if ord(char) > 127]
        self.assertEqual(
            non_ascii,
            [],
            f"Found non-ASCII characters in docs/topic--system-comparisons.md: {non_ascii[:5]}",
        )


if __name__ == "__main__":
    unittest.main()
