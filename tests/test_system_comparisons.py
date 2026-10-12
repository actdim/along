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

    def test_paradigm_7_header_and_paper_reference(self):
        """Paradigm 7 section header must reference SKILL.state and arXiv:2608.26263."""
        expected_header = "## 8. Paradigm 7: Conversational History Accumulation vs. Explicit Execution State (SKILL.state / arXiv:2608.26263)"
        self.assertIn(expected_header, self.content)
        self.assertIn("arXiv:2608.26263", self.content)
        self.assertIn("SKILL.state", self.content)

    def test_three_execution_models_contrasted(self):
        """Verify all three execution architectures are explicitly contrasted."""
        self.assertIn("Append-Only Conversational History", self.content)
        self.assertIn("Pure Ephemeral State Transition", self.content)
        self.assertIn("Along's Dual-Tier State & Provenance Architecture", self.content)

    def test_adopted_aspects_articulated(self):
        """Verify adopted mechanisms: bounded prompt footprints, observation distillation, retry discard, merge operator."""
        self.assertIn("Bounded Prompt Footprints & Linear Token Scaling", self.content)
        self.assertIn("Observation Distillation", self.content)
        self.assertIn("Ephemeral Reasoning Discard in Worker Retry Loops", self.content)
        self.assertIn("Deterministic Runtime Merge Operator with Null-Deletion Semantics", self.content)

    def test_rejected_aspects_articulated(self):
        """Verify critically rejected aspects: sufficient statistic trap, open-model fragility, multi-agent concurrency."""
        self.assertIn("The \"Sufficient Statistic\" Trap / Lost History", self.content)
        self.assertIn("Open-Model Fragility on Pure State Generation", self.content)
        self.assertIn("Destruction of Engineering Provenance", self.content)
        self.assertIn("Single-Agent Simplification vs. Multi-Agent Concurrency", self.content)

    def test_master_architectural_advantage_matrix_row(self):
        """Master Architectural Advantage Matrix must contain 'Execution History & Memory Model' row."""
        self.assertIn("## 9. Master Architectural Advantage Matrix", self.content)
        self.assertIn("**Execution History & Memory Model**", self.content)
        matrix_row_found = False
        for line in self.content.splitlines():
            if "| **Execution History & Memory Model** |" in line:
                matrix_row_found = True
                self.assertIn("Append-only chat bloat", line)
                self.assertIn("Dual-Tier", line)
                break
        self.assertTrue(matrix_row_found, "Missing Execution History & Memory Model row in matrix")

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
