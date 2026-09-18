#!/usr/bin/env python3
"""
along_graph_sync.py - Code Knowledge Graph Synchronization Engine.

Builds, updates, or inspects the code-review-graph AST database for the repository:
  1. Ensures .code-review-graph-ignore exists with standard exclusions (node_modules, dist, .venv, etc.)
  2. Runs incremental update (default) or full rebuild (--full) via the pinned code-review-graph package.
  3. Reports graph status and execution metrics cleanly.

Usage:
    python scripts/along_graph_sync.py [OPTIONS]
    Options:
      --full              Perform a full graph rebuild (re-parse every file from scratch).
      --status            Only show current graph statistics without modifying the graph.
      --repo DIR          Target repository root (auto-detected if omitted).
      --base REF          Git diff base for incremental updates (default: HEAD~1 or last build).
      --skip-flows        Skip flow and community detection for faster synchronization.
      --skip-postprocess  Skip all post-processing (raw AST parse only).
      --optional          Treat missing uvx/server as a non-fatal warning (exit code 0).
      -q, --quiet         Suppress non-essential output.
      --json              Output machine-readable JSON status.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from typing import Dict, Any, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import install, repo

STANDARD_IGNORES = [
    "# Code Review Graph Exclusions",
    "node_modules/",
    "node_modules/**",
    "*node_modules*",
    "dist/",
    "dist/**",
    "*dist*",
    "build/",
    "build/**",
    "*build*",
    "out/",
    ".next/",
    ".nuxt/",
    "vendor/",
    "tmp/",
    "temp/",
    "coverage/",
    "site/",
    ".venv/",
    ".venv/**",
    "*.venv*",
    "venv/",
    "env/",
    ".git/",
    ".along/SESSIONS/",
    ".along/.session/",
    ".archive/",
    "*.min.js",
    "*.bundle.js",
    "*.map",
    "*.pyc",
    "__pycache__/",
]

CRITICAL_PATTERNS = ["node_modules", "dist", "build", ".venv", "*node_modules*"]


def ensure_ignore_file(repo_root: str, verbose: bool = False) -> Tuple[bool, List[str]]:
    """Ensure both .code-review-graph-ignore and .code-review-graphignore exist and contain critical exclusions.

    Returns (was_modified_or_created, missing_patterns_added).
    """
    modified = False
    all_added: List[str] = []

    # Check both canonical Along filename and native crg filename
    target_files = [
        os.path.join(repo_root, ".code-review-graph-ignore"),
        os.path.join(repo_root, ".code-review-graphignore"),
    ]

    for ignore_path in target_files:
        if not os.path.exists(ignore_path):
            try:
                with open(ignore_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write("\n".join(STANDARD_IGNORES) + "\n")
                if verbose:
                    print(f"-> [Graph Sync] Created {os.path.basename(ignore_path)} at {ignore_path}")
                modified = True
                all_added = list(CRITICAL_PATTERNS)
            except OSError as exc:
                if verbose:
                    print(f"[Warning] Failed to write {ignore_path}: {exc}", file=sys.stderr)
            continue

        # File exists: check if critical exclusions are present
        try:
            with open(ignore_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            continue

        missing = [p for p in CRITICAL_PATTERNS if p not in content]
        if missing:
            try:
                with open(ignore_path, "a", encoding="utf-8", newline="\n") as f:
                    f.write("\n# Additional critical exclusions appended by Along\n")
                    for item in missing:
                        f.write(f"{item}\n")
                if verbose:
                    print(f"-> [Graph Sync] Appended missing exclusions to {os.path.basename(ignore_path)}: {', '.join(missing)}")
                modified = True
                all_added.extend(missing)
            except OSError as exc:
                if verbose:
                    print(f"[Warning] Failed to append to {ignore_path}: {exc}", file=sys.stderr)

    return modified, list(set(all_added))


def parse_graph_status(output: str) -> Dict[str, Any]:
    """Parse text output of 'code-review-graph status' into structured dict."""
    res: Dict[str, Any] = {
        "nodes": 0,
        "edges": 0,
        "files": 0,
        "languages": [],
        "last_updated": None,
        "built_on_branch": None,
        "built_at_commit": None,
    }
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("Nodes:"):
            try:
                res["nodes"] = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.startswith("Edges:"):
            try:
                res["edges"] = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.startswith("Files:"):
            try:
                res["files"] = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.startswith("Languages:"):
            langs = line.split(":", 1)[1].strip()
            res["languages"] = [l.strip() for l in langs.split(",") if l.strip()]
        elif line.startswith("Last updated:"):
            res["last_updated"] = line.split(":", 1)[1].strip()
        elif line.startswith("Built on branch:"):
            res["built_on_branch"] = line.split(":", 1)[1].strip()
        elif line.startswith("Built at commit:"):
            res["built_at_commit"] = line.split(":", 1)[1].strip()
    return res


def run_graph_sync(
    repo_root: Optional[str] = None,
    full: bool = False,
    status_only: bool = False,
    base: Optional[str] = None,
    skip_flows: bool = False,
    skip_postprocess: bool = False,
    quiet: bool = False,
    optional: bool = False,
    timeout: float = 300.0,
) -> Dict[str, Any]:
    """Execute code-review-graph build, update, or status.

    Returns dict with execution outcome, status, and stats.
    """
    if not repo_root:
        repo_root = repo.find_repo_root(os.getcwd())

    ensure_ignore_file(repo_root, verbose=not quiet)

    uvx_bin = shutil.which("uvx")
    package_spec = install.MCP_SERVER_PACKAGE
    version = install.MCP_SERVER_VERSION

    if not uvx_bin:
        msg = "uvx executable not found in PATH. Install uv (https://astral.sh/uv)."
        if not quiet and not optional:
            print(f"[Error] {msg}", file=sys.stderr)
        elif not quiet and optional:
            print(f"-> [Graph Sync] Skipped (uvx not available in PATH)")
        return {
            "success": optional,
            "status": "skipped" if optional else "error",
            "message": msg,
            "package": package_spec,
            "version": version,
            "stats": {},
        }

    # Determine command: status, build (full), or update (incremental)
    if status_only:
        subcmd = "status"
        cmd = [uvx_bin, package_spec, "status", "--repo", repo_root]
    elif full:
        subcmd = "build"
        cmd = [uvx_bin, package_spec, "build", "--repo", repo_root]
        if skip_flows:
            cmd.append("--skip-flows")
        if skip_postprocess:
            cmd.append("--skip-postprocess")
        if quiet:
            cmd.append("-q")
    else:
        subcmd = "update"
        cmd = [uvx_bin, package_spec, "update", "--repo", repo_root]
        if base:
            cmd.extend(["--base", base])
        if skip_flows:
            cmd.append("--skip-flows")
        if skip_postprocess:
            cmd.append("--skip-postprocess")
        if quiet:
            cmd.append("-q")

    if not quiet:
        mode_label = "Full Rebuild" if full else ("Status" if status_only else "Incremental Update")
        print(f"-> [Graph Sync] Running {mode_label} ({package_spec})...")

    try:
        proc_res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        combined_output = ((proc_res.stdout or "") + "\n" + (proc_res.stderr or "")).strip()

        if proc_res.returncode != 0:
            if not quiet and not optional:
                print(f"[Error] Graph sync failed (exit code {proc_res.returncode}):\n{combined_output}", file=sys.stderr)
            elif not quiet and optional:
                print(f"-> [Graph Sync] Non-fatal failure: exit code {proc_res.returncode}")
            return {
                "success": optional,
                "status": "error",
                "exit_code": proc_res.returncode,
                "message": combined_output,
                "package": package_spec,
                "stats": {},
            }

        # If we just built or updated, fetch status cleanly
        stats: Dict[str, Any] = {}
        if not status_only:
            stat_cmd = [uvx_bin, package_spec, "status", "--repo", repo_root]
            stat_res = subprocess.run(stat_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            if stat_res.returncode == 0 and stat_res.stdout:
                stats = parse_graph_status(stat_res.stdout)
        else:
            stats = parse_graph_status(combined_output)

        if not quiet:
            if status_only:
                print(combined_output)
            else:
                nodes_cnt = stats.get("nodes", 0)
                files_cnt = stats.get("files", 0)
                edges_cnt = stats.get("edges", 0)
                print(f"-> [Graph Sync] [OK] Completed: {files_cnt} files, {nodes_cnt} nodes, {edges_cnt} edges indexed.")

        return {
            "success": True,
            "status": "ok",
            "mode": subcmd,
            "message": combined_output,
            "stats": stats,
        }

    except subprocess.TimeoutExpired:
        msg = f"Graph sync timed out after {timeout} seconds"
        if not quiet:
            print(f"[Error] {msg}", file=sys.stderr)
        return {
            "success": optional,
            "status": "timeout",
            "message": msg,
            "stats": {},
        }
    except OSError as exc:
        msg = f"Graph sync execution failed: {exc}"
        if not quiet:
            print(f"[Error] {msg}", file=sys.stderr)
        return {
            "success": optional,
            "status": "error",
            "message": msg,
            "stats": {},
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronize or inspect code-review-graph code intelligence database."
    )
    parser.add_argument(
        "--full", action="store_true", help="Perform a full rebuild (re-parse all files)"
    )
    parser.add_argument(
        "--status", action="store_true", help="Display current graph status and stats without changes"
    )
    parser.add_argument(
        "--repo", default=None, help="Target repository directory (defaults to auto-detect)"
    )
    parser.add_argument(
        "--base", default=None, help="Git ref to diff against for incremental updates (e.g. HEAD~1)"
    )
    parser.add_argument(
        "--skip-flows", action="store_true", help="Skip flow and community detection for faster sync"
    )
    parser.add_argument(
        "--skip-postprocess", action="store_true", help="Skip all post-processing (raw AST parse only)"
    )
    parser.add_argument(
        "--optional", action="store_true", help="Treat missing uvx as non-fatal warning (exit code 0)"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress progress output"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output machine-readable JSON summary"
    )
    parser.add_argument(
        "--timeout", type=float, default=300.0, help="Process timeout in seconds (default: 300)"
    )

    args = parser.parse_args()

    res = run_graph_sync(
        repo_root=args.repo,
        full=args.full,
        status_only=args.status,
        base=args.base,
        skip_flows=args.skip_flows,
        skip_postprocess=args.skip_postprocess,
        quiet=args.quiet or args.json,
        optional=args.optional,
        timeout=args.timeout,
    )

    if args.json:
        print(json.dumps(res, indent=2))

    return 0 if res["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
