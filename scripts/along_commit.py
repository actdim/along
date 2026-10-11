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


from alongkit import attribution, bypass, entities, gates, gitgates, proc, repo, session, verify


# Both gates live in alongkit.gates, shared with the release engine, which used to
# carry its own copies that discarded the sanitizer's output.
typography_gate = gates.typography_gate


def get_active_issue(repo_root, explicit_slug=None, strict=False):
    """Resolve the active issue from SSOT entity files (.along/ISSUES/*.md)."""
    issue, _ = entities.resolve_active_issue(
        repo_root, explicit_slug=explicit_slug, strict=strict
    )
    return issue


def _abort(repo_root, message):
    """Abort the commit; the failure is what a later `-n --reason` bypass must follow."""
    bypass.record_failure(repo_root, bypass.PRE_COMMIT)
    print(message, file=sys.stderr)
    sys.exit(1)


def _planned_commit_paths(repo_root, parsed):
    """Repo-relative paths this commit will contain (before staging), [] when git cannot say."""
    if parsed.all_files or parsed.paths:
        args = ["status", "--porcelain", "-z", "--untracked-files=all"]
        if parsed.paths:
            args += ["--", *parsed.paths]
        res = proc.git(args, cwd=repo_root)
        if not res.ok:
            return []
        paths = []
        entries = (res.stdout or "").split("\0")
        i = 0
        while i < len(entries):
            entry = entries[i]
            i += 1
            if len(entry) < 4:
                continue
            paths.append(entry[3:])
            if entry[0] in ("R", "C"):
                i += 1  # the rename source follows
        return paths
    res = proc.git(["diff", "--cached", "--name-only"], cwd=repo_root)
    return [p.strip() for p in (res.stdout or "").splitlines() if p.strip()] if res.ok else []


def _staged_or_worktree_diff(repo_root, path):
    """Diff of `path` against HEAD (staged and unstaged), '' when unavailable."""
    res = proc.git(["diff", "HEAD", "--", path], cwd=repo_root)
    return res.stdout if res.ok else ""


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

    # Append the binding unless the message already carries one of the two forms the
    # commit_issue_binding gate accepts; a slug named in prose is not a binding.
    # See [bug--along-commit-drops-issue-binding].
    if active_issue:
        slug = active_issue["slug"]
        bindings = (f"(refs #{slug})", f"[{active_issue.get('type', '')}--{slug}]")
        if not any(b in msg for b in bindings):
            msg = f"{msg} (refs #{slug})"

    return msg


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Along Smart Conventional Committer with quality and typography gates."
    )
    parser.add_argument("message", nargs="*", help="Commit message (positional)")
    parser.add_argument("-m", "--message-flag", dest="msg_flag", help="Commit message (-m \"...\")")
    parser.add_argument("-i", "--issue", dest="issue", help="Explicit issue slug to bind (refs #<slug>)")
    parser.add_argument("-a", "--all", dest="all_files", action="store_true", help="Stage all changes (git add -A) before committing")
    parser.add_argument("--paths", nargs="+", help="Specific paths to stage before committing")
    parser.add_argument("-p", "--push", action="store_true", help="Push to remote after successful commit")
    parser.add_argument("-n", "--no-verify", dest="skip_tests", action="store_true",
                        help="Skip pre-commit gates (needs --reason; recorded as an Along-Bypass trailer)")
    parser.add_argument("--reason", dest="bypass_reason", help="Why the user accepts skipping the gates (-n)")
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
              "[-a] [--paths <file>...] [--push] [--no-verify] [--fix-typography] [--strict]", file=sys.stderr)
        print("Example: python along_commit.py \"add cytoscape graph view\" -i feat--cytoscape-graph -a -p", file=sys.stderr)
        sys.exit(1)

    print("==================================================")
    print("-> Along Smart Committer")
    print(f"   Target: {repo_root}")
    print("==================================================")

    # A bypass is the user's decision, with a reason, and it is recorded
    # [feat--gate-friction-and-bypass-accountability] REQ-3.
    bypass_trailer = None
    if parsed.skip_tests:
        bypass_trailer = bypass.guard(repo_root, bypass.PRE_COMMIT, parsed.bypass_reason, slug=parsed.issue)
        if not bypass_trailer:
            sys.exit(2)

    # 1. Pre-Commit Syntax Gate
    if not parsed.skip_tests:
        if not gates.syntax_gate(repo_root, "Pre-Commit Quality Gate"):
            _abort(repo_root, "Commit aborted. Fix syntax errors before committing.")

    # 2. Pre-Commit Markdown Link Integrity Gate
    if not parsed.skip_tests:
        if not gates.link_integrity_gate(repo_root, "Pre-Commit Quality Gate", strict=parsed.strict):
            _abort(repo_root, "Commit aborted. Fix broken Markdown links before committing.")

    # 3. Mandatory Pre-Commit Tests, under the declared verify policy. A change of only
    # documentation / Along state skips them with a note [bug--test-gate-no-tests-policy].
    if not parsed.skip_tests:
        planned = _planned_commit_paths(repo_root, parsed)
        if planned and verify.docs_only_change(repo_root, planned, lambda p: _staged_or_worktree_diff(repo_root, p)):
            print("-> [Pre-Commit Quality Gate] Only documentation / Along state changes: tests skipped.")
        else:
            outcome = gates.run_test_gate(repo_root, "Pre-Commit Quality Gate")
            if outcome not in (gates.TESTS_PASSED, gates.TESTS_SKIPPED):
                _abort(repo_root, f"Commit aborted: {gates.test_gate_abort_reason(outcome)}.")

    # 4. Pre-commit typography check. Reports and aborts; --fix-typography rewrites.
    if not parsed.skip_tests:
        if not typography_gate(repo_root, "Pre-Commit Quality Gate",
                               allow_fix=parsed.fix_typography):
            _abort(repo_root, "Commit aborted. Clean the typography before committing.")

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

    # AI co-author trailers make GitHub list the vendor as a contributor.
    if not attribution.allow_ai_coauthor(repo_root):
        cleaned = attribution.strip_ai_coauthor_trailers(raw_msg).strip()
        if cleaned != raw_msg:
            print("-> Removed AI Co-Authored-By trailer(s) from the message.")
            raw_msg = cleaned

    final_msg = format_commit_message(raw_msg, active_issue)
    print(f"-> Commit message: \"{final_msg}\"")

    # 4. Stage changes according to explicit flags
    if parsed.all_files:
        print("-> Staging all working tree changes (--all)...")
        staged = proc.git(["add", "-A"], cwd=repo_root)
        if not staged.ok:
            print(f"[Error] Git staging failed: {staged.stderr.strip()}", file=sys.stderr)
            sys.exit(1)
    elif parsed.paths:
        print(f"-> Staging specified paths: {' '.join(parsed.paths)}...")
        staged = proc.git(["add", "--", *parsed.paths], cwd=repo_root)
        if not staged.ok:
            print(f"[Error] Git staging failed: {staged.stderr.strip()}", file=sys.stderr)
            sys.exit(1)

    # Inspect what is currently staged in the index
    staged_status = proc.git(["diff", "--cached", "--name-only"], cwd=repo_root)
    staged_files = [f.strip() for f in (staged_status.stdout or "").splitlines() if f.strip()]
    if not staged_files:
        print("[Error] No staged changes to commit.", file=sys.stderr)
        print("Stage files with 'git add <files>', pass '--paths <file>...', or pass '--all' / '-a' to stage all changes.", file=sys.stderr)
        sys.exit(1)

    # 5. Entity reference integrity of the staged .along/ entities: block only the
    # dangling references / enum violations this commit introduces.
    if not parsed.skip_tests and gitgates.touches_entities(staged_files):
        head = "HEAD" if proc.git(["rev-parse", "--verify", "-q", "HEAD"], cwd=repo_root).ok else None
        broken = gitgates.check_entity_references(repo_root, staged_files, "git", "index", head)
        if broken:
            print(gitgates.format_report(broken, "Pre-Commit Quality Gate"), file=sys.stderr)
            _abort(repo_root, "Commit aborted. Fix the entity references before committing.")
        print("-> [Pre-Commit Quality Gate] Entity references intact.")

    # 6. Blackboard Records of committed session logs are append-only
    # [bug--session-records-not-captured] REQ-7.
    if not parsed.skip_tests:
        head = "HEAD" if proc.git(["rev-parse", "--verify", "-q", "HEAD"], cwd=repo_root).ok else None
        cut = gitgates.check_session_records(repo_root, staged_files, "git", head)
        if cut:
            print(gitgates.format_report(cut, "Pre-Commit Quality Gate"), file=sys.stderr)
            _abort(repo_root, "Commit aborted. Restore the removed Blackboard Record lines.")

    if bypass_trailer:
        final_msg = f"{final_msg}\n\n{bypass_trailer}"

    print(f"-> Committing {len(staged_files)} staged file(s):")
    for f in staged_files[:10]:
        print(f"   - {f}")
    if len(staged_files) > 10:
        print(f"   ... and {len(staged_files) - 10} more.")

    res = proc.git(["commit", "-m", final_msg], cwd=repo_root)
    if not res.ok:
        if "nothing to commit" in res.stdout or "nothing to commit" in res.stderr:
            print("-> [Notice] Nothing to commit, working tree clean.")
            sys.exit(0)
        print(f"[Error] Git commit failed:\n{res.stderr}", file=sys.stderr)
        sys.exit(res.returncode)
    print("-> Git commit created successfully.")
    print(res.out)

    # The completion token `along wrap` left for this issue is used up by its commit.
    if active_issue and session.consume_completion_token(
            repo_root, session.current_session_key(), str(active_issue["slug"])):
        print(f"-> Completion token for '{active_issue['slug']}' used.")

    # 5. Optional Push
    if parsed.push:
        print("-> Pushing to remote repository...")
        res = proc.git(["push"], cwd=repo_root)
        if res.ok:
            print("-> Successfully pushed to remote.")
        else:
            print(f"[Error] Git push failed:\n{res.stderr}", file=sys.stderr)
            sys.exit(res.returncode if res.returncode != 0 else 1)


if __name__ == "__main__":
    main()

