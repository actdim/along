#!/usr/bin/env python3
"""
along_resolve.py - Semantic conflict auto-resolution engine for documentation and markdown.

Detects unmerged markdown documentation files (docs/**/*.md, README.md, AGENTS.md),
parses conflict hunks outside fenced code, performs structural reconciliation
(non-overlapping sections, checklist deduplication, table rows), verifies link integrity
and clean ASCII typography, and synchronizes the Knowledge Base via along kb sync.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap

# Ensure runtime dependencies
bootstrap.ensure_deps()

from alongkit import proc, repo, resolve, resolve_code, textio


def resolve_file(abs_path: str, repo_root: str, dry_run: bool = False,
                 strict: bool = False) -> Tuple[bool, List[str]]:
    """Resolve conflicts in one file. Returns (clean, notes)."""
    rel_path = repo.safe_relpath(abs_path, repo_root).replace("\\", "/")
    if not os.path.isfile(abs_path):
        return False, [f"File not found: {rel_path}"]

    try:
        content = textio.read_text(abs_path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return False, [f"Failed to read {rel_path}: {exc}"]

    merged, clean, warnings = resolve.resolve_markdown_content(
        content, file_path=abs_path, repo_root=repo_root, strict=strict
    )

    notes = [f"{rel_path}: {w}" for w in warnings]

    if not dry_run and merged != content:
        try:
            textio.write_text(abs_path, merged)
        except (OSError, ValueError) as exc:
            return False, notes + [f"Failed to write {rel_path}: {exc}"]

    return clean, notes


def run_resolve(args: argparse.Namespace) -> int:
    repo_root = repo.find_repo_root()
    target_files: List[str] = []

    if args.files:
        for f in args.files:
            target_files.append(os.path.abspath(f) if os.path.isabs(f) else os.path.join(repo_root, f))

    # Detect whether code mode is requested or inferred from file arguments
    is_code_mode = args.code
    if not is_code_mode and not args.docs and target_files:
        if any(resolve_code.is_source_code_file(f) for f in target_files):
            is_code_mode = True

    if is_code_mode:
        if not target_files:
            unmerged = resolve_code.get_unmerged_code_files(repo_root)
            for u in unmerged:
                target_files.append(os.path.join(repo_root, u))

        if not target_files:
            print("No conflicted source code files detected.")
            return 0

        print(f"-> Along Resolve: Processing {len(target_files)} source code file(s)...")
        success, notes = resolve_code.resolve_and_verify_code(
            repo_root,
            target_files=target_files,
            dry_run=args.dry_run,
            strict=args.strict,
            run_tests=not args.no_tests,
        )
        for n in notes:
            print(f"   {n}")

        if success:
            print("-> [OK] Source code conflicts cleanly resolved and verified.")
            return 0
        else:
            print("-> [FAIL] Source code conflict resolution failed quality gates.")
            return 1

    # Documentation mode (default or --docs)
    if not target_files:
        unmerged = resolve.get_unmerged_docs(repo_root)
        for u in unmerged:
            target_files.append(os.path.join(repo_root, u))

    if not target_files:
        print("No conflicted documentation files detected.")
        return 0

    print(f"-> Along Resolve: Processing {len(target_files)} file(s)...")
    all_clean = True
    any_modified = False

    for target in target_files:
        rel = repo.safe_relpath(target, repo_root).replace("\\", "/")
        clean, notes = resolve_file(target, repo_root, dry_run=args.dry_run, strict=args.strict)
        status_label = "[OK]" if clean else "[CONFLICT]"
        print(f"   {status_label} {rel}")
        for n in notes:
            print(f"      - {n}")
        if not clean:
            all_clean = False
        else:
            any_modified = True

    if not args.dry_run and any_modified and not args.no_kb_sync:
        # Run along kb sync if docs were modified
        kb_script = repo.resolve_tool_script("along_kb_sync.py", repo_root)
        if kb_script and os.path.isfile(kb_script):
            print("-> Synchronizing Knowledge Base via along kb sync...")
            res = proc.run_capture([sys.executable, kb_script], cwd=repo_root)
            if res.ok:
                print("   [OK] Knowledge Base recompiled successfully.")
            else:
                print(f"   [WARN] kb-sync completed with warnings/errors: {res.stderr.strip() or res.stdout.strip()}")

    if not all_clean and args.strict:
        return 1
    return 0 if all_clean else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Semantic and test-gated conflict auto-resolution engine for docs and source code."
    )
    parser.add_argument(
        "--docs", action="store_true", default=False,
        help="Resolve unmerged documentation files in docs/ and root markdown."
    )
    parser.add_argument(
        "--code", action="store_true", default=False,
        help="Resolve unmerged source code files with test-gated verification."
    )
    parser.add_argument(
        "--no-tests", action="store_true", default=False,
        help="Skip running test runner during code conflict resolution verification."
    )
    parser.add_argument(
        "--check", "--dry-run", dest="dry_run", action="store_true",
        help="Simulate resolution without modifying files on disk."
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Fail with exit code 1 if any conflict cannot be resolved cleanly."
    )
    parser.add_argument(
        "--no-kb-sync", action="store_true",
        help="Skip automatic along kb sync after resolution."
    )
    parser.add_argument(
        "files", nargs="*",
        help="Specific files to resolve (optional)."
    )

    args = parser.parse_args()
    if not args.code and not args.docs and not args.files:
        args.docs = True

    sys.exit(run_resolve(args))


if __name__ == "__main__":
    main()
