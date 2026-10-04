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
  along wrap <slug> (--decisions ADR-a,ADR-b | --no-decisions) [--status|-s done|superseded|cancelled|duplicate]
             [--summary|-m "..."] [--force-reason "..."] [--dry-run] [-n]
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
        "-s",
        default="done",
        choices=["done", "superseded", "cancelled", "duplicate"],
        help="Closing status (done, superseded, cancelled, duplicate). Default: done",
    )
    parser.add_argument(
        "--summary",
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
    # Were architectural decisions made? Wrap requires an explicit answer
    # [feat--wrap-session-log-from-blackboard].
    answer = parser.add_mutually_exclusive_group(required=True)
    answer.add_argument(
        "--decisions",
        "-d",
        default=None,
        help="Comma-separated ADR keys recorded in this session (create them first via along decision create)",
    )
    answer.add_argument(
        "--no-decisions",
        action="store_true",
        help="Confirm that the session made no architectural decisions",
    )
    parser.add_argument(
        "--force-reason",
        default=None,
        help="Wrap a role-based blackboard with open steps or missing reviews; the reason goes to the log",
    )

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    repo_root = repo.find_repo_root()
    decisions = [] if args.no_decisions else [d.strip() for d in args.decisions.split(",") if d.strip()]

    code = lifecycle.execute_wrap(
        repo_root=repo_root,
        slug=args.slug,
        status=args.status,
        summary=args.summary,
        dry_run=args.dry_run,
        no_verify=args.no_verify,
        agent=args.agent,
        decisions=decisions,
        force_reason=args.force_reason,
    )
    if code == 0:
        # Not verifiable mechanically, so the engine only reminds (skills/along-wrap Phase A).
        print("-> Wrap reminder: README.md and AGENTS.md 'Project specifics' current? New terms in "
              ".along/GLOSSARY.md? .along/VISION.md roadmap touched only if scope/roadmap changed?")
    return code


if __name__ == "__main__":
    sys.exit(main())
