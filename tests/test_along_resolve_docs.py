#!/usr/bin/env python3
"""
tests/test_along_resolve_docs.py - Unit and end-to-end tests for along resolve --docs.

Covers [feat--docs-semantic-conflict-resolution]:
- Conflict hunk parsing (2-way, 3-way, fence isolation, Setext underline protection)
- Structural reconcilers (sections, checklists, bullet lists, tables)
- Link integrity and heading anchor validation
- End-to-end conflict resolution and Knowledge Base synchronization
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

import argparse
import unittest
from typing import List

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import markdown, repo, resolve, textio
import along_resolve
from tests import hermetic


class TestConflictHunkParser(unittest.TestCase):
    """Test fence-aware conflict hunk parsing and edge case handling."""

    def test_parse_standard_two_way_conflict(self):
        content = (
            "# Intro\n\n"
            "<<<<<<< ours\n"
            "Section Alpha\n"
            "=======\n"
            "Section Beta\n"
            ">>>>>>> theirs\n\n"
            "# Outro\n"
        )
        chunks, clean = resolve.parse_conflict_hunks(content)
        self.assertTrue(clean)
        self.assertEqual(len(chunks), 3)
        self.assertIsInstance(chunks[0], str)
        self.assertIsInstance(chunks[1], resolve.ConflictHunk)
        self.assertIsInstance(chunks[2], str)

        hunk = chunks[1]
        self.assertEqual(hunk.ours_label, "ours")
        self.assertEqual(hunk.theirs_label, "theirs")
        self.assertEqual(hunk.ours, ["Section Alpha\n"])
        self.assertEqual(hunk.theirs, ["Section Beta\n"])
        self.assertIsNone(hunk.base)

    def test_parse_three_way_diff3_conflict(self):
        content = (
            "<<<<<<< HEAD\n"
            "Ours content\n"
            "||||||| merged common ancestors\n"
            "Base content\n"
            "=======\n"
            "Theirs content\n"
            ">>>>>>> feature\n"
        )
        chunks, clean = resolve.parse_conflict_hunks(content)
        self.assertTrue(clean)
        self.assertEqual(len(chunks), 1)
        hunk = chunks[0]
        self.assertIsInstance(hunk, resolve.ConflictHunk)
        self.assertEqual(hunk.ours, ["Ours content\n"])
        self.assertEqual(hunk.base, ["Base content\n"])
        self.assertEqual(hunk.theirs, ["Theirs content\n"])
        self.assertEqual(hunk.base_label, "merged common ancestors")

    def test_ignore_markers_inside_code_fences(self):
        content = (
            "# Guide\n\n"
            "```markdown\n"
            "<<<<<<< HEAD\n"
            "Code example\n"
            "=======\n"
            "Code example 2\n"
            ">>>>>>> feature\n"
            "```\n\n"
            "Trailing prose.\n"
        )
        chunks, clean = resolve.parse_conflict_hunks(content)
        self.assertTrue(clean)
        # Should be treated as plain text, no conflict hunks
        self.assertEqual(len(chunks), 1)
        self.assertIsInstance(chunks[0], str)
        self.assertEqual(chunks[0], content)

    def test_setext_heading_underline_is_not_treated_as_conflict_separator(self):
        content = (
            "Heading Title\n"
            "=============\n\n"
            "Paragraph text.\n"
        )
        chunks, clean = resolve.parse_conflict_hunks(content)
        self.assertTrue(clean)
        self.assertEqual(len(chunks), 1)
        self.assertIsInstance(chunks[0], str)


class TestStructuralReconcilers(unittest.TestCase):
    """Test structural reconciliation for sections, checklists, bullet lists, and tables."""

    def test_reconcile_non_overlapping_sections(self):
        ours = ["## Section A\n", "Content A.\n\n"]
        theirs = ["## Section B\n", "Content B.\n\n"]
        merged = resolve.reconcile_markdown_sections(ours, theirs)
        self.assertIsNotNone(merged)
        merged_str = "".join(merged)
        self.assertIn("## Section A\nContent A.", merged_str)
        self.assertIn("## Section B\nContent B.", merged_str)

    def test_reconcile_checklists_with_completion_priority(self):
        ours = [
            "- [ ] Item 1\n",
            "- [ ] Item 2\n",
        ]
        theirs = [
            "- [x] Item 1\n",
            "- [ ] Item 3\n",
        ]
        merged = resolve.reconcile_markdown_lists(ours, theirs)
        self.assertIsNotNone(merged)
        merged_str = "".join(merged)
        # Item 1 must be marked completed [x] because theirs completed it
        self.assertIn("- [x] Item 1\n", merged_str)
        self.assertIn("- [ ] Item 2\n", merged_str)
        self.assertIn("- [ ] Item 3\n", merged_str)

    def test_reconcile_bullet_lists_union(self):
        ours = [
            "- Alpha\n",
            "- Beta\n",
        ]
        theirs = [
            "- Beta\n",
            "- Gamma\n",
        ]
        merged = resolve.reconcile_markdown_lists(ours, theirs)
        self.assertIsNotNone(merged)
        merged_str = "".join(merged)
        self.assertEqual(merged_str, "- Alpha\n- Beta\n- Gamma\n")

    def test_reconcile_markdown_tables(self):
        ours = [
            "| Command | Description |\n",
            "| :--- | :--- |\n",
            "| `along init` | Scaffold project |\n",
        ]
        theirs = [
            "| Command | Description |\n",
            "| :--- | :--- |\n",
            "| `along build` | Run build hook |\n",
        ]
        merged = resolve.reconcile_markdown_tables(ours, theirs)
        self.assertIsNotNone(merged)
        merged_str = "".join(merged)
        self.assertIn("| Command | Description |\n", merged_str)
        self.assertIn("| :--- | :--- |\n", merged_str)
        self.assertIn("| `along init` | Scaffold project |\n", merged_str)
        self.assertIn("| `along build` | Run build hook |\n", merged_str)

    def test_unresolvable_prose_retains_conflict_markers(self):
        hunk = resolve.ConflictHunk(
            start_line=1,
            end_line=5,
            ours=["This sentence describes our approach.\n"],
            theirs=["This sentence describes their completely different approach.\n"],
            base=None,
            ours_label="branch-a",
            theirs_label="branch-b",
        )
        resolved, clean, method = resolve.reconcile_hunk(hunk)
        self.assertFalse(clean)
        self.assertEqual(method, "unresolved")
        self.assertIn("<<<<<<< branch-a\n", resolved)
        self.assertIn("=======\n", resolved)
        self.assertIn(">>>>>>> branch-b\n", resolved)


class TestLinkIntegrityAndAnchors(unittest.TestCase):
    """Test heading anchor extraction and link integrity verification."""

    def test_extract_heading_anchors(self):
        text = (
            "# Main Title\n\n"
            "## First Section\n\n"
            "### Deep Subsection ##\n\n"
            "```markdown\n"
            "## Ignored Heading In Code\n"
            "```\n\n"
            "## First Section\n"
        )
        anchors = markdown.extract_heading_anchors(text)
        self.assertIn("main-title", anchors)
        self.assertIn("first-section", anchors)
        self.assertIn("deep-subsection", anchors)
        self.assertIn("first-section-1", anchors)
        self.assertNotIn("ignored-heading-in-code", anchors)

    def test_find_broken_links_detects_dangling_anchor(self):
        with hermetic.repo_fixture() as root:
            file_path = os.path.join(root, "docs", "topic--test.md")
            content = (
                "# Test Topic\n\n"
                "See [Architecture](#valid-anchor) and [Broken](#nonexistent-anchor).\n\n"
                "## Valid Anchor\n\n"
                "Target content.\n"
            )
            broken = markdown.find_broken_links(content, file_path, root)
            self.assertEqual(len(broken), 1)
            self.assertEqual(broken[0]["target"], "#nonexistent-anchor")

    def test_find_broken_links_detects_forbidden_file_scheme(self):
        with hermetic.repo_fixture() as root:
            file_path = os.path.join(root, "docs", "topic--test.md")
            content = "# Topic\n\n[Forbidden](file:///path/to/file.md)\n"
            broken = markdown.find_broken_links(content, file_path, root)
            self.assertEqual(len(broken), 1)
            self.assertIn("file://", broken[0]["reason"])


class TestEndToEndResolution(unittest.TestCase):
    """Test end-to-end execution of along resolve --docs."""

    def test_resolve_conflicted_file_in_fixture(self):
        with hermetic.repo_fixture() as root:
            target_file = os.path.join(root, "docs", "topic--conflict.md")
            conflicted_content = (
                "---\n"
                "protocol: along\n"
                "slug: conflict-test\n"
                "type: topic\n"
                "---\n\n"
                "# Conflict Test Topic\n\n"
                "<<<<<<< ours\n"
                "## Section Added By Ours\n\n"
                "Ours detailed explanations.\n\n"
                "- [ ] Task 1\n"
                "=======\n"
                "## Section Added By Theirs\n\n"
                "Theirs detailed explanations.\n\n"
                "- [x] Task 1\n"
                "- [ ] Task 2\n"
                ">>>>>>> theirs\n"
            )
            textio.write_text(target_file, conflicted_content)

            # Execute resolution directly on target file
            clean, notes = along_resolve.resolve_file(target_file, root, dry_run=False, strict=True)
            self.assertTrue(clean)

            resolved_text = textio.read_text(target_file)
            self.assertNotIn("<<<<<<<", resolved_text)
            self.assertNotIn("=======", resolved_text)
            self.assertNotIn(">>>>>>>", resolved_text)
            self.assertIn("## Section Added By Ours", resolved_text)
            self.assertIn("## Section Added By Theirs", resolved_text)
            self.assertIn("- [x] Task 1", resolved_text)
            self.assertIn("- [ ] Task 2", resolved_text)


if __name__ == "__main__":
    unittest.main()
