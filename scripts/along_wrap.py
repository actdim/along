#!/usr/bin/env python3
"""
along_wrap.py - Transactional wrap-up engine for Along sessions and issues.

Executes automated lifecycle finalization:
- Runs pre-flight test gates before any mutations
- Audits working tree for zero-byte corrupt files
- Updates issue front-matter (status, completed, updated) and relocates to .along/ISSUES/done/
- Recompiles .along/ISSUES.md and Knowledge Base projections
- Purges ephemeral session blackboard (.along/.session/<slug>/)
- Appends formatted entry to .along/HISTORY.md when --summary is provided
- Automatically rolls back all changes via FileTransaction on failure

Usage:
  along wrap <slug> [--status done|superseded|cancelled|duplicate] [--summary "..."] [--dry-run] [-n]
  python scripts/along_wrap.py <slug> [options]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import lifecycle, repo


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Along Transactional Session and Issue Wrap Engine."
    )
    parser.add_argument(
        "slug",
        help="Slug or canonical key of the issue to wrap (e.g. feat--my-feature or my-feature)",
    )
    parser.add_argument(
        "--status",
        default="done",
        help="Closing status (done, superseded, cancelled, duplicate). Default: done",
    )
    parser.add_argument(
        "--summary",
        "-s",
        "-m",
        dest="summary",
        default=None,
        help="One-line summary for .along/HISTORY.md index",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate wrap-up operations without writing or moving files on disk",
    )
    parser.add_argument(
        "-n",
        "--no-verify",
        action="store_true",
        help="Skip pre-flight automated test execution",
    )
    parser.add_argument(
        "--agent",
        "-a",
        default=None,
        help="Explicit agent name (defaults to runtime detected agent)",
    )

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    repo_root = repo.find_repo_root()

    code = lifecycle.execute_wrap(
        repo_root=repo_root,
        slug=args.slug,
        status=args.status,
        summary=args.summary,
        dry_run=args.dry_run,
        no_verify=args.no_verify,
        agent=args.agent,
    )
    return code


if __name__ == "__main__":
    sys.exit(main())
