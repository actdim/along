#!/usr/bin/env python3
"""
along_conflict_check.py - CLI tool to predict git merge conflicts before merging.

Compares HEAD against a target branch by analyzing their common merge-base ancestor,
detecting overlapping modified files, and identifying AST symbol collisions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap

# Ensure runtime dependencies
bootstrap.ensure_deps()

from alongkit import conflict_check, repo


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Predict merge conflict risks and symbol collisions between HEAD and a target branch."
    )
    parser.add_argument("branch", help="Target branch to compare against HEAD.")
    parser.add_argument("--json", action="store_true", help="Output report in JSON format.")

    args = parser.parse_args()
    repo_root = repo.find_repo_root()

    report = conflict_check.predict_conflicts(repo_root, args.branch)

    if args.json:
        data = {
            "target_branch": report.target_branch,
            "merge_base": report.merge_base,
            "risk_level": report.risk_level,
            "overlapping_files": report.overlapping_files,
            "colliding_symbols": report.colliding_symbols,
            "notes": report.notes,
        }
        print(json.dumps(data, indent=2))
    else:
        print(conflict_check.format_prediction_report(report))

    sys.exit(1 if report.risk_level in ("HIGH", "UNKNOWN") else 0)


if __name__ == "__main__":
    main()
