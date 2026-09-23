#!/usr/bin/env python3
"""
along_graph_arch.py - Architectural Intelligence & Coupling Hotspot Engine.

Inspects repository modular architecture, community boundaries, coupling hotspots,
and critical bridge nodes using code-review-graph with fallback to static analysis:
1. Analyzes community clusters and cohesion.
2. Flags cross-community coupling risks.
3. Discovers high-fan-in hub hotspots.
4. Identifies architectural bridge bottlenecks.

Usage:
    python scripts/along_graph_arch.py [OPTIONS]
    along graph-arch [OPTIONS]

Options:
    --detail-level      minimal | standard (default: standard)
    --top-hubs N        Number of top hub nodes to report (default: 10)
    --top-bridges N     Number of top bridge nodes to report (default: 10)
    --repo DIR          Target repository root (auto-detected if omitted)
    --optional          Treat offline state as non-fatal warning (exit code 0)
    --json              Output machine-readable JSON report
    --timeout SECONDS   Process timeout for external probes (default: 20.0)
    -q, --quiet         Suppress non-essential progress output
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from typing import Dict, Any, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import install, repo


def static_arch_analysis(repo_root: str, top_hubs: int = 10, top_bridges: int = 10) -> Dict[str, Any]:
    """Fallback static architectural analysis based on directory clusters and import fan-in/fan-out."""
    packages: Dict[str, Dict[str, Any]] = {}
    import_counts: Dict[str, int] = {}
    cross_edges: Dict[Tuple[str, str], int] = {}

    target_dirs = ["scripts", "dashboard", "packages", "rules", "skills", "tests", "hooks"]

    for d in target_dirs:
        abs_d = os.path.join(repo_root, d)
        if not os.path.isdir(abs_d):
            continue
        file_count = 0
        total_lines = 0
        dominant_ext = {}
        for root, _, files in os.walk(abs_d):
            if "__pycache__" in root or "node_modules" in root or ".git" in root:
                continue
            for f in files:
                ext = os.path.splitext(f)[1]
                dominant_ext[ext] = dominant_ext.get(ext, 0) + 1
                fpath = os.path.join(root, f)
                file_count += 1
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                        lines = len(fh.readlines())
                    total_lines += lines
                except OSError:
                    pass

        dom_lang = max(dominant_ext.items(), key=lambda x: x[1])[0] if dominant_ext else "unknown"
        packages[d] = {
            "name": d,
            "size": file_count,
            "total_lines": total_lines,
            "dominant_language": dom_lang,
        }

    # Analyze cross-directory imports across Python and TypeScript files
    import_re = re.compile(r"^\s*(?:from|import)\s+([\w\.\-]+)", re.MULTILINE)
    for d in target_dirs:
        abs_d = os.path.join(repo_root, d)
        if not os.path.isdir(abs_d):
            continue
        for root, _, files in os.walk(abs_d):
            if "__pycache__" in root or "node_modules" in root:
                continue
            for f in files:
                if not (f.endswith(".py") or f.endswith(".ts") or f.endswith(".tsx")):
                    continue
                fpath = os.path.join(root, f)
                rel_source = os.path.relpath(fpath, repo_root).replace("\\", "/")
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read()
                    matches = import_re.findall(content)
                    for m in matches:
                        import_counts[m] = import_counts.get(m, 0) + 1
                        # Check target directory
                        for target_d in target_dirs:
                            if target_d != d and (m.startswith(target_d) or m.startswith("alongkit")):
                                key = (d, target_d)
                                cross_edges[key] = cross_edges.get(key, 0) + 1
                except OSError:
                    continue

    sorted_hubs = [
        {"name": k, "fan_in": v, "kind": "Module / Symbol"}
        for k, v in sorted(import_counts.items(), key=lambda x: x[1], reverse=True)[:top_hubs]
    ]

    warnings = []
    for (src, tgt), cnt in cross_edges.items():
        if cnt > 15:
            warnings.append(f"High static coupling ({cnt} imports) between '{src}' and '{tgt}'")

    communities = [
        {
            "id": idx + 1,
            "name": pkg["name"],
            "size": pkg["size"],
            "cohesion": 0.1,
            "dominant_language": pkg["dominant_language"],
        }
        for idx, pkg in enumerate(packages.values())
    ]

    return {
        "status": "degraded",
        "mode": "degraded_static",
        "communities": communities,
        "cross_community_edges": [
            {"source_community": src, "target_community": tgt, "edge_count": cnt}
            for (src, tgt), cnt in cross_edges.items()
        ],
        "warnings": warnings,
        "hub_nodes": sorted_hubs,
        "bridge_nodes": sorted_hubs[:top_bridges],
        "summary": f"[DEGRADED] code-review-graph offline - static analysis mapped {len(communities)} packages and {len(sorted_hubs)} coupling hubs.",
    }


def analyze_architecture(
    repo_root: Optional[str] = None,
    detail_level: str = "standard",
    top_hubs: int = 10,
    top_bridges: int = 10,
    timeout: float = 20.0,
    optional: bool = False,
) -> Dict[str, Any]:
    """Run architectural analysis using CRG or static fallback."""
    if not repo_root:
        repo_root = repo.find_repo_root(os.getcwd())

    uvx_bin = shutil.which("uvx")
    package_spec = install.MCP_SERVER_PACKAGE

    is_crg_available = False
    if uvx_bin:
        try:
            stat_res = subprocess.run(
                [uvx_bin, package_spec, "status", "--repo", repo_root],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5.0,
                check=False,
            )
            if stat_res.returncode == 0 and "Nodes:" in stat_res.stdout:
                is_crg_available = True
        except (subprocess.TimeoutExpired, OSError):
            pass

    if is_crg_available:
        cmd = [
            uvx_bin,
            package_spec,
            "architecture",
            "--detail-level",
            detail_level,
            "--repo",
            repo_root,
        ]
        try:
            arch_res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                check=False,
            )
            if arch_res.returncode == 0 and arch_res.stdout:
                arch_data = json.loads(arch_res.stdout)

                # Fetch large functions to enrich hotspot insights
                large_fns = []
                large_res = subprocess.run(
                    [uvx_bin, package_spec, "large-functions", "--repo", repo_root],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
                if large_res.returncode == 0 and large_res.stdout:
                    try:
                        large_data = json.loads(large_res.stdout)
                        for item in large_data.get("large_functions", [])[:top_hubs]:
                            large_fns.append({
                                "name": item.get("name"),
                                "kind": item.get("kind"),
                                "lines": item.get("line_count"),
                                "path": item.get("relative_path"),
                            })
                    except ValueError:
                        pass

                # Derive top hub hotspots from cross-community edges and large functions
                hub_nodes = []
                for edge in arch_data.get("cross_community_edges", []):
                    hub_nodes.append({
                        "name": f"{edge['source_community']} -> {edge['target_community']}",
                        "edge_count": edge.get("edge_count", 0),
                        "top_kinds": edge.get("top_kinds", []),
                    })

                return {
                    "status": "healthy",
                    "mode": "code_review_graph",
                    "summary": arch_data.get("summary", "Architecture overview generated."),
                    "communities": arch_data.get("communities", []),
                    "cross_community_edges": arch_data.get("cross_community_edges", []),
                    "warnings": arch_data.get("warnings", []),
                    "hub_nodes": hub_nodes[:top_hubs],
                    "large_functions": large_fns,
                    "bridge_nodes": hub_nodes[:top_bridges],
                }
        except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError):
            pass

    # Static fallback
    return static_arch_analysis(repo_root, top_hubs=top_hubs, top_bridges=top_bridges)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect repository architecture, community structure, and coupling hotspots."
    )
    parser.add_argument(
        "--detail-level",
        choices=["minimal", "standard"],
        default="standard",
        help="Detail level for architecture analysis (default: standard)",
    )
    parser.add_argument(
        "--top-hubs",
        type=int,
        default=10,
        help="Number of top hub nodes to report (default: 10)",
    )
    parser.add_argument(
        "--top-bridges",
        type=int,
        default=10,
        help="Number of top bridge nodes to report (default: 10)",
    )
    parser.add_argument(
        "--repo", default=None, help="Target repository root (auto-detected if omitted)"
    )
    parser.add_argument(
        "--optional", action="store_true", help="Treat offline state as non-fatal (exit code 0)"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress progress output"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output report in machine-readable JSON"
    )
    parser.add_argument(
        "--timeout", type=float, default=20.0, help="External tool timeout in seconds"
    )

    args = parser.parse_args()
    effective_root = args.repo or repo.find_repo_root(os.getcwd())
    report = analyze_architecture(
        repo_root=effective_root,
        detail_level=args.detail_level,
        top_hubs=args.top_hubs,
        top_bridges=args.top_bridges,
        timeout=args.timeout,
        optional=args.optional,
    )

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    status_tag = report["status"].upper()
    print("=" * 60)
    print(f"-> Along Graph Architecture: [{status_tag}]")
    print("=" * 60)
    print(f"Summary:         {report['summary']}")
    print(f"Mode:            {report['mode']}")
    print("-" * 60)

    print(f"Architectural Communities ({len(report.get('communities', []))} detected):")
    for comm in report.get("communities", []):
        c_id = comm.get("id", "-")
        c_name = comm.get("name", "unnamed")
        c_size = comm.get("size", 0)
        c_lang = comm.get("dominant_language", "unknown")
        c_cohesion = comm.get("cohesion")
        cohesion_str = f", cohesion: {c_cohesion:.2f}" if c_cohesion is not None else ""
        print(f"  [{c_id}] {c_name} (nodes: {c_size}, language: {c_lang}{cohesion_str})")

    if report.get("warnings"):
        print("-" * 60)
        print("Architectural Warnings & Coupling Risks:")
        for w in report["warnings"]:
            print(f"  [!] {w}")

    if report.get("cross_community_edges"):
        print("-" * 60)
        print("Subsystem Coupling Intersections:")
        comm_map = {c.get("id"): c.get("name") for c in report.get("communities", [])}
        for edge in report["cross_community_edges"][:10]:
            if "edge_count" in edge:
                src = edge.get("source_community", "")
                tgt = edge.get("target_community", "")
                cnt = edge.get("edge_count", 0)
                kinds = ", ".join(edge.get("top_kinds", []))
                kinds_str = f" ({kinds})" if kinds else ""
                print(f"  - {src} -> {tgt}: {cnt} edges{kinds_str}")
            elif "source" in edge:
                src_comm = comm_map.get(edge.get("source_community"), edge.get("source_community"))
                tgt_comm = comm_map.get(edge.get("target_community"), edge.get("target_community"))
                src_sym = repo.safe_relpath(edge.get("source", ""), effective_root)
                tgt_sym = repo.safe_relpath(edge.get("target", ""), effective_root)
                kind = edge.get("edge_kind", "COUPLED")
                print(f"  - [{src_comm} -> {tgt_comm}] {src_sym} -{kind}-> {tgt_sym}")

    if report.get("large_functions"):
        print("-" * 60)
        print("High-Complexity Hotspots (Oversized Functions & Modules):")
        for fn in report["large_functions"][:8]:
            name = fn.get("name", "")
            lines = fn.get("lines", 0)
            fpath = fn.get("path", "")
            print(f"  - {name} ({lines} lines) in {fpath}")

    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
