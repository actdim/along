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

import io
import os
import sys
import tempfile
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


class TestCollectorSkipReporting(unittest.TestCase):
    """Verify that entity collectors report malformed/skipped files and do not swallow failures."""

    def test_kb_search_reports_skips_and_continues(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            along_dir = os.path.join(tmp_dir, ".along")
            issues_dir = os.path.join(along_dir, "ISSUES")
            os.makedirs(issues_dir, exist_ok=True)

            # Valid entity
            valid_path = os.path.join(issues_dir, "feat--sample-valid.md")
            with open(valid_path, "w", encoding="utf-8") as f:
                f.write("---\nprotocol: along\nslug: sample-valid\ntype: feat\ntitle: Sample Valid\nstatus: open\n---\n# Valid Body\n")

            # Malformed entity (invalid YAML front-matter)
            broken_path = os.path.join(issues_dir, "bug--broken-syntax.md")
            with open(broken_path, "w", encoding="utf-8") as f:
                f.write("---\ntitle: broken: unquoted: colons: [broken\n---\n# Broken\n")

            # Capture stderr
            old_stderr = sys.stderr
            sys.stderr = io.StringIO()
            try:
                entries = kb.collect_all_entries(tmp_dir, verbose=True)
                err_output = sys.stderr.getvalue()
            finally:
                sys.stderr = old_stderr

            # Verify that malformed file was reported on stderr
            self.assertIn("skipped", err_output)
            self.assertIn("bug--broken-syntax.md", err_output)
            self.assertIn("malformed or unreadable file(s) skipped", err_output)

            # Verify that valid file was collected
            valid_entries = [e for e in entries if e.get("slug") == "sample-valid"]
            self.assertEqual(len(valid_entries), 1)
            self.assertEqual(valid_entries[0]["category"], "issue")

            # Verify search functions with the valid entry
            results = kb.search_knowledge_base("valid", repo_root=tmp_dir)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["slug"], "sample-valid")

    def test_dashboard_collector_records_skips(self):
        from dashboard.core.collector import EntityCollector
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp_dir:
            along_dir = Path(tmp_dir) / ".along"
            issues_dir = along_dir / "ISSUES"
            issues_dir.mkdir(parents=True, exist_ok=True)

            # Valid entity
            (issues_dir / "feat--dash-valid.md").write_text(
                "---\nprotocol: along\nslug: dash-valid\ntype: feat\ntitle: Dash Valid\nstatus: open\n---\n# Body\n",
                encoding="utf-8"
            )

            # Broken entity
            (issues_dir / "bug--dash-broken.md").write_text(
                "---\ntitle: broken: [unclosed\n---\n# Broken\n",
                encoding="utf-8"
            )

            collector = EntityCollector(along_dir)
            collector.collect_all()

            self.assertEqual(len(collector.issues), 1)
            self.assertEqual(collector.issues[0].slug, "dash-valid")
            self.assertTrue(len(collector.skipped_entities) >= 1)
            skipped_paths = [s[0] for s in collector.skipped_entities]
            self.assertTrue(any("bug--dash-broken.md" in p for p in skipped_paths))


class TestRelevanceAndRanking(unittest.TestCase):
    """Relevance and ranking fixture tests (REQ-1, REQ-2, REQ-3, REQ-4, REQ-5, REQ-7)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo_root = self.tmp.name
        docs_dir = os.path.join(self.repo_root, "docs")
        issues_dir = os.path.join(self.repo_root, ".along", "ISSUES")
        os.makedirs(docs_dir, exist_ok=True)
        os.makedirs(issues_dir, exist_ok=True)

        # Doc 1: Has 'concatenate' and 'category', but NOT standalone 'cat'
        with open(os.path.join(docs_dir, "topic--concatenation.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write("---\nprotocol: along\nslug: concatenation\ntitle: String Concatenation\ntype: topic\n---\n"
                    "# String Concatenation\n\nThis article explains how to concatenate strings in various category types.\n")

        # Doc 2: Has standalone 'cat'
        with open(os.path.join(docs_dir, "topic--felines.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write("---\nprotocol: along\nslug: felines\ntitle: Domestic Animals\ntype: topic\n---\n"
                    "# Domestic Animals\n\nThe domestic cat is a small carnivorous mammal.\n")

        # Doc 3: Has alpha and beta
        with open(os.path.join(docs_dir, "topic--alpha-beta.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write("---\nprotocol: along\nslug: alpha-beta\ntitle: Alpha Beta Process\ntype: topic\n---\n"
                    "# Alpha Beta Process\n\nDetailed walkthrough of alpha stage followed by beta verification.\n")

        # Doc 4: Has alpha and gamma (no beta)
        with open(os.path.join(docs_dir, "topic--alpha-gamma.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write("---\nprotocol: along\nslug: alpha-gamma\ntitle: Alpha Gamma Pipeline\ntype: topic\n---\n"
                    "# Alpha Gamma Pipeline\n\nDetailed walkthrough of alpha stage followed by gamma verification.\n")

        # Doc 5: Has exact phrase "single-file append-only"
        with open(os.path.join(issues_dir, "task--phrase-match.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write("---\nprotocol: along\nslug: phrase-match\ntitle: Phrase Matching Task\ntype: task\nstatus: open\n---\n"
                    "# Phrase Matching\n\nWe require a single-file append-only decisions ledger for safety.\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_token_matching_does_not_substring_match(self):
        """Query 'cat' must match standalone 'cat', not 'concatenate' or 'category' (REQ-1)."""
        results = kb.search_knowledge_base("cat", repo_root=self.repo_root)
        matched_slugs = [r["slug"] for r in results]
        self.assertIn("felines", matched_slugs)
        self.assertNotIn("concatenation", matched_slugs)

    def test_and_semantics_by_default(self):
        """Query 'alpha beta' must require BOTH terms by default (REQ-2)."""
        results = kb.search_knowledge_base("alpha beta", repo_root=self.repo_root)
        matched_slugs = [r["slug"] for r in results]
        self.assertIn("alpha-beta", matched_slugs)
        self.assertNotIn("alpha-gamma", matched_slugs)

    def test_or_semantics_with_match_any(self):
        """Query 'beta gamma' with match_any=True must return docs matching either term (REQ-2)."""
        results = kb.search_knowledge_base("beta gamma", repo_root=self.repo_root, match_any=True)
        matched_slugs = [r["slug"] for r in results]
        self.assertIn("alpha-beta", matched_slugs)
        self.assertIn("alpha-gamma", matched_slugs)

    def test_quoted_phrase_search(self):
        """Quoted phrase query must match exact adjacent phrase (REQ-3)."""
        results = kb.search_knowledge_base('"single-file append-only"', repo_root=self.repo_root)
        matched_slugs = [r["slug"] for r in results]
        self.assertEqual(matched_slugs, ["phrase-match"])

    def test_light_stemming_matches_plurals(self):
        """Query 'processes' matches singular 'process' (REQ-1)."""
        results = kb.search_knowledge_base("processes", repo_root=self.repo_root)
        matched_slugs = [r["slug"] for r in results]
        self.assertIn("alpha-beta", matched_slugs)

    def test_search_stats_reporting(self):
        """Stats mode returns corpus entries, estimated tokens, and savings percentage (REQ-5)."""
        results, stats = kb.search_knowledge_base("alpha", repo_root=self.repo_root, return_stats=True)
        self.assertGreater(len(results), 0)
        self.assertEqual(stats["corpus_entries"], 5)
        self.assertGreater(stats["corpus_tokens_est"], 0)
        self.assertGreater(stats["returned_tokens_est"], 0)
        self.assertGreaterEqual(stats["savings_pct"], 0.0)

    def test_snippet_extraction_word_boundaries(self):
        """Snippet extraction preserves word boundaries and does not truncate mid-word (REQ-4)."""
        long_body = "The quick brown fox jumps over the lazy dog repeatedly in an extraordinary algorithmic demonstration."
        snippet = kb.extract_passage_snippet(long_body, query_terms=["dog"], phrases=[], max_chars=40)
        self.assertFalse(snippet.endswith("al..."))
        self.assertIn("dog", snippet)
        # Should not end with partial letters before ellipsis
        truncated_part = snippet.rstrip(".").strip()
        last_word = truncated_part.split()[-1]
        self.assertTrue(last_word.isalpha(), f"Last word '{last_word}' is not clean")


if __name__ == "__main__":
    unittest.main()
