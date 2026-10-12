#!/usr/bin/env python3
"""
tests/test_bench_kb_search.py - Tests for kb-search benchmark harness and grounded claims.

Verifies [docs--unverified-performance-claims]:
- scripts/bench_kb_search.py computes p50/p95 latency and token statistics.
- Synthetic fixture generation produces structured, reproducible entities.
- In-memory ranking meets target latency specification (< 250ms from ADR-2026-09-09).
- README.md does not contain obsolete hardcoded claims ("12 protocol invariants", "85-95%").
- README.md reflects current runtime gate counts (16 runtime gates, 30+ protocol invariants).
- docs/topic--system-comparisons.md includes neutral ecosystem tool comparison table.
- All created and modified files adhere strictly to clean ASCII typography.
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
import bench_kb_search


class TestBenchKbSearch(unittest.TestCase):
    """Test suite for search performance benchmark harness and documentation claims."""

    def test_calculate_percentiles(self):
        """Verify linear interpolation percentile calculation for p50 and p95."""
        p50, p95 = bench_kb_search.calculate_percentiles([10.0, 20.0, 30.0, 40.0, 50.0])
        self.assertEqual(p50, 30.0)
        self.assertEqual(p95, 48.0)

        # Single element edge case
        single_p50, single_p95 = bench_kb_search.calculate_percentiles([42.5])
        self.assertEqual(single_p50, 42.5)
        self.assertEqual(single_p95, 42.5)

        # Empty list edge case
        empty_p50, empty_p95 = bench_kb_search.calculate_percentiles([])
        self.assertEqual(empty_p50, 0.0)
        self.assertEqual(empty_p95, 0.0)

    def test_generate_synthetic_entities(self):
        """Verify synthetic entity generator outputs valid, well-formed entities."""
        entities = bench_kb_search.generate_synthetic_entities(count=30, seed=123)
        self.assertEqual(len(entities), 30)

        for e in entities:
            self.assertIn("category", e)
            self.assertIn("slug", e)
            self.assertIn("title", e)
            self.assertIn("raw", e)
            self.assertIn("body", e)
            self.assertTrue(e["raw"].startswith("---"))
            self.assertIn("status: active", e["raw"])
            self.assertGreater(len(e["body"]), 100)

    def test_benchmark_search_latency_and_token_stats(self):
        """Verify search latency measurement computes percentiles and token savings."""
        entities = bench_kb_search.generate_synthetic_entities(count=40, seed=42)
        queries = ["gate enforcement", "in-memory search"]

        result = bench_kb_search.benchmark_search_latency(
            entries=entities,
            queries=queries,
            runs=3,
            limit=5,
        )

        self.assertEqual(result["entity_count"], 40)
        self.assertGreater(result["total_corpus_tokens"], 0)
        self.assertEqual(len(result["query_stats"]), 2)

        for qs in result["query_stats"]:
            self.assertIn(qs["query"], queries)
            self.assertGreaterEqual(qs["p50_ms"], 0.0)
            self.assertGreaterEqual(qs["p95_ms"], qs["p50_ms"])
            self.assertGreaterEqual(qs["max_ms"], qs["p95_ms"])
            self.assertGreaterEqual(qs["snippet_tokens"], 1)
            self.assertGreaterEqual(qs["matched_full_tokens"], 1)
            self.assertGreaterEqual(qs["savings_vs_full_files_pct"], 0.0)
            self.assertLessEqual(qs["savings_vs_full_files_pct"], 100.0)

    def test_benchmark_synthetic_fixture_meets_target(self):
        """Verify synthetic benchmark checks ADR-2026-09-09 < 250ms target."""
        sb = bench_kb_search.benchmark_synthetic_fixture(
            fixture_size=50,
            queries=["gate enforcement"],
            runs=2,
            target_latency_ms=250.0,
        )

        self.assertEqual(sb["entity_count"], 50)
        self.assertEqual(sb["target_latency_ms"], 250.0)
        self.assertTrue(sb["meets_target"])
        self.assertLess(sb["overall_p95_ms"], 250.0)

    def test_format_report(self):
        """Verify ASCII benchmark report formatting."""
        report = bench_kb_search.run_all_benchmarks(
            repo_root=REPO_ROOT,
            fixture_size=20,
            runs=1,
            queries=["gate enforcement"],
            target_latency_ms=250.0,
        )
        text = bench_kb_search.format_benchmark_report(report)
        self.assertIn("ALONG KNOWLEDGE SEARCH PERFORMANCE BENCHMARK", text)
        self.assertIn("1. REAL REPOSITORY BENCHMARK", text)
        self.assertIn("2. SYNTHETIC FIXTURE BENCHMARK", text)
        self.assertIn("ADR-2026-09-09 Gate", text)

    def test_readme_no_obsolete_claims(self):
        """Verify README.md contains no obsolete invariant or unbacked percentage claims."""
        readme_path = os.path.join(REPO_ROOT, "README.md")
        content = textio.read_text(readme_path, strict=True)

        self.assertNotIn("12 protocol invariants", content)
        self.assertNotIn("85-95%", content)
        self.assertNotIn("Sub-50ms", content)
        self.assertNotIn("sub-50ms", content)

        # Grounded claims must be present
        self.assertIn("16 runtime gates", content)
        self.assertIn("30+ protocol invariants", content)
        self.assertIn("bench_kb_search.py", content)

    def test_docs_system_comparisons_table_and_claims(self):
        """Verify docs/topic--system-comparisons.md contains neutral tool comparison table."""
        doc_path = os.path.join(REPO_ROOT, "docs", "topic--system-comparisons.md")
        content = textio.read_text(doc_path, strict=True)

        # Neutral comparison tools required by REQ-4
        self.assertIn("GitHub spec-kit", content)
        self.assertIn("Task Master", content)
        self.assertIn("Beads / Kiro specs", content)
        self.assertIn("CLAUDE.md", content)
        self.assertIn("AGENTS.md", content)
        self.assertIn("Cursor rules", content)

        # Unbacked claim removed
        self.assertNotIn("85-95%", content)
        self.assertIn("bench_kb_search.py", content)

    def test_clean_ascii_typography(self):
        """Verify all new benchmark files adhere strictly to clean ASCII typography."""
        for rel_path in ["scripts/bench_kb_search.py", "tests/test_bench_kb_search.py"]:
            full_path = os.path.join(REPO_ROOT, rel_path)
            content = textio.read_text(full_path, strict=True)
            violations = typography.findings(content)
            self.assertEqual(
                violations,
                [],
                f"Typography violations in {rel_path}: {violations}",
            )


if __name__ == "__main__":
    unittest.main()
