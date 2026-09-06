#!/usr/bin/env python3
"""
along_commit.py - Smart, ASCII-safe, and issue-linked Conventional Committer for Along.

Features:
- Checks for banned typography before committing (NBSP, ZWSP, curly quotes, etc.)
- Auto-extracts active issue from .along/ISSUES.md and appends issue reference
- Enforces or formats Conventional Commits (feat, fix, docs, refactor, test, chore)
- Supports optional --push flag

The typography gate reports and aborts; it does not rewrite the working tree on its
own. It used to: every commit triggered a repository-wide read-modify-write with a
lossy read, so a single non-UTF8 file lost its undecodable bytes and the same command
then staged and committed the damage. Passing --fix-typography opts back into the
rewrite, explicitly and per invocation. See
`[bug--typography-sanitizer-destroys-non-utf8-files]`.
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap
bootstrap.ensure_deps()


from alongkit import entities, gates, proc, repo


# Both gates live in alongkit.gates, shared with the release engine, which used to
# carry its own copies that discarded the sanitizer's output.
typography_gate = gates.typography_gate


def get_active_issue(repo_root, explicit_slug=None, strict=False):
    """Resolve the active issue from SSOT entity files (.along/ISSUES/*.md)."""
    issue, _ = entities.resolve_active_issue(
        repo_root, explicit_slug=explicit_slug, strict=strict
    )
    return issue


def format_commit_message(raw_msg, active_issue):
    msg = raw_msg.strip()
    # Check if already conventional commit (type(scope): message or type: message)
    conv_match = re.match(r'^(\w+)(?:\(([^)]+)\))?:\s*(.+)$', msg)
    if not conv_match and active_issue:
        itype = active_issue["type"]
        # Map Along issue types to Conventional Commits
        type_map = {"feat": "feat", "bug": "fix", "debt": "refactor", "task": "chore", "docs": "docs"}
        ctype = type_map.get(itype, "chore")
        msg = f"{ctype}: {msg}"

    # Append issue reference if available and not already present
    if active_issue:
        slug = active_issue["slug"]
        if slug not in msg:
            msg = f"{msg} (refs #{slug})"

    return msg


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Along Smart Conventional Committer with quality and typography gates."
    )
    parser.add_argument("message", nargs="*", help="Commit message (positional)")
    parser.add_argument("-m", "--message-flag", dest="msg_flag", help="Commit message (-m \"...\")")
    parser.add_argument("-i", "--issue", dest="issue", help="Explicit issue slug to bind (refs #<slug>)")
    parser.add_argument("-p", "--push", action="store_true", help="Push to remote after successful commit")
    parser.add_argument("-n", "--no-verify", dest="skip_tests", action="store_true", help="Skip pre-commit gates")
    parser.add_argument("--fix-typography", action="store_true", help="Fix typography automatically before committing")
    parser.add_argument("--strict", action="store_true", help="Fail if active issue cannot be determined unambiguously")
    return parser.parse_args(argv)


def main(argv=None):
    parsed = parse_args(argv)
    repo_root = repo.find_repo_root()

    msg_parts = parsed.message
    raw_msg = (parsed.msg_flag or " ".join(msg_parts)).strip()

    if not raw_msg:
        print("Usage: python along_commit.py \"<commit message>\" [-i <slug>] "
              "[--push] [--no-verify] [--fix-typography] [--strict]", file=sys.stderr)
        print("Example: python along_commit.py \"add cytoscape graph view\" -i feat--cytoscape-graph -p", file=sys.stderr)
        sys.exit(1)

    print("==================================================")
    print("-> Along Smart Committer")
    print(f"   Target: {repo_root}")
    print("==================================================")

    # 1. Mandatory Pre-Commit Tests
    if not parsed.skip_tests:
        if not gates.run_repository_tests(repo_root, "Pre-Commit Quality Gate"):
            print("Commit aborted. Fix failing tests before committing.", file=sys.stderr)
            sys.exit(1)

    # 2. Pre-commit typography check. Reports and aborts; --fix-typography rewrites.
    if not parsed.skip_tests:
        if not typography_gate(repo_root, "Pre-Commit Quality Gate",
                               allow_fix=parsed.fix_typography):
            print("Commit aborted. Clean the typography before committing.",
                  file=sys.stderr)
            sys.exit(1)

    # 3. Extract active issue context deterministically from SSOT
    try:
        active_issue, warnings = entities.resolve_active_issue(
            repo_root,
            explicit_slug=parsed.issue,
            strict=parsed.strict,
        )
    except ValueError as exc:
        print(f"[Error] {exc}", file=sys.stderr)
        sys.exit(1)

    for warn in warnings:
        print(f"[Warning] {warn}", file=sys.stderr)

    final_msg = format_commit_message(raw_msg, active_issue)
    print(f"-> Commit message: \"{final_msg}\"")

    # 4. Stage changes and commit
    staged = proc.git(["add", "-A"], cwd=repo_root)
    if not staged.ok:
        print(f"[Error] Git staging failed: {staged.stderr.strip()}", file=sys.stderr)
        sys.exit(1)

    res = proc.git(["commit", "-m", final_msg], cwd=repo_root)
    if not res.ok:
        if "nothing to commit" in res.stdout or "nothing to commit" in res.stderr:
            print("-> [Notice] Nothing to commit, working tree clean.")
            sys.exit(0)
        print(f"[Error] Git commit failed:\n{res.stderr}", file=sys.stderr)
        sys.exit(res.returncode)
    print("-> Git commit created successfully.")
    print(res.out)

    # 5. Optional Push
    if parsed.push:
        print("-> Pushing to remote repository...")
        res = proc.git(["push"], cwd=repo_root)
        if res.ok:
            print("-> Successfully pushed to remote.")
        else:
            print(f"[Warning] Git push failed:\n{res.stderr}", file=sys.stderr)


if __name__ == "__main__":
    main()

