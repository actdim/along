#!/usr/bin/env python3
"""tests/test_progressive_disclosure.py - Tests for progressive disclosure and context scaling."""

import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import along_kb_search as kb
from alongkit import entities, textio


class TestProgressiveDisclosure(unittest.TestCase):
    def test_generate_knowledge_catalog(self):
        catalog = kb.generate_knowledge_catalog(REPO_ROOT)
        self.assertIn("=== Along Knowledge Catalog & Project Map ===", catalog)
        self.assertIn("Docs Topics", catalog)
        self.assertIn("Active Milestones", catalog)
        self.assertIn("Active ADRs", catalog)
        # Verify compact token footprint (< 250 tokens / ~1000 chars)
        self.assertLess(len(catalog), 1200)

    def test_search_knowledge_base_line_anchors(self):
        results = kb.search_knowledge_base("worktree", repo_root=REPO_ROOT, limit=3)
        self.assertTrue(len(results) > 0)
        top = results[0]
        self.assertIn("#L", top["file_path"])
        self.assertGreaterEqual(top["line_start"], 1)
        self.assertGreaterEqual(top["line_end"], top["line_start"])
        self.assertTrue(len(top["snippet"]) > 0)

    def test_lint_issue_sections(self):
        valid_content = """---
slug: test-issue
---

# Title

## Problem
Some problem.

## Requirements
REQ-1: Do something.

## Acceptance Criteria
- [ ] Done
"""
        missing = entities.lint_issue_sections(valid_content)
        self.assertEqual(missing, [])

        invalid_content = """---
slug: test-issue
---

# Title

## Background
Some background.
"""
        missing = entities.lint_issue_sections(invalid_content)
        self.assertIn("Problem", missing)
        self.assertIn("Requirements or Architecture", missing)
        self.assertIn("Acceptance Criteria", missing)

    def test_requires_frontmatter_in_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, ".along", "ISSUES"), exist_ok=True)
            os.makedirs(os.path.join(tmpdir, "docs"), exist_ok=True)
            textio.write_text(os.path.join(tmpdir, "docs", "topic--domain-model.md"), "# Domain Model\n")
            issue_path = os.path.join(tmpdir, ".along", "ISSUES", "feat--test-requires.md")
            textio.write_text(issue_path, """---
protocol: along
slug: test-requires
type: feat
status: open
priority: medium
requires:
  docs: [topic--domain-model]
---

# Test Requires

## Problem
Testing.

## Requirements
Testing.

## Acceptance Criteria
- [ ] Done
""")
            summary = entities.get_issue_summary(tmpdir, "test-requires")
            self.assertIsNotNone(summary)
            self.assertEqual(summary.get("requires"), {"docs": ["topic--domain-model"]})


if __name__ == "__main__":
    unittest.main()
