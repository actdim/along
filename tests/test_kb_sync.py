#!/usr/bin/env python3
"""
tests/test_kb_sync.py - Hermetic behavioral unit tests for Knowledge Base pipeline.

Focus:
1. TopicDictionary: multi-term sorting, word boundaries, alias prioritization.
2. Cross-Link Engine: first-per-section replacement, masking links, spans, fences, headings.
3. AST Code Symbol Grounding: symbol extraction from codebase, ghost symbol detection.
4. Structured Section Taxonomy: validation of required H2 sections and non-empty bodies.
5. CLI Integration: --crosslink-check, --crosslink-apply, --strict-sections, --check-symbols.
"""

from __future__ import annotations

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in (SCRIPTS_DIR, TESTS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hermetic
from alongkit import kb, proc, textio
import along_kb_sync


class TestTopicDictionary(unittest.TestCase):
    """Unit tests for TopicDictionary term indexing and matching."""

    def test_topic_dictionary_sorting_and_aliases(self):
        articles = [
            {
                "slug": "topic--architecture",
                "title": "System Architecture",
                "filename": "topic--architecture.md",
                "tags": ["core-engine"],
            },
            {
                "slug": "topic--domain-model",
                "title": "Domain Model",
                "filename": "topic--domain-model.md",
                "tags": [],
            },
        ]
        td = kb.TopicDictionary.build_from_articles(articles)
        # Should contain entries
        self.assertGreaterEqual(len(td.entries), 2)
        # Longest terms should precede shorter terms
        terms = [term for term, _ in td.sorted_terms]
        self.assertGreaterEqual(len(terms), 2)
        for i in range(len(terms) - 1):
            self.assertGreaterEqual(len(terms[i]), len(terms[i + 1]))

    def test_topic_dictionary_self_slug_exclusion(self):
        articles = [
            {
                "slug": "topic--architecture",
                "title": "System Architecture",
                "filename": "topic--architecture.md",
                "tags": [],
            },
        ]
        td = kb.TopicDictionary.build_from_articles(articles)
        # For topic--architecture itself, entries matching its own target should be excluded
        filtered = td.get_entries_for_slug("topic--architecture")
        for entry in filtered:
            self.assertNotEqual(entry.target, "topic--architecture.md")


class TestCrossLinkEngine(unittest.TestCase):
    """Unit tests for deterministic cross-link scanning and application."""

    def setUp(self):
        self.td = kb.TopicDictionary()
        self.td.add_entry("Architecture", "./topic--architecture.md", "topic--architecture")
        self.td.add_entry("Domain Model", "./topic--domain-model.md", "topic--domain-model")

    def test_apply_crosslinks_basic_and_idempotent(self):
        doc = (
            "---\n"
            "protocol: along\n"
            "slug: topic--intro\n"
            "---\n\n"
            "# Introduction\n\n"
            "## Section One\n\n"
            "This project follows a clean Architecture pattern.\n"
            "The Architecture is modular.\n\n"
            "## Section Two\n\n"
            "Here we consult the Architecture again.\n"
        )
        updated, count = kb.apply_crosslinks(doc, self.td, current_slug="topic--intro")
        self.assertEqual(count, 2)
        self.assertIn("[Architecture](./topic--architecture.md) pattern", updated)
        # In Section One, second occurrence is untouched
        self.assertIn("The Architecture is modular", updated)
        # In Section Two, first occurrence is linked
        self.assertIn("consult the [Architecture](./topic--architecture.md) again", updated)

        # Idempotence: re-applying should make zero new modifications
        re_applied, re_count = kb.apply_crosslinks(updated, self.td, current_slug="topic--intro")
        self.assertEqual(re_count, 0)
        self.assertEqual(re_applied, updated)

    def test_apply_crosslinks_masks_spans_links_fences_and_headings(self):
        doc = (
            "---\n"
            "protocol: along\n"
            "slug: topic--intro\n"
            "---\n\n"
            "# Heading with Architecture in title\n\n"
            "## Section with Domain Model in title\n\n"
            "Already linked: [Domain Model](./topic--domain-model.md).\n"
            "Inline code span: `Architecture`.\n"
            "```python\n"
            "# In code fence:\n"
            "Architecture = 1\n"
            "```\n\n"
            "First unlinked prose mention: Architecture is great.\n"
        )
        updated, count = kb.apply_crosslinks(doc, self.td, current_slug="topic--intro")
        # Only the unlinked prose mention should be linked
        self.assertEqual(count, 1)
        self.assertIn("# Heading with Architecture in title", updated)
        self.assertIn("## Section with Domain Model in title", updated)
        self.assertIn("Already linked: [Domain Model](./topic--domain-model.md)", updated)
        self.assertIn("Inline code span: `Architecture`", updated)
        self.assertIn("Architecture = 1", updated)
        self.assertIn("[Architecture](./topic--architecture.md) is great", updated)

    def test_scan_crosslinks_reports_opportunities(self):
        doc = (
            "---\n"
            "protocol: along\n"
            "slug: topic--intro\n"
            "---\n\n"
            "# Intro\n\n"
            "## Overview\n\n"
            "Mentioning Architecture here.\n"
        )
        candidates = kb.scan_crosslinks("topic--intro.md", doc, self.td, current_slug="topic--intro")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].term, "Architecture")
        self.assertEqual(candidates[0].target, "./topic--architecture.md")
        self.assertEqual(candidates[0].section, "Overview")


class TestAstSymbolGrounding(unittest.TestCase):
    """Unit tests for AST symbol extraction and documentation grounding gate."""

    def test_extract_code_symbols_from_source(self):
        with hermetic.repo_fixture() as root:
            py_path = os.path.join(root, "scripts", "sample_module.py")
            os.makedirs(os.path.dirname(py_path), exist_ok=True)
            textio.write_text(py_path, (
                "GLOBAL_CONFIG = {}\n\n"
                "class EngineRunner:\n"
                "    def execute_step(self):\n"
                "        pass\n\n"
                "async def dispatch_event():\n"
                "    pass\n"
            ))
            symbols = kb.extract_code_symbols(root)
            self.assertIn("GLOBAL_CONFIG", symbols)
            self.assertIn("EngineRunner", symbols)
            self.assertIn("execute_step", symbols)
            self.assertIn("dispatch_event", symbols)

    def test_verify_grounded_symbols_detects_ghosts(self):
        valid_inventory = {"EngineRunner", "execute_step"}
        content = (
            "# Documentation\n\n"
            "Uses `EngineRunner` and method `execute_step`.\n"
            "Also refers to non-existent `ghost_function_missing` and `UnknownClass`.\n"
            "Should ignore standard terms like `True`, `None`, `sys.path`, `--strict`, `test.py`.\n"
        )
        ghosts = kb.verify_grounded_symbols("topic--test.md", content, valid_inventory)
        ghost_names = {g.symbol for g in ghosts}
        self.assertIn("ghost_function_missing", ghost_names)
        self.assertIn("UnknownClass", ghost_names)
        self.assertNotIn("EngineRunner", ghost_names)
        self.assertNotIn("execute_step", ghost_names)
        self.assertNotIn("True", ghost_names)
        self.assertNotIn("sys.path", ghost_names)


class TestSectionTaxonomyContracts(unittest.TestCase):
    """Unit tests for structured section contracts across standard articles."""

    def test_compliant_architecture_article_passes(self):
        content = (
            "---\n"
            "protocol: along\n"
            "slug: topic--architecture\n"
            "type: architecture\n"
            "---\n\n"
            "# Architecture\n\n"
            "## 1. System Topology & Overview\n\n"
            "The system is organized into modular components.\n"
            "Subsystems communicate via strictly typed interfaces.\n\n"
            "## 2. Core Components & Subsystems\n\n"
            "Components include the parser and validator.\n"
            "Each module maintains localized encapsulation.\n\n"
            "## 3. Data Flow and Execution Workflows\n\n"
            "Data flows sequentially through stages.\n"
            "Results are passed down without side effects.\n\n"
            "## 4. Invariants, Failure Modes & Edge Cases\n\n"
            "All operations must maintain zero-byte rollback.\n"
            "Errors trigger immediate clean aborts.\n"
        )
        violations = kb.validate_topic_sections("topic--architecture.md", content, "architecture")
        self.assertEqual(violations, [])

    def test_missing_and_empty_sections_flagged(self):
        # Missing data flow, and invariants is empty
        content = (
            "---\n"
            "protocol: along\n"
            "slug: topic--architecture\n"
            "type: architecture\n"
            "---\n\n"
            "# Architecture\n\n"
            "## System Topology\n\n"
            "Overview line 1.\n"
            "Overview line 2.\n\n"
            "## Core Components\n\n"
            "Components line 1.\n"
            "Components line 2.\n\n"
            "## Invariants & Failure Modes\n\n"
        )
        violations = kb.validate_topic_sections("topic--architecture.md", content, "architecture")
        self.assertGreaterEqual(len(violations), 2)
        errors = [v.error for v in violations]
        self.assertTrue(any("missing required section" in e for e in errors))
        self.assertTrue(any("empty section content" in e for e in errors))


class TestKbSyncCliIntegration(unittest.TestCase):
    """Hermetic behavioral integration tests for along_kb_sync CLI flags."""

    def test_crosslink_check_and_apply_cli(self):
        with hermetic.repo_fixture() as root:
            docs_dir = os.path.join(root, "docs")
            # Create a topic article that mentions Architecture
            sample_article = os.path.join(docs_dir, "topic--sample.md")
            textio.write_text(sample_article, (
                "---\n"
                "protocol: along\n"
                "slug: topic--sample\n"
                "title: Sample Article\n"
                "type: topic\n"
                "tags: []\n"
                "---\n\n"
                "# Sample Article\n\n"
                "## Overview\n\n"
                "This references Architecture in prose.\n"
            ))

            # Run --crosslink-check
            res_check = proc.run_python([
                os.path.join(SCRIPTS_DIR, "along_kb_sync.py"),
                root,
                "--check",
                "--crosslink-check",
            ], cwd=root)
            self.assertEqual(res_check.returncode, 0, res_check.stderr)
            self.assertIn("Cross-Link Scanner identified", res_check.stdout)
            # File should not be modified yet
            c_before = textio.read_text(sample_article)
            self.assertNotIn("[Architecture]", c_before)

            # Run --crosslink-apply
            res_apply = proc.run_python([
                os.path.join(SCRIPTS_DIR, "along_kb_sync.py"),
                root,
                "--crosslink-apply",
            ], cwd=root)
            self.assertEqual(res_apply.returncode, 0, res_apply.stderr)
            self.assertIn("Total cross-links applied: 1", res_apply.stdout)
            c_after = textio.read_text(sample_article)
            self.assertIn("[Architecture](./topic--architecture.md)", c_after)

    def test_strict_sections_cli_fails_on_incomplete_article(self):
        with hermetic.repo_fixture() as root:
            # The default hermetic FIXTURE_TOPIC has no sections
            res = proc.run_python([
                os.path.join(SCRIPTS_DIR, "along_kb_sync.py"),
                root,
                "--check",
                "--strict-sections",
            ], cwd=root)
            self.assertEqual(res.returncode, 1)
            self.assertIn("section contract violation(s)", res.stdout)

    def test_check_symbols_cli_in_strict_mode(self):
        with hermetic.repo_fixture() as root:
            docs_dir = os.path.join(root, "docs")
            test_doc = os.path.join(docs_dir, "topic--symbols.md")
            textio.write_text(test_doc, (
                "---\n"
                "protocol: along\n"
                "slug: topic--symbols\n"
                "title: Symbol Doc\n"
                "type: topic\n"
                "tags: []\n"
                "---\n\n"
                "# Symbol Documentation\n\n"
                "Mentions ghost symbol `totally_imaginary_function_xyz`.\n"
            ))

            # Run with --check-symbols and --strict
            res = proc.run_python([
                os.path.join(SCRIPTS_DIR, "along_kb_sync.py"),
                root,
                "--check",
                "--check-symbols",
                "--strict",
            ], cwd=root)
            self.assertEqual(res.returncode, 1)
            self.assertIn("Grounding Gate detected", res.stdout)
            self.assertIn("ghost symbol(s)", res.stdout)


if __name__ == "__main__":
    unittest.main()
