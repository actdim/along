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

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)
import hermetic


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

    @hermetic.requires_dashboard_deps
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


class TestArchiveScopeAndRanking(unittest.TestCase):
    """Tests for archive scope exclusion, --archive flag, explicit category, and ranking boost (REQ-1 to REQ-4)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo_root = self.tmp.name
        self.docs_dir = os.path.join(self.repo_root, "docs")
        self.issues_dir = os.path.join(self.repo_root, ".along", "ISSUES")
        self.done_issues_dir = os.path.join(self.issues_dir, "done")
        self.dec_dir = os.path.join(self.repo_root, ".along", "DECISIONS")
        self.sess_dir = os.path.join(self.repo_root, ".along", "SESSIONS", "2026")

        os.makedirs(self.docs_dir, exist_ok=True)
        os.makedirs(self.done_issues_dir, exist_ok=True)
        os.makedirs(self.dec_dir, exist_ok=True)
        os.makedirs(self.sess_dir, exist_ok=True)

        with open(os.path.join(self.docs_dir, "topic--worktree.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write("---\nprotocol: along\nslug: worktree\ntitle: Worktree Isolation Guide\ntype: topic\n---\n"
                    "# Worktree Isolation Guide\n\nGuide for workspace isolation and worktree environments.\n")

        with open(os.path.join(self.issues_dir, "feat--open-worktree.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write("---\nprotocol: along\nslug: open-worktree\ntitle: Open Worktree Task\ntype: feat\nstatus: open\n---\n"
                    "# Open Worktree Task\n\nImplementing active worktree features.\n")

        with open(os.path.join(self.done_issues_dir, "feat--done-worktree.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write("---\nprotocol: along\nslug: done-worktree\ntitle: Done Worktree Task\ntype: feat\nstatus: done\n---\n"
                    "# Done Worktree Task\n\nHistorical completed worktree task.\n")

        with open(os.path.join(self.dec_dir, "ADR-2026-01-01--active-worktree.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write("---\nprotocol: along\nslug: active-worktree\ntitle: Active Worktree Decision\nstatus: accepted\n---\n"
                    "# ADR-2026-01-01--active-worktree - Active Worktree Decision\n- Status: accepted\n- Decision: Use worktree.\n")

        with open(os.path.join(self.dec_dir, "ADR-2026-01-02--superseded-worktree.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write("---\nprotocol: along\nslug: superseded-worktree\ntitle: Superseded Worktree Decision\nstatus: superseded\n---\n"
                    "# ADR-2026-01-02--superseded-worktree - Superseded Worktree Decision\n- Status: superseded by newer\n- Decision: Old worktree method.\n")

        with open(os.path.join(self.sess_dir, "2026-01-01--session-worktree.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write("---\nprotocol: along\nslug: session-worktree\ndate: 2026-01-01\n---\n"
                    "# Session Log: Worktree\n\nLogged work on worktree isolation.\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_search_excludes_archived_entities(self):
        """Default search excludes done issues, sessions, and superseded ADRs (REQ-1)."""
        results = kb.search_knowledge_base("worktree", repo_root=self.repo_root, include_archive=False)
        slugs = [r["slug"] for r in results]
        self.assertIn("worktree", slugs)
        self.assertIn("open-worktree", slugs)
        self.assertIn("active-worktree", slugs)
        self.assertNotIn("done-worktree", slugs)
        self.assertNotIn("superseded-worktree", slugs)
        self.assertNotIn("session-worktree", slugs)

    def test_archive_flag_restores_archived_entities(self):
        """--archive / include_archive=True restores archived entities (REQ-1)."""
        results = kb.search_knowledge_base("worktree", repo_root=self.repo_root, limit=10, include_archive=True)
        slugs = [r["slug"] for r in results]
        self.assertIn("worktree", slugs)
        self.assertIn("open-worktree", slugs)
        self.assertIn("done-worktree", slugs)
        self.assertIn("active-worktree", slugs)
        self.assertIn("superseded-worktree", slugs)
        self.assertIn("session-worktree", slugs)

    def test_explicit_category_includes_archived(self):
        """Explicit --category session or --category issue includes them even without --archive (REQ-1)."""
        session_results = kb.search_knowledge_base("worktree", repo_root=self.repo_root, category="session", include_archive=False)
        session_slugs = [r["slug"] for r in session_results]
        self.assertIn("session-worktree", session_slugs)

        issue_results = kb.search_knowledge_base("worktree", repo_root=self.repo_root, category="issue", include_archive=False)
        issue_slugs = [r["slug"] for r in issue_results]
        self.assertIn("done-worktree", issue_slugs)
        self.assertIn("open-worktree", issue_slugs)

    def test_queries_return_matching_docs_in_top_3_by_default(self):
        """Queries 'worktree isolation', 'typography gate', 'migration backup' return docs/ topic in top 3 (REQ-4)."""
        queries = ["worktree isolation", "typography gate", "migration backup"]
        for q in queries:
            results = kb.search_knowledge_base(q, repo_root=REPO_ROOT, limit=3)
            self.assertGreaterEqual(len(results), 1, f"Expected matches for '{q}'")
            has_doc_in_top_3 = any(r["category"] == "kb" for r in results[:3])
            top_3_labels = [f"[{r['category_label']}] {r['title']} ({r['file_path']})" for r in results[:3]]
            self.assertTrue(
                has_doc_in_top_3,
                f"Query '{q}' did not return docs/ topic in top 3. Top results were:\n" + "\n".join(top_3_labels)
            )

    def test_status_displayed_in_result_lines(self):
        """Result lines show status [open, in-progress, done, superseded, active, etc.] (REQ-3)."""
        results = kb.search_knowledge_base("worktree", repo_root=self.repo_root, include_archive=True)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIn("status", r)
            self.assertTrue(r["status"])

        old_stdout = sys.stdout
        old_argv = sys.argv
        sys.stdout = io.StringIO()
        sys.argv = ["along_kb_search.py", "worktree", "--repo", self.repo_root, "-a", "--limit", "10"]
        try:
            kb.main()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
            sys.argv = old_argv

        self.assertIn("[active]", output)
        self.assertIn("[open]", output)
        self.assertIn("[done]", output)
        self.assertIn("[superseded]", output)
        self.assertIn("[completed]", output)

    def test_literal_search_matches_slug_across_all_scopes(self):
        """Literal search finds exact substrings across all scopes including archives (REQ-2)."""
        results = kb.search_knowledge_base("done-worktree", repo_root=self.repo_root, literal=True)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["slug"], "done-worktree")
        self.assertEqual(results[0]["status"], "done")


if __name__ == "__main__":
    unittest.main()
