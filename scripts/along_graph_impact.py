#!/usr/bin/env python3
"""
along_graph_impact.py - Semantic Blast Radius Assessment Engine.

Determines the blast radius of planned or modified symbols and files using
code-review-graph AST queries with automatic fallback to static search:
1. Traces callers, callees, and importers.
2. Identifies affected execution flows.
3. Discovers candidate tests for the target.
4. Maps affected symbols to Knowledge Base articles in docs/topic--*.md.

Usage:
    python scripts/along_graph_impact.py [TARGET] [OPTIONS]
    along graph-impact [TARGET] [OPTIONS]

Options:
    TARGET              Symbol name or file path (auto-detects changes if omitted)
    --base REF          Git base ref for change detection (default: HEAD~1)
    --max-depth N       Dependency traversal depth (default: 2)
    --repo DIR          Target repository root (auto-detected if omitted)
    --optional          Treat missing uvx/crg as non-fatal warning (exit code 0)
    --json              Output machine-readable JSON report
    --timeout SECONDS   Process timeout for external probes (default: 15.0)
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


def get_git_changed_files(repo_root: str, base: str = "HEAD~1") -> List[str]:
    """Retrieve list of modified or untracked files relative to repo root."""
    changed = []
    # 1. Uncommitted working tree changes
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5.0,
            check=False,
        )
        if res.returncode == 0 and res.stdout:
            for line in res.stdout.splitlines():
                parts = line.strip().split(maxsplit=1)
                if len(parts) == 2:
                    changed.append(parts[1].strip().replace("\\", "/"))
    except (subprocess.TimeoutExpired, OSError):
        pass

    # 2. Diff against base if working tree has few or no changes
    if not changed:
        try:
            res = subprocess.run(
                ["git", "diff", "--name-only", base],
                cwd=repo_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5.0,
                check=False,
            )
            if res.returncode == 0 and res.stdout:
                for line in res.stdout.splitlines():
                    f = line.strip().replace("\\", "/")
                    if f and f not in changed:
                        changed.append(f)
        except (subprocess.TimeoutExpired, OSError):
            pass

    return changed


def find_candidate_tests_static(repo_root: str, target: str) -> List[str]:
    """Find test files referencing or naming the target symbol or file."""
    tests_found = []
    target_clean = os.path.splitext(os.path.basename(target))[0]
    if target_clean.startswith("along_"):
        target_clean = target_clean.replace("along_", "")

    tests_dir = os.path.join(repo_root, "tests")
    if not os.path.isdir(tests_dir):
        return tests_found

    for root, _, files in os.walk(tests_dir):
        for f in files:
            if not f.endswith(".py") and not f.endswith(".js") and not f.endswith(".ts"):
                continue
            fpath = os.path.join(root, f)
            rel = os.path.relpath(fpath, repo_root).replace("\\", "/")
            # Filename heuristic
            if target_clean and (target_clean in f):
                if rel not in tests_found:
                    tests_found.append(rel)
                continue
            # Content match
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
                if target in content or (target_clean and target_clean in content):
                    if rel not in tests_found:
                        tests_found.append(rel)
            except OSError:
                continue

    return tests_found[:10]


def find_affected_docs_static(repo_root: str, target: str) -> List[str]:
    """Map target symbol or file to affected Knowledge Base articles in docs/."""
    docs_found = []
    target_clean = os.path.splitext(os.path.basename(target))[0]
    docs_dir = os.path.join(repo_root, "docs")
    if not os.path.isdir(docs_dir):
        return docs_found

    for root, _, files in os.walk(docs_dir):
        for f in files:
            if not f.endswith(".md"):
                continue
            fpath = os.path.join(root, f)
            rel = os.path.relpath(fpath, repo_root).replace("\\", "/")
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
                if target in content or (target_clean and target_clean in content):
                    docs_found.append(rel)
            except OSError:
                continue

    # Prioritize primary topic articles (docs/topic--*.md) over individual ADRs
    topic_docs = sorted([d for d in docs_found if "topic--" in d])
    other_docs = sorted([d for d in docs_found if "topic--" not in d])
    return (topic_docs + other_docs)[:15]


def static_impact_search(repo_root: str, target: str) -> Dict[str, Any]:
    """Fallback static search across callers, imports, tests, and documentation."""
    callers = []
    importers = []
    target_clean = os.path.splitext(os.path.basename(target))[0]

    pattern = re.compile(r"\b" + re.escape(target_clean) + r"\b")

    search_dirs = [os.path.join(repo_root, "scripts"), os.path.join(repo_root, "skills")]
    for sdir in search_dirs:
        if not os.path.isdir(sdir):
            continue
        for root, _, files in os.walk(sdir):
            for f in files:
                if not (f.endswith(".py") or f.endswith(".md") or f.endswith(".ts")):
                    continue
                fpath = os.path.join(root, f)
                rel = os.path.relpath(fpath, repo_root).replace("\\", "/")
                if rel == target or rel == target.replace("\\", "/"):
                    continue
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read()
                    if pattern.search(content):
                        if f.endswith(".py") or f.endswith(".ts"):
                            callers.append(rel)
                        else:
                            importers.append(rel)
                except OSError:
                    continue

    tests = find_candidate_tests_static(repo_root, target)
    docs = find_affected_docs_static(repo_root, target)

    return {
        "mode": "degraded_static",
        "callers": sorted(list(set(callers)))[:15],
        "importers": sorted(list(set(importers)))[:10],
        "affected_flows": [],
        "candidate_tests": tests,
        "affected_docs": docs,
    }


def query_crg_cli(
    uvx_bin: str,
    package_spec: str,
    repo_root: str,
    subcmd: str,
    args: List[str],
    timeout: float = 15.0,
) -> Tuple[bool, str]:
    """Run a code-review-graph CLI subcommand."""
    cmd = [uvx_bin, package_spec, subcmd] + args + ["--repo", repo_root]
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = ((res.stdout or "") + "\n" + (res.stderr or "")).strip()
        return (res.returncode == 0), output
    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, str(exc)


def analyze_impact(
    repo_root: Optional[str] = None,
    target: Optional[str] = None,
    base: str = "HEAD~1",
    max_depth: int = 2,
    timeout: float = 15.0,
    optional: bool = False,
) -> Dict[str, Any]:
    """Compute blast radius for target symbol or file using CRG or static fallback."""
    if not repo_root:
        repo_root = repo.find_repo_root(os.getcwd())

    uvx_bin = shutil.which("uvx")
    package_spec = install.MCP_SERVER_PACKAGE

    # Determine effective target
    changed_files = []
    if not target:
        changed_files = get_git_changed_files(repo_root, base)
        if changed_files:
            target = changed_files[0]
        else:
            target = "HEAD"

    is_crg_available = False
    crg_output = ""

    # Check if uvx and crg respond
    if uvx_bin:
        succ, out = query_crg_cli(uvx_bin, package_spec, repo_root, "status", [], timeout=5.0)
        if succ and "Nodes:" in out:
            is_crg_available = True

    if is_crg_available:
        # Run crg impact command
        impact_args = ["--depth", str(max_depth), "--base", base]
        if target and target != "HEAD":
            impact_args.extend(["--files", target])
        succ_impact, impact_out = query_crg_cli(
            uvx_bin, package_spec, repo_root, "impact", impact_args, timeout=timeout
        )

        impact_data: Dict[str, Any] = {}
        if succ_impact and impact_out:
            try:
                impact_data = json.loads(impact_out)
            except ValueError:
                pass

        callers = []
        # If target looks like a symbol or single file, also query callers
        if target and target != "HEAD":
            succ_q, q_out = query_crg_cli(
                uvx_bin, package_spec, repo_root, "query", ["callers_of", target], timeout=timeout
            )
            if succ_q and q_out:
                try:
                    q_data = json.loads(q_out)
                    for item in q_data.get("results", []):
                        if isinstance(item, dict):
                            callers.append(item.get("name") or item.get("id") or str(item))
                        else:
                            callers.append(str(item))
                except ValueError:
                    callers = [line.strip() for line in q_out.splitlines() if line.strip() and not line.startswith("=")]

        # Also parse impacted nodes and files from impact_data
        impacted_summary = []
        if impact_data:
            nodes = impact_data.get("nodes", [])
            for n in nodes[:15]:
                name = n.get("name") or n.get("id", "")
                kind = n.get("kind", "")
                fpath = n.get("file_path", "")
                if fpath:
                    fpath = repo.safe_relpath(fpath, repo_root) if repo_root else fpath
                impacted_summary.append(f"{kind} {name} ({fpath})" if kind else f"{name} ({fpath})")

        tests = find_candidate_tests_static(repo_root, target)
        docs = find_affected_docs_static(repo_root, target)

        return {
            "status": "healthy",
            "mode": "code_review_graph",
            "target": target,
            "changed_files": changed_files or ([target] if target != "HEAD" else []),
            "callers": callers,
            "impacted_nodes": impacted_summary,
            "total_impacted": impact_data.get("total_impacted", len(impacted_summary)),
            "impact_raw": impact_data or impact_out,
            "candidate_tests": tests,
            "affected_docs": docs,
            "summary": f"Analyzed blast radius via code-review-graph for '{target}'.",
        }

    # Fallback to static analysis
    static_res = static_impact_search(repo_root, target)
    return {
        "status": "degraded",
        "mode": "degraded_static",
        "target": target,
        "changed_files": changed_files or ([target] if target != "HEAD" else []),
        "callers": static_res["callers"],
        "importers": static_res["importers"],
        "affected_flows": [],
        "candidate_tests": static_res["candidate_tests"],
        "affected_docs": static_res["affected_docs"],
        "summary": (
            f"[DEGRADED] code-review-graph offline - static search identified "
            f"{len(static_res['callers'])} caller(s), {len(static_res['candidate_tests'])} candidate test(s), "
            f"and {len(static_res['affected_docs'])} KB doc(s)."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Determine semantic blast radius, affected flows, and candidate tests."
    )
    parser.add_argument(
        "target", nargs="?", default=None, help="Target symbol or file path to evaluate"
    )
    parser.add_argument(
        "--base", default="HEAD~1", help="Git diff base for change detection (default: HEAD~1)"
    )
    parser.add_argument(
        "--max-depth", type=int, default=2, help="Dependency traversal depth (default: 2)"
    )
    parser.add_argument(
        "--repo", default=None, help="Path to repository root (auto-detected if omitted)"
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
        "--timeout", type=float, default=15.0, help="External tool timeout in seconds"
    )

    args = parser.parse_args()
    report = analyze_impact(
        repo_root=args.repo,
        target=args.target,
        base=args.base,
        max_depth=args.max_depth,
        timeout=args.timeout,
        optional=args.optional,
    )

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    status_tag = report["status"].upper()
    print("=" * 60)
    print(f"-> Along Graph Impact: [{status_tag}]")
    print("=" * 60)
    print(f"Target:          {report['target']}")
    print(f"Mode:            {report['mode']}")
    print(f"Changed Files:   {', '.join(report.get('changed_files', [])) or 'None detected'}")
    print("-" * 60)

    if report["mode"] == "code_review_graph":
        if isinstance(report.get("impact_raw"), dict) and "summary" in report["impact_raw"]:
            print("AST Impact Analysis:")
            print(report["impact_raw"]["summary"])
        elif report.get("impacted_nodes"):
            print(f"Impacted AST Nodes ({report.get('total_impacted', len(report['impacted_nodes']))} total):")
            for item in report["impacted_nodes"]:
                print(f"  - {item}")
        elif report.get("impact_raw"):
            print("AST Impact Analysis:")
            raw_s = str(report["impact_raw"])
            print(raw_s[:500] + ("..." if len(raw_s) > 500 else ""))

        if report.get("callers"):
            print("\nDirect Callers:")
            for c in report["callers"][:10]:
                print(f"  - {c}")
    else:
        print("Direct Callers (Static):")
        if report.get("callers"):
            for c in report["callers"]:
                print(f"  - {c}")
        else:
            print("  (None found)")

        if report.get("importers"):
            print("\nImporters / References (Static):")
            for imp in report["importers"]:
                print(f"  - {imp}")

    print("-" * 60)
    print("Candidate Tests:")
    if report.get("candidate_tests"):
        for t in report["candidate_tests"]:
            print(f"  - {t}")
    else:
        print("  (No direct test matches found)")

    print("-" * 60)
    print("Affected Knowledge Base Articles (docs/):")
    if report.get("affected_docs"):
        for d in report["affected_docs"]:
            print(f"  - {d}")
    else:
        print("  (No direct doc matches found)")

    print("=" * 60)
    print(f"Summary: {report['summary']}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
