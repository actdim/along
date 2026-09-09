#!/usr/bin/env python3
"""
along_graph_check.py - Preflight Health Check & Verification Engine for code-review-graph MCP.

Validates that:
1. uv / uvx is installed and accessible in PATH.
2. The pinned code-review-graph MCP package starts and responds cleanly.
3. .code-review-graph-ignore exists in the repository root and excludes critical paths.

Usage:
    python scripts/along_graph_check.py [--json] [--repo DIR] [--timeout SECONDS]
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


def probe_mcp_server(package_spec: str, timeout: float = 7.0) -> Tuple[bool, int, str]:
    """Probe the MCP server package by running --help through uvx.

    Returns (success, exit_code, output_or_error).
    """
    uvx_path = shutil.which("uvx")
    if not uvx_path:
        return False, -1, "uvx executable not found in PATH"

    cmd = [uvx_path, package_spec, "--help"]
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        success = (proc.returncode == 0)
        return success, proc.returncode, output.strip()
    except subprocess.TimeoutExpired:
        return False, -2, f"Timed out after {timeout} seconds"
    except OSError as exc:
        return False, -3, f"Execution failed: {exc}"


def check_ignore_file(repo_root: str) -> Tuple[bool, List[str]]:
    """Check if .code-review-graph-ignore exists and contains recommended exclusions."""
    ignore_path = os.path.join(repo_root, ".code-review-graph-ignore")
    if not os.path.isfile(ignore_path):
        return False, []

    recommended = ["node_modules", "dist", "build", ".git"]
    missing = []
    try:
        with open(ignore_path, "r", encoding="utf-8") as f:
            content = f.read()
        for rec in recommended:
            if rec not in content:
                missing.append(rec)
    except OSError:
        return True, ["<unreadable>"]

    return True, missing


def run_graph_check(repo_root: Optional[str] = None, timeout: float = 7.0) -> Dict[str, Any]:
    """Execute full health check of the code-review-graph MCP server and repository filters."""
    if not repo_root:
        repo_root = repo.find_repo_root(os.getcwd())

    uvx_bin = shutil.which("uvx")
    uv_bin = shutil.which("uv")

    package_spec = install.MCP_SERVER_PACKAGE
    version = install.MCP_SERVER_VERSION

    probe_ok = False
    probe_code = -1
    probe_msg = ""

    if uvx_bin:
        probe_ok, probe_code, probe_msg = probe_mcp_server(package_spec, timeout=timeout)
    else:
        probe_msg = "uvx not found in PATH. Install uv (https://astral.sh/uv)."

    ignore_exists, missing_rec = check_ignore_file(repo_root)

    # Determine overall status: HEALTHY, DEGRADED, or OFFLINE
    if probe_ok and ignore_exists:
        status = "healthy"
        summary = f"code-review-graph=={version} is operational and configured."
    elif probe_ok and not ignore_exists:
        status = "degraded"
        summary = f"code-review-graph=={version} is responsive, but .code-review-graph-ignore is missing."
    else:
        status = "offline"
        summary = f"code-review-graph=={version} probe failed ({probe_msg})."

    recommendations: List[str] = []
    if not uvx_bin:
        recommendations.append("Install uv package manager from https://astral.sh/uv to run uvx.")
    if not probe_ok and uvx_bin:
        recommendations.append(f"Verify that 'uvx {package_spec} --help' executes without errors in terminal.")
    if not ignore_exists:
        recommendations.append("Create .code-review-graph-ignore excluding node_modules/, dist/, and build/.")
    elif missing_rec:
        recommendations.append(f"Consider adding missing exclusions to .code-review-graph-ignore: {', '.join(missing_rec)}")

    return {
        "status": status,
        "summary": summary,
        "mcp_server": install.MCP_SERVER_NAME,
        "version": version,
        "package": package_spec,
        "uvx_path": uvx_bin,
        "uv_path": uv_bin,
        "probe_success": probe_ok,
        "probe_exit_code": probe_code,
        "probe_message": probe_msg.splitlines()[0] if probe_msg else "",
        "ignore_file_present": ignore_exists,
        "missing_recommended_ignores": missing_rec,
        "recommendations": recommendations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preflight Health Check for code-review-graph MCP server."
    )
    parser.add_argument(
        "--json", action="store_true", help="Output machine-readable JSON"
    )
    parser.add_argument(
        "--repo", default=None, help="Path to repository root (defaults to auto-detect)"
    )
    parser.add_argument(
        "--timeout", type=float, default=7.0, help="Probe timeout in seconds (default: 7.0)"
    )

    args = parser.parse_args()
    report = run_graph_check(repo_root=args.repo, timeout=args.timeout)

    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "healthy" else 1

    status = report["status"].upper()
    print("=" * 60)
    print(f"-> Along Graph Check: [{status}]")
    print("=" * 60)
    print(f"MCP Server:  {report['mcp_server']} (pinned: {report['version']})")
    print(f"Package:     {report['package']}")
    print(f"uvx binary:  {report['uvx_path'] or 'NOT FOUND'}")
    print(f"Probe:       {'OK (exit code 0)' if report['probe_success'] else 'FAILED: ' + report['probe_message']}")
    print(f"Ignore File: {'PRESENT' if report['ignore_file_present'] else 'MISSING (.code-review-graph-ignore)'}")
    print("-" * 60)
    print(f"Summary:     {report['summary']}")

    if report["recommendations"]:
        print("-" * 60)
        print("Actionable Recommendations:")
        for rec in report["recommendations"]:
            print(f"  - {rec}")
    print("=" * 60)

    return 0 if report["status"] == "healthy" else 1


if __name__ == "__main__":
    sys.exit(main())
