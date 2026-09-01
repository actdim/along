#!/usr/bin/env python3
"""
tests/test_kb_search.py - Regression tests for the unified knowledge retrieval engine.

Focus: ADR (Architectural Decision Record) parsing in .along/DECISIONS.md.

Background: protocol v2.2.0 replaced numeric ADR headers (`## 011 - Title`) with
decentralized slug headers (`## ADR-YYYY-MM-DD--<slug> - <Title>`) to avoid merge
collisions across parallel branches. The retrieval engine kept the old splitter and
silently returned zero decisions on every v2.2.x repository. These tests pin BOTH
formats so the header schema cannot drift away from the parser again.
"""

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import along_kb_search as kb


SLUG_FORMAT_FIXTURE = """# Decisions (ADR - append-only)

<!-- Template:
## ADR-YYYY-MM-DD--<slug> - <Title>
- Date: YYYY-MM-DD
- Status: accepted            (or: superseded by ADR-YYYY-MM-DD--<slug>)
-->

## ADR-2026-08-15--single-file-append-only-decisions - Single-file append-only log
- Date: 2026-08-15
- Status: accepted
- Context: Deciding between one file and many files.
- Decision: Keep one append-only file.

## ADR-2026-08-31--concurrency-projections - Multi-Branch Concurrency & Projections
- Date: 2026-08-31
- Status: superseded by ADR-2026-09-01--something-newer
- Context: Parallel branches conflict on tracking files.
- Decision: Use merge=union for append-only files.
"""

LEGACY_FORMAT_FIXTURE = """# Decisions (ADR - append-only)

## 001 - Adopt provider-agnostic AGENTS.md
- Date: 2026-08-04
- Status: accepted
- Context: Every agent tool ships its own config format.
- Decision: Standardize on AGENTS.md.

## 011: Numeric header with colon separator
- Date: 2026-08-10
- Status: Superseded by #012
- Decision: Something that was later replaced.

## 2026-08-20 Weekly notes heading that is not an ADR
- This section must not be indexed as a decision record.
"""


class TestAdrParsing(unittest.TestCase):

    def test_01_slug_format_is_parsed(self):
        """Current protocol slug headers must produce one entry per ADR."""
        entries = kb.parse_decision_entries(SLUG_FORMAT_FIXTURE)
        slugs = [e["slug"] for e in entries]

        self.assertEqual(len(entries), 2, f"Expected 2 slug-format ADRs, got {slugs}")
        self.assertIn("adr-2026-08-15--single-file-append-only-decisions", slugs)
        self.assertIn("adr-2026-08-31--concurrency-projections", slugs)

        first = entries[0]
        self.assertEqual(first["category"], "decision")
        self.assertEqual(first["type"], "adr")
        self.assertIn("Single-file append-only log", first["title"])
        self.assertIn("Keep one append-only file", first["body"])

    def test_02_legacy_numeric_format_is_parsed(self):
        """Legacy pre-v2.2.0 numeric headers must keep working for unmigrated repos."""
        entries = kb.parse_decision_entries(LEGACY_FORMAT_FIXTURE)
        slugs = [e["slug"] for e in entries]

        self.assertEqual(len(entries), 2, f"Expected 2 legacy-format ADRs, got {slugs}")
        self.assertEqual(slugs, ["adr-001", "adr-011"])
        self.assertIn("Adopt provider-agnostic AGENTS.md", entries[0]["title"])
        self.assertIn("Numeric header with colon separator", entries[1]["title"])

    def test_02b_iso_date_heading_is_not_an_adr(self):
        """A '## 2026-08-20 ...' heading must not be mistaken for a numeric ADR."""
        entries = kb.parse_decision_entries(LEGACY_FORMAT_FIXTURE)
        for e in entries:
            self.assertNotIn("Weekly notes", e["title"])
            self.assertNotIn("must not be indexed", e["body"])

    def test_03_template_placeholder_is_excluded(self):
        """The schema template header must never surface as a search result."""
        entries = kb.parse_decision_entries(SLUG_FORMAT_FIXTURE)
        for e in entries:
            self.assertNotIn("<", e["slug"], f"Placeholder leaked into results: {e['slug']}")
            self.assertNotIn("yyyy", e["slug"].lower(), f"Placeholder leaked: {e['slug']}")

    def test_04_superseded_status_is_detected_case_insensitively(self):
        """Both 'superseded by ADR-...' (protocol form) and 'Superseded by #N' must be detected."""
        slug_entries = {e["slug"]: e for e in kb.parse_decision_entries(SLUG_FORMAT_FIXTURE)}
        self.assertEqual(slug_entries["adr-2026-08-15--single-file-append-only-decisions"]["status"], "active")
        self.assertEqual(slug_entries["adr-2026-08-31--concurrency-projections"]["status"], "superseded")

        legacy_entries = {e["slug"]: e for e in kb.parse_decision_entries(LEGACY_FORMAT_FIXTURE)}
        self.assertEqual(legacy_entries["adr-001"]["status"], "active")
        self.assertEqual(legacy_entries["adr-011"]["status"], "superseded")

    def test_05_file_path_carries_github_compatible_anchor(self):
        """Deep links must point at a real GitHub heading anchor, not a bare number."""
        entries = kb.parse_decision_entries(SLUG_FORMAT_FIXTURE, rel_path=".along/DECISIONS.md")
        target = entries[0]["file_path"]

        self.assertTrue(target.startswith(".along/DECISIONS.md#"), target)
        anchor = target.split("#", 1)[1]
        self.assertEqual(anchor, kb.github_heading_anchor(
            "ADR-2026-08-15--single-file-append-only-decisions - Single-file append-only log"
        ))
        self.assertNotIn(" ", anchor)
        self.assertNotIn(".", anchor)

    def test_06_github_anchor_algorithm(self):
        """Punctuation is dropped, spaces become hyphens, case is lowered."""
        self.assertEqual(
            kb.github_heading_anchor("ADR-2026-08-15--x - Single-file DECISIONS.md over MADR/Nygard"),
            "adr-2026-08-15--x---single-file-decisionsmd-over-madrnygard",
        )


class TestLiveRepositoryRetrieval(unittest.TestCase):
    """Guards against silent format drift between the protocol and the parser."""

    def test_07_real_decisions_log_is_searchable(self):
        decisions_path = os.path.join(REPO_ROOT, ".along", "DECISIONS.md")
        if not os.path.exists(decisions_path):
            self.skipTest("No .along/DECISIONS.md in this repository")

        with open(decisions_path, "r", encoding="utf-8") as f:
            raw = f.read()

        entries = kb.parse_decision_entries(raw)
        self.assertGreater(
            len(entries), 0,
            "ADR splitter parsed zero decisions from the live .along/DECISIONS.md. "
            "The header format and the parser have drifted apart."
        )

        collected = [e for e in kb.collect_all_entries(REPO_ROOT) if e["category"] == "decision"]
        self.assertEqual(
            len(collected), len(entries),
            "collect_all_entries() must surface every ADR that parse_decision_entries() finds."
        )

    def test_08_decision_category_search_returns_results(self):
        decisions_path = os.path.join(REPO_ROOT, ".along", "DECISIONS.md")
        if not os.path.exists(decisions_path):
            self.skipTest("No .along/DECISIONS.md in this repository")

        results = kb.search_knowledge_base(
            "decisions", repo_root=REPO_ROOT, limit=5, category="decision"
        )
        self.assertGreater(
            len(results), 0,
            "/along-kb-search --category decision returned no ADRs from the live decision log."
        )
        for r in results:
            self.assertEqual(r["category"], "decision")


if __name__ == "__main__":
    unittest.main()
