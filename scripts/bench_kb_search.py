#!/usr/bin/env python3
"""
scripts/bench_kb_search.py - Benchmark search latency (p50, p95) and token efficiency.

Measures in-memory search and ranking performance across:
1. Current repository entries (docs/, .along/ artifacts).
2. Synthetic 1,000-entity fixture against the < 250ms target from ADR-2026-09-09.

CLI Usage:
    python scripts/bench_kb_search.py [--fixture-size 1000] [--runs 10] [--repo .] [--json]
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import platform
import random
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap, distill
bootstrap.ensure_deps()

from along_kb_search import (
    collect_all_entries,
    search_knowledge_base,
)

estimate_tokens = distill.estimate_tokens

DEFAULT_QUERIES = [
    "gate enforcement",
    "in-memory search",
    "runtime lifecycle hooks",
    "git merge conflict",
    "bounded context budget",
]


def calculate_percentiles(latencies: Sequence[float]) -> Tuple[float, float]:
    """Calculate p50 (median) and p95 latencies with linear interpolation."""
    if not latencies:
        return (0.0, 0.0)
    sorted_vals = sorted(latencies)
    n = len(sorted_vals)
    if n == 1:
        return (round(sorted_vals[0], 2), round(sorted_vals[0], 2))

    def _p(pct: float) -> float:
        k = (n - 1) * pct
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_vals[int(k)]
        d0 = sorted_vals[int(f)] * (c - k)
        d1 = sorted_vals[int(c)] * (k - f)
        return d0 + d1

    return (round(_p(0.50), 2), round(_p(0.95), 2))


def generate_synthetic_entities(count: int = 1000, seed: int = 42) -> List[Dict[str, Any]]:
    """Generate a reproducible synthetic fixture of structured entities."""
    rng = random.Random(seed)
    categories = ["kb", "issue", "decision", "milestone", "risk", "spike"]
    terms_pool = [
        "architecture", "boundary", "concurrency", "deployment", "enforcement",
        "framework", "governance", "hermetic", "indexing", "junction",
        "knowledge", "lifecycle", "memory", "namespace", "orchestration",
        "provenance", "quality", "runtime", "synchronization", "telemetry",
        "unidirectional", "verification", "worktree", "zero-vector", "ranking",
        "snippet", "budget", "circuit", "driver", "blackboard",
    ]
    phrases_pool = [
        "gate enforcement",
        "in-memory search",
        "runtime lifecycle hooks",
        "git merge conflict",
        "bounded context budget",
        "dual-tier memory architecture",
        "zero-vector snippet retrieval",
        "declarative quality gates",
        "session blackboard state",
        "ast symbol grounding",
    ]

    entries: List[Dict[str, Any]] = []
    for i in range(count):
        cat = rng.choice(categories)
        slug_terms = rng.sample(terms_pool, 3)
        slug = f"{cat}-{i:04d}-" + "-".join(slug_terms)
        title_terms = [t.title() for t in slug_terms]
        assigned_phrases = rng.sample(phrases_pool, 2)
        title = f"Component Specification {i:04d} : {assigned_phrases[0].title()} in " + " ".join(title_terms)
        tags = rng.sample(terms_pool, 3) + [assigned_phrases[0].split()[0]]

        # Generate realistic prose paragraphs (approx 800 - 1600 characters)
        body_paragraphs = []
        body_paragraphs.append(
            f"## Overview of {title}\n\n"
            f"This entity specifies the behavior and requirements for {assigned_phrases[0]} "
            f"within the context of {assigned_phrases[1]} and system {slug_terms[0]}. "
            f"It ensures reliable gate enforcement, bounded context budgets, and deterministic state transitions."
        )
        body_paragraphs.append(
            f"### Implementation Mechanics\n\n"
            f"The component integrates zero-vector retrieval with in-memory search and smoothed ranking. "
            f"When evaluating queries related to {assigned_phrases[0]} and {slug_terms[1]}, "
            f"smoothed inverse document frequency provides discriminative scoring. "
            f"Extracted passages are bounded to word boundaries without truncating code fences."
        )
        body_paragraphs.append(
            f"### Concurrency and Invariants\n\n"
            f"Under multi-agent execution, worktree isolation guarantees clean checkout trees and avoids any git merge conflict. "
            f"Merge drivers handle append-only logs while atomic state updates prevent race conditions. "
            f"Runtime lifecycle hooks enforce ASCII typography and valid entity references."
        )
        body = "\n\n".join(body_paragraphs)

        fm_lines = [
            "---",
            "protocol: along",
            f"slug: {slug}",
            f"category: {cat}",
            f"title: \"{title}\"",
            f"tags: [{', '.join(tags)}]",
            "status: active",
            "---",
        ]
        raw = "\n".join(fm_lines) + "\n\n" + body

        entries.append({
            "category": cat,
            "category_label": cat.upper(),
            "title": title,
            "slug": slug,
            "type": cat,
            "tags": tags,
            "status": "active",
            "file_path": f".along/{cat.upper()}S/{slug}.md",
            "abs_path": f"/synthetic/{slug}.md",
            "raw": raw,
            "body": body,
        })

    return entries


def benchmark_search_latency(
    entries: List[Dict[str, Any]],
    queries: Sequence[str],
    runs: int = 10,
    limit: int = 5,
) -> Dict[str, Any]:
    """Execute queries multiple times to record in-memory search and ranking latencies."""
    query_stats: List[Dict[str, Any]] = []
    all_latencies_ms: List[float] = []

    # Warm-up run to prime any module caches
    if queries:
        search_knowledge_base(queries[0], limit=limit, return_stats=True, entries=entries)

    for q in queries:
        q_latencies: List[float] = []
        sample_results: List[Dict[str, Any]] = []
        sample_stats: Dict[str, Any] = {}

        for _ in range(runs):
            t0 = time.perf_counter()
            res, stats = search_knowledge_base(
                q,
                limit=limit,
                return_stats=True,
                entries=entries,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            q_latencies.append(elapsed_ms)
            all_latencies_ms.append(elapsed_ms)
            sample_results = res
            sample_stats = stats

        p50, p95 = calculate_percentiles(q_latencies)

        # Calculate token statistics for this query
        snippet_chars = sum(len(r.get("snippet", "")) + len(r.get("title", "")) for r in sample_results)
        snippet_tokens = max(1, snippet_chars // 4)

        matched_slugs = {r.get("slug") for r in sample_results}
        matched_entries = [e for e in entries if e.get("slug") in matched_slugs]
        matched_full_chars = sum(len(e.get("raw") or e.get("body", "")) for e in matched_entries)
        matched_full_tokens = max(1, matched_full_chars // 4) if matched_entries else snippet_tokens

        savings_vs_full_files_pct = (
            round((1.0 - (snippet_tokens / matched_full_tokens)) * 100.0, 1)
            if matched_full_tokens > 0 else 0.0
        )

        query_stats.append({
            "query": q,
            "runs": runs,
            "p50_ms": p50,
            "p95_ms": p95,
            "min_ms": round(min(q_latencies), 2),
            "max_ms": round(max(q_latencies), 2),
            "avg_ms": round(sum(q_latencies) / len(q_latencies), 2),
            "matches": len(sample_results),
            "snippet_tokens": snippet_tokens,
            "matched_full_tokens": matched_full_tokens,
            "savings_vs_full_files_pct": savings_vs_full_files_pct,
            "corpus_tokens": sample_stats.get("corpus_tokens_est", 0),
            "corpus_savings_pct": sample_stats.get("savings_pct", 0.0),
        })

    overall_p50, overall_p95 = calculate_percentiles(all_latencies_ms)
    total_corpus_chars = sum(len(e.get("raw") or e.get("body", "")) for e in entries)
    total_corpus_tokens = max(1, total_corpus_chars // 4)

    return {
        "entity_count": len(entries),
        "total_corpus_tokens": total_corpus_tokens,
        "runs_per_query": runs,
        "overall_p50_ms": overall_p50,
        "overall_p95_ms": overall_p95,
        "overall_min_ms": round(min(all_latencies_ms), 2) if all_latencies_ms else 0.0,
        "overall_max_ms": round(max(all_latencies_ms), 2) if all_latencies_ms else 0.0,
        "overall_avg_ms": round(sum(all_latencies_ms) / len(all_latencies_ms), 2) if all_latencies_ms else 0.0,
        "query_stats": query_stats,
    }


def benchmark_repository(
    repo_root: str = ".",
    queries: Optional[Sequence[str]] = None,
    runs: int = 10,
    limit: int = 5,
) -> Dict[str, Any]:
    """Benchmark search on the actual repository entries."""
    q_list = list(queries or DEFAULT_QUERIES)
    t0 = time.perf_counter()
    entries = collect_all_entries(os.path.abspath(repo_root))
    collect_time_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    bench = benchmark_search_latency(entries, q_list, runs=runs, limit=limit)
    bench["collect_time_ms"] = collect_time_ms
    bench["repo_root"] = os.path.abspath(repo_root)
    return bench


def benchmark_synthetic_fixture(
    fixture_size: int = 1000,
    queries: Optional[Sequence[str]] = None,
    runs: int = 10,
    limit: int = 5,
    target_latency_ms: float = 250.0,
) -> Dict[str, Any]:
    """Benchmark in-memory ranking on a synthetic fixture against target latency."""
    q_list = list(queries or DEFAULT_QUERIES)
    t0 = time.perf_counter()
    entries = generate_synthetic_entities(count=fixture_size)
    generate_time_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    bench = benchmark_search_latency(entries, q_list, runs=runs, limit=limit)
    bench["generate_time_ms"] = generate_time_ms
    bench["target_latency_ms"] = target_latency_ms
    bench["meets_target"] = bench["overall_p95_ms"] < target_latency_ms
    return bench


def run_all_benchmarks(
    repo_root: str = ".",
    fixture_size: int = 1000,
    runs: int = 10,
    queries: Optional[Sequence[str]] = None,
    limit: int = 5,
    target_latency_ms: float = 250.0,
) -> Dict[str, Any]:
    """Run full benchmark suite and compile system and benchmark metrics."""
    q_list = list(queries or DEFAULT_QUERIES)
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    metadata = {
        "timestamp": timestamp,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "target_latency_ms": target_latency_ms,
    }

    repo_bench = benchmark_repository(repo_root=repo_root, queries=q_list, runs=runs, limit=limit)
    synth_bench = benchmark_synthetic_fixture(
        fixture_size=fixture_size,
        queries=q_list,
        runs=runs,
        limit=limit,
        target_latency_ms=target_latency_ms,
    )

    return {
        "metadata": metadata,
        "repository_benchmark": repo_bench,
        "synthetic_benchmark": synth_bench,
    }


def format_benchmark_report(report: Dict[str, Any]) -> str:
    """Format benchmark results into clean ASCII summary tables."""
    lines: List[str] = []
    meta = report["metadata"]
    lines.append("================================================================================")
    lines.append("                ALONG KNOWLEDGE SEARCH PERFORMANCE BENCHMARK                   ")
    lines.append("================================================================================")
    lines.append(f"Timestamp      : {meta['timestamp']}")
    lines.append(f"Platform       : {meta['platform']}")
    lines.append(f"Python         : {meta['python_version']}")
    lines.append(f"Target Latency : < {meta['target_latency_ms']} ms (ADR-2026-09-09 for 1,000 entities)")
    lines.append("")

    # 1. Real Repository
    rb = report["repository_benchmark"]
    lines.append("--------------------------------------------------------------------------------")
    lines.append("1. REAL REPOSITORY BENCHMARK")
    lines.append("--------------------------------------------------------------------------------")
    lines.append(f"Repository Root    : {rb.get('repo_root', '.')}")
    lines.append(f"Corpus Entities    : {rb['entity_count']} entities (~{rb['total_corpus_tokens']:,} tokens)")
    lines.append(f"Collection Latency : {rb.get('collect_time_ms', 0)} ms")
    lines.append(f"Overall In-Memory  : p50 = {rb['overall_p50_ms']} ms | p95 = {rb['overall_p95_ms']} ms | avg = {rb['overall_avg_ms']} ms")
    lines.append("")
    lines.append(f"{'Query':<28} {'p50 (ms)':<10} {'p95 (ms)':<10} {'Snippet Tok':<12} {'Full Doc Tok':<14} {'Doc Savings':<12}")
    lines.append("-" * 88)
    for qs in rb["query_stats"]:
        lines.append(
            f"{qs['query']:<28} "
            f"{qs['p50_ms']:<10.2f} "
            f"{qs['p95_ms']:<10.2f} "
            f"{qs['snippet_tokens']:<12} "
            f"{qs['matched_full_tokens']:<14} "
            f"{qs['savings_vs_full_files_pct']:<10.1f}%"
        )
    lines.append("")

    # 2. Synthetic Fixture
    sb = report["synthetic_benchmark"]
    target_status = "PASS" if sb["meets_target"] else "FAIL"
    lines.append("--------------------------------------------------------------------------------")
    lines.append(f"2. SYNTHETIC FIXTURE BENCHMARK ({sb['entity_count']:,} ENTITIES)")
    lines.append("--------------------------------------------------------------------------------")
    lines.append(f"Fixture Entities   : {sb['entity_count']:,} entities (~{sb['total_corpus_tokens']:,} tokens)")
    lines.append(f"Fixture Generation : {sb.get('generate_time_ms', 0)} ms")
    lines.append(f"Overall In-Memory  : p50 = {sb['overall_p50_ms']} ms | p95 = {sb['overall_p95_ms']} ms | avg = {sb['overall_avg_ms']} ms")
    lines.append(f"ADR-2026-09-09 Gate: < {sb['target_latency_ms']} ms target -> {target_status} (p95: {sb['overall_p95_ms']} ms)")
    lines.append("")
    lines.append(f"{'Query':<28} {'p50 (ms)':<10} {'p95 (ms)':<10} {'Snippet Tok':<12} {'Full Doc Tok':<14} {'Doc Savings':<12}")
    lines.append("-" * 88)
    for qs in sb["query_stats"]:
        lines.append(
            f"{qs['query']:<28} "
            f"{qs['p50_ms']:<10.2f} "
            f"{qs['p95_ms']:<10.2f} "
            f"{qs['snippet_tokens']:<12} "
            f"{qs['matched_full_tokens']:<14} "
            f"{qs['savings_vs_full_files_pct']:<10.1f}%"
        )
    lines.append("================================================================================")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Along Knowledge Search Performance & Token Savings Benchmark Harness"
    )
    parser.add_argument(
        "--fixture-size",
        type=int,
        default=1000,
        help="Number of synthetic entities to benchmark (default: 1000)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=10,
        help="Number of iterations per query for percentile calculation (default: 10)",
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Target repository root to benchmark (default: .)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of top results per search query (default: 5)",
    )
    parser.add_argument(
        "--target-ms",
        type=float,
        default=250.0,
        help="Target latency ceiling in ms from ADR-2026-09-09 (default: 250.0)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format instead of text table",
    )
    args = parser.parse_args()

    report = run_all_benchmarks(
        repo_root=args.repo,
        fixture_size=args.fixture_size,
        runs=args.runs,
        limit=args.limit,
        target_latency_ms=args.target_ms,
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_benchmark_report(report))

    # Exit code: 0 if synthetic p95 meets target, 1 otherwise
    if not report["synthetic_benchmark"]["meets_target"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
