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

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import gates, proc, repo


# Both gates live in alongkit.gates, shared with the release engine, which used to
# carry its own copies that discarded the sanitizer's output.
typography_gate = gates.typography_gate


def get_active_issue(repo_root):
    issues_board = os.path.join(repo.state_dir(repo_root), "ISSUES.md")
    if not os.path.exists(issues_board):
        return None
    try:
        with open(issues_board, "r", encoding="utf-8") as f:
            lines = f.readlines()
        in_active = False
        for line in lines:
            if line.startswith("## Active"):
                in_active = True
                continue
            elif line.startswith("## "):
                in_active = False
                continue
            if in_active:
                m = re.search(r'\[[ ~]\]\s*`\((\w+)\)`\s*\[([^\]]+)\]', line)
                if m:
                    return {"type": m.group(1), "slug": m.group(2)}
    except OSError as exc:
        print(f"[Warning] cannot read {issues_board}: {exc}", file=sys.stderr)
    return None


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


def main():
    repo_root = repo.find_repo_root()
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = [a for a in sys.argv[1:] if a.startswith("-")]

    push = "--push" in flags or "-p" in flags
    skip_tests = "--no-verify" in flags or "-n" in flags
    fix_typography = "--fix-typography" in flags

    if not args:
        print("Usage: python along_commit.py \"<commit message>\" "
              "[--push] [--no-verify] [--fix-typography]")
        print("Example: python along_commit.py \"add cytoscape graph view\" -p")
        sys.exit(1)

    raw_msg = " ".join(args)

    print("==================================================")
    print("-> Along Smart Committer")
    print(f"   Target: {repo_root}")
    print("==================================================")

    # 1. Mandatory Pre-Commit Tests
    if not skip_tests:
        if not gates.run_repository_tests(repo_root, "Pre-Commit Quality Gate"):
            print("Commit aborted. Fix failing tests before committing.", file=sys.stderr)
            sys.exit(1)

    # 2. Pre-commit typography check. Reports and aborts; --fix-typography rewrites.
    if not skip_tests:
        if not typography_gate(repo_root, "Pre-Commit Quality Gate",
                               allow_fix=fix_typography):
            print("Commit aborted. Clean the typography before committing.",
                  file=sys.stderr)
            sys.exit(1)

    # 3. Extract active issue context
    active_issue = get_active_issue(repo_root)
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
    if push:
        print("-> Pushing to remote repository...")
        res = proc.git(["push"], cwd=repo_root)
        if res.ok:
            print("-> Successfully pushed to remote.")
        else:
            print(f"[Warning] Git push failed:\n{res.stderr}", file=sys.stderr)


if __name__ == "__main__":
    main()
