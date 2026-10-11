#!/usr/bin/env python3
"""
alongkit.resolve_code - Source code conflict auto-resolution and test-gated verification.

Provides AST-aware and structural reconciliation for source code conflicts:
- Imports set-union deduplication (Python, TypeScript, JavaScript).
- Non-overlapping function and class additions (Python AST).
- Collision detection (preserves conflict markers when symbols overlap).
- Quality Gate Verification Pipeline (syntax validation, typography check, test runner).
- Transactional rollback via FileTransaction to preserve exact Git conflict state on failure.
"""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along resolve --code   (or: python scripts/along_resolve.py --code)"
    )

import ast
import os
import re
import sys
from typing import Dict, List, Optional, Set, Tuple, Union

from . import closeout, gates, markdown, merge, proc, repo, textio, transaction, typography
from .resolve import ConflictHunk, parse_conflict_hunks

CODE_EXTENSIONS = frozenset({
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".rs", ".cs", ".go", ".c", ".cpp", ".h", ".hpp",
    ".java", ".kt", ".rb", ".php",
})

_PY_IMPORT_RE = re.compile(r"^\s*(?:import\s+[\w\.\,\s]+|from\s+[\w\.]+\s+import\s+[\w\.\,\*\s\(\)]+)")
_JS_IMPORT_RE = re.compile(r"^\s*import\s+(?:.*from\s+['\"][^'\"]+['\"]|['\"][^'\"]+['\"])")


def is_source_code_file(path: str) -> bool:
    """Return True if the file has a recognized source code extension."""
    _, ext = os.path.splitext(path.lower())
    return ext in CODE_EXTENSIONS


def get_unmerged_code_files(repo_root: str) -> List[str]:
    """Find unmerged source code files across the repository."""
    changes = closeout.git_changes(repo_root)
    unmerged: List[str] = []
    for path, code in changes.items():
        if code in closeout._UNMERGED_CODES:
            norm_path = path.replace("\\", "/")
            if is_source_code_file(norm_path):
                unmerged.append(norm_path)
    return sorted(unmerged)


def reconcile_python_imports(ours: List[str], theirs: List[str]) -> Optional[List[str]]:
    """Reconcile Python import statements via set-union deduplication and sorting."""
    ours_clean = [l.strip() for l in ours if l.strip()]
    theirs_clean = [l.strip() for l in theirs if l.strip()]

    if not ours_clean and not theirs_clean:
        return []

    # Verify that all non-empty lines are import statements
    if not all(_PY_IMPORT_RE.match(l) for l in ours_clean):
        return None
    if not all(_PY_IMPORT_RE.match(l) for l in theirs_clean):
        return None

    # Verify each side parses validly as imports
    try:
        ast.parse("".join(ours))
        ast.parse("".join(theirs))
    except (SyntaxError, ValueError):
        return None

    seen: Set[str] = set()
    result: List[str] = []

    # Preserve order: ours first, then new theirs imports
    for line in ours:
        raw = line.rstrip("\r\n")
        if raw.strip() and raw.strip() not in seen:
            seen.add(raw.strip())
            result.append(raw + "\n")

    for line in theirs:
        raw = line.rstrip("\r\n")
        if raw.strip() and raw.strip() not in seen:
            seen.add(raw.strip())
            result.append(raw + "\n")

    # Verify combined result parses as valid Python
    try:
        ast.parse("".join(result))
    except (SyntaxError, ValueError):
        return None

    return result


def reconcile_js_imports(ours: List[str], theirs: List[str]) -> Optional[List[str]]:
    """Reconcile JS/TS import statements via set-union deduplication."""
    ours_clean = [l.strip() for l in ours if l.strip()]
    theirs_clean = [l.strip() for l in theirs if l.strip()]

    if not ours_clean and not theirs_clean:
        return []

    if not all(_JS_IMPORT_RE.match(l) for l in ours_clean):
        return None
    if not all(_JS_IMPORT_RE.match(l) for l in theirs_clean):
        return None

    seen: Set[str] = set()
    result: List[str] = []

    for line in ours:
        raw = line.rstrip("\r\n")
        if raw.strip() and raw.strip() not in seen:
            seen.add(raw.strip())
            result.append(raw + "\n")

    for line in theirs:
        raw = line.rstrip("\r\n")
        if raw.strip() and raw.strip() not in seen:
            seen.add(raw.strip())
            result.append(raw + "\n")

    return result


def _extract_top_level_definitions(tree: ast.AST) -> Optional[Dict[str, ast.AST]]:
    """Extract top-level function, class, and assignment symbol names from an AST.

    Returns a dict mapping symbol name to node, or None if the AST contains
    non-definition statements (e.g. top-level control flow, returns).
    """
    definitions: Dict[str, ast.AST] = {}
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    definitions[target.id] = node
                else:
                    return None
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                definitions[node.target.id] = node
            else:
                return None
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            # Handled separately by import reconciler
            pass
        else:
            return None
    return definitions


def reconcile_python_definitions(ours: List[str], theirs: List[str]) -> Optional[List[str]]:
    """Reconcile non-overlapping Python function and class definitions.

    If both sides introduce or modify distinct symbols, concatenates them sequentially
    with PEP 8 compliant spacing. If symbol names collide, returns None to retain
    conflict markers for human review.
    """
    text_ours = "".join(ours)
    text_theirs = "".join(theirs)

    try:
        tree_ours = ast.parse(text_ours)
        tree_theirs = ast.parse(text_theirs)
    except (SyntaxError, ValueError):
        return None

    defs_ours = _extract_top_level_definitions(tree_ours)
    defs_theirs = _extract_top_level_definitions(tree_theirs)

    if defs_ours is None or defs_theirs is None:
        return None

    symbols_ours = set(defs_ours.keys())
    symbols_theirs = set(defs_theirs.keys())

    # Must contain at least one definition on each side
    if not symbols_ours or not symbols_theirs:
        return None

    # Collision guard: if any symbol exists on both sides, do not guess
    if not symbols_ours.isdisjoint(symbols_theirs):
        return None

    # Disjoint definitions: combine sequentially
    clean_ours = text_ours.rstrip()
    clean_theirs = text_theirs.strip()
    merged_text = clean_ours + "\n\n\n" + clean_theirs + "\n"

    # Verify combined syntax compiles cleanly
    try:
        compile(merged_text, "<merged>", "exec")
    except (SyntaxError, ValueError):
        return None

    return [line + "\n" for line in merged_text.splitlines()]


def reconcile_code_hunk(hunk: ConflictHunk, file_path: str = "") -> Tuple[str, bool, str]:
    """Reconcile a single source code conflict hunk.

    Returns (replacement_text, is_clean, resolution_method).
    """
    # Exact match on both sides
    if hunk.ours == hunk.theirs:
        return "".join(hunk.ours), True, "identical"

    # One side empty and matches base
    if hunk.base is not None:
        if hunk.ours == hunk.base and hunk.theirs != hunk.base:
            return "".join(hunk.theirs), True, "theirs_addition"
        if hunk.theirs == hunk.base and hunk.ours != hunk.base:
            return "".join(hunk.ours), True, "ours_addition"

    _, ext = os.path.splitext(file_path.lower()) if file_path else ("", "")

    # Python language-aware reconciliation
    if ext == ".py":
        imp = reconcile_python_imports(hunk.ours, hunk.theirs)
        if imp is not None:
            return "".join(imp), True, "python_imports_union"

        defs = reconcile_python_definitions(hunk.ours, hunk.theirs)
        if defs is not None:
            return "".join(defs), True, "python_definitions_sequential"

    # JS/TS imports reconciliation
    elif ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
        imp = reconcile_js_imports(hunk.ours, hunk.theirs)
        if imp is not None:
            return "".join(imp), True, "js_imports_union"

    # Attempt 3-way text merge if base is available
    if hunk.base is not None:
        merged, clean = merge.text_merge("".join(hunk.base), "".join(hunk.ours), "".join(hunk.theirs))
        if clean:
            return merged, True, "text_3way"

    # Unresolved: preserve standard conflict markers for human or agent review
    unresolved: List[str] = [f"<<<<<<< {hunk.ours_label or 'ours'}\n"]
    unresolved.extend(hunk.ours)
    if hunk.base is not None:
        unresolved.append(f"||||||| {hunk.base_label or 'base'}\n")
        unresolved.extend(hunk.base)
    unresolved.append("=======\n")
    unresolved.extend(hunk.theirs)
    unresolved.append(f">>>>>>> {hunk.theirs_label or 'theirs'}\n")

    return "".join(unresolved), False, "unresolved"


def resolve_code_content(text: str, file_path: str = "",
                         repo_root: str = "",
                         strict: bool = False) -> Tuple[str, bool, List[str]]:
    """Parse, reconcile, and validate a source code file containing conflict markers.

    Returns (merged_text, clean, warnings).
    """
    warnings: List[str] = []
    chunks, valid_syntax = parse_conflict_hunks(text, is_markdown=False)

    if not valid_syntax:
        warnings.append("Malformed or unclosed conflict markers in content")
        return text, False, warnings

    reconciled_parts: List[str] = []
    all_clean = True

    for chunk in chunks:
        if isinstance(chunk, str):
            reconciled_parts.append(chunk)
        elif isinstance(chunk, ConflictHunk):
            resolved, clean, method = reconcile_code_hunk(chunk, file_path=file_path)
            reconciled_parts.append(resolved)
            if not clean:
                all_clean = False
                warnings.append(
                    f"Line {chunk.start_line}-{chunk.end_line}: unresolvable code collision ({method})"
                )
            else:
                warnings.append(
                    f"Line {chunk.start_line}-{chunk.end_line}: resolved via {method}"
                )

    merged_text = "".join(reconciled_parts)

    # Clean typography check
    sanitized, changed = typography.clean(merged_text)
    if changed:
        merged_text = sanitized
        warnings.append("Sanitized non-ASCII typographic characters")

    return merged_text, all_clean, warnings


def verify_code_gates(repo_root: str, target_files: List[str],
                      run_tests: bool = True,
                      test_cmd: Optional[List[str]] = None) -> Tuple[bool, List[str]]:
    """Execute quality gate verification pipeline across modified source files.

    Order:
    1. Syntax check (compile on Python files).
    2. Typography check (zero forbidden non-ASCII typography).
    3. Project test execution (along test or custom command).

    Returns (passed, diagnostic_messages).
    """
    diagnostics: List[str] = []

    # Gate 1: Syntax Validation
    for path in target_files:
        abs_path = path if os.path.isabs(path) else os.path.join(repo_root, path)
        if not os.path.isfile(abs_path):
            continue
        rel = repo.safe_relpath(abs_path, repo_root).replace("\\", "/")
        _, ext = os.path.splitext(abs_path.lower())

        if ext == ".py":
            try:
                content = textio.read_text(abs_path)
                compile(content, rel, "exec")
            except (SyntaxError, ValueError) as exc:
                diagnostics.append(f"Syntax validation failed in {rel}: {exc}")
                return False, diagnostics

    # Gate 2: Typography Validation
    for path in target_files:
        abs_path = path if os.path.isabs(path) else os.path.join(repo_root, path)
        if not os.path.isfile(abs_path):
            continue
        rel = repo.safe_relpath(abs_path, repo_root).replace("\\", "/")
        content = textio.read_text(abs_path)
        violations = typography.findings(content)
        if violations:
            diagnostics.append(
                f"Typography violations detected in {rel}: {len(violations)} non-ASCII glyph(s)"
            )
            return False, diagnostics

    # Gate 3: Test Suite Execution
    if run_tests:
        print("-> Running Test-Gated Quality Verification...")
        if test_cmd:
            cmd = test_cmd
        else:
            test_script = repo.resolve_tool_script("test.py", repo_root)
            if not test_script:
                test_script = os.path.join(repo_root, ".along", "scripts", "test.py")
            if os.path.isfile(test_script):
                cmd = [sys.executable, test_script, "-q"]
            else:
                cmd = [sys.executable, "-m", "unittest"]

        res = proc.run_capture(cmd, cwd=repo_root)
        if not res.ok:
            err_msg = res.stderr.strip() or res.stdout.strip()
            diagnostics.append(f"Test suite verification failed (code {res.returncode}):\n{err_msg}")
            return False, diagnostics

    return True, diagnostics


def resolve_and_verify_code(repo_root: str,
                            target_files: Optional[List[str]] = None,
                            dry_run: bool = False,
                            strict: bool = False,
                            run_tests: bool = True,
                            test_cmd: Optional[List[str]] = None) -> Tuple[bool, List[str]]:
    """Execute transactional test-gated code conflict resolution pipeline.

    Wraps the entire resolution in FileTransaction:
    - Snapshots all conflicted files before modifications.
    - Tentatively writes reconciled code to disk.
    - Runs Quality Gate Verification Pipeline (syntax, typography, tests).
    - If any gate fails: rolls back to exact Git conflict markers.
    - If all pass: stages resolved files and commits transaction.

    Returns (success, notes).
    """
    notes: List[str] = []

    if not target_files:
        target_files = [os.path.join(repo_root, u) for u in get_unmerged_code_files(repo_root)]

    if not target_files:
        return True, ["No conflicted source code files detected."]

    tx = transaction.FileTransaction(repo_root, label="resolve-code")
    resolved_paths: List[str] = []
    has_unresolvable_collisions = False

    try:
        # Snapshot files in transaction
        for target in target_files:
            abs_path = target if os.path.isabs(target) else os.path.join(repo_root, target)
            rel = repo.safe_relpath(abs_path, repo_root).replace("\\", "/")
            if not os.path.isfile(abs_path):
                continue

            content = textio.read_text(abs_path)
            tx.protect(abs_path)

            merged, clean, warnings = resolve_code_content(
                content, file_path=abs_path, repo_root=repo_root, strict=strict
            )

            for w in warnings:
                notes.append(f"{rel}: {w}")

            if not clean:
                has_unresolvable_collisions = True

            if not dry_run and merged != content:
                textio.write_text(abs_path, merged)
                resolved_paths.append(abs_path)

        if dry_run:
            tx.rollback()
            return not has_unresolvable_collisions, notes

        if has_unresolvable_collisions:
            notes.append("Aborting test execution: unresolvable collisions present in conflict hunks.")
            tx.rollback()
            return False, notes

        # Execute Quality Gate Verification Pipeline
        gates_passed, gate_diagnostics = verify_code_gates(
            repo_root, resolved_paths, run_tests=run_tests, test_cmd=test_cmd
        )

        if not gates_passed:
            notes.extend(gate_diagnostics)
            notes.append("Quality gates failed: rolling back to original Git conflict state.")
            tx.rollback()
            return False, notes

        # Stage cleanly resolved files
        if resolved_paths:
            rel_resolved = [repo.safe_relpath(p, repo_root).replace("\\", "/") for p in resolved_paths]
            proc.git(["add", *rel_resolved], cwd=repo_root)
            notes.append(f"Successfully staged {len(resolved_paths)} resolved file(s).")

        tx.commit()
        return True, notes

    except (OSError, RuntimeError, ValueError, TypeError, AttributeError, SyntaxError) as exc:
        tx.rollback()
        notes.append(f"Unexpected error during resolution: {exc}")
        return False, notes
