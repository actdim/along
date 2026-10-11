#!/usr/bin/env python3
"""
alongkit.conflict_check - Pre-merge conflict prediction and blast radius analysis.

Scans branch diffs against their common merge-base to predict potential merge conflicts:
- Identifies overlapping modified files between HEAD and target branch.
- Inspects AST symbols (Python classes, functions, top-level definitions) for collisions.
- Evaluates advisory risk levels (LOW, MEDIUM, HIGH) and provides mitigation recommendations.
"""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along conflict-check <branch>   (or: python scripts/along_conflict_check.py <branch>)"
    )

import ast
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from . import proc, repo


@dataclass
class ConflictPredictionReport:
    """Diagnostic report predicting merge conflict risks between two branches."""
    target_branch: str
    merge_base: str = ""
    risk_level: str = "LOW"
    overlapping_files: List[str] = field(default_factory=list)
    head_modified_files: List[str] = field(default_factory=list)
    target_modified_files: List[str] = field(default_factory=list)
    colliding_symbols: Dict[str, List[str]] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    @property
    def has_collisions(self) -> bool:
        return bool(self.colliding_symbols)


def _get_branch_file_content(rev: str, rel_path: str, repo_root: str) -> Optional[str]:
    """Retrieve file content at a given Git revision using git show."""
    res = proc.git(["show", f"{rev}:{rel_path}"], cwd=repo_root)
    if res.ok:
        return res.stdout
    return None


def _extract_ast_symbol_map(source: str) -> Dict[str, str]:
    """Extract symbol name to normalized node representation from Python code.

    Includes functions, classes, and top-level variable assignments.
    """
    symbols: Dict[str, str] = {}
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return symbols

    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # Use unparse or dump to capture structural definition
            try:
                symbols[node.name] = ast.unparse(node).strip()
            except (AttributeError, ValueError, RecursionError):
                symbols[node.name] = ast.dump(node)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    try:
                        symbols[target.id] = ast.unparse(node).strip()
                    except (AttributeError, ValueError, RecursionError):
                        symbols[target.id] = ast.dump(node)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                try:
                    symbols[node.target.id] = ast.unparse(node).strip()
                except (AttributeError, ValueError, RecursionError):
                    symbols[node.target.id] = ast.dump(node)

    return symbols


def predict_conflicts(repo_root: str, target_branch: str) -> ConflictPredictionReport:
    """Predict conflict risk between HEAD and target_branch.

    1. Resolves git merge-base between HEAD and target_branch.
    2. Identifies modified files on both sides against merge-base.
    3. Finds overlapping modified files.
    4. For overlapping Python files, compares AST symbols to detect direct collisions.
    5. Returns ConflictPredictionReport with risk level and recommendations.
    """
    report = ConflictPredictionReport(target_branch=target_branch)

    # Resolve merge-base
    res_base = proc.git(["merge-base", "HEAD", target_branch], cwd=repo_root)
    if not res_base.ok:
        report.risk_level = "UNKNOWN"
        report.notes.append(
            f"Could not resolve common ancestor (merge-base) between HEAD and '{target_branch}'."
        )
        return report

    merge_base = res_base.stdout.strip()
    report.merge_base = merge_base

    # Query changed files on HEAD vs merge-base
    res_head = proc.git(["diff", "--name-only", f"{merge_base}..HEAD"], cwd=repo_root)
    head_files = [l.strip().replace("\\", "/") for l in res_head.stdout.splitlines() if l.strip()]
    report.head_modified_files = head_files

    # Query changed files on target_branch vs merge-base
    res_target = proc.git(["diff", "--name-only", f"{merge_base}..{target_branch}"], cwd=repo_root)
    target_files = [l.strip().replace("\\", "/") for l in res_target.stdout.splitlines() if l.strip()]
    report.target_modified_files = target_files

    # Compute overlapping files
    overlapping = sorted(set(head_files) & set(target_files))
    report.overlapping_files = overlapping

    if not overlapping:
        report.risk_level = "LOW"
        report.notes.append(
            f"No overlapping files between HEAD and '{target_branch}'. Merge should proceed cleanly."
        )
        return report

    # Check overlapping files for AST symbol collisions
    colliding_map: Dict[str, List[str]] = {}

    for path in overlapping:
        _, ext = os.path.splitext(path.lower())
        if ext == ".py":
            base_src = _get_branch_file_content(merge_base, path, repo_root) or ""
            head_src = _get_branch_file_content("HEAD", path, repo_root) or ""
            target_src = _get_branch_file_content(target_branch, path, repo_root) or ""

            syms_base = _extract_ast_symbol_map(base_src)
            syms_head = _extract_ast_symbol_map(head_src)
            syms_target = _extract_ast_symbol_map(target_src)

            # Modified or newly added symbols in HEAD
            changed_head = {
                sym for sym, body in syms_head.items()
                if sym not in syms_base or syms_base.get(sym) != body
            }

            # Modified or newly added symbols in target branch
            changed_target = {
                sym for sym, body in syms_target.items()
                if sym not in syms_base or syms_base.get(sym) != body
            }

            colliding = sorted(changed_head & changed_target)
            if colliding:
                colliding_map[path] = colliding

    report.colliding_symbols = colliding_map

    if colliding_map:
        report.risk_level = "HIGH"
        report.notes.append(
            f"Direct AST symbol collisions detected in {len(colliding_map)} file(s). "
            "Manual review or structured conflict resolution required."
        )
    else:
        report.risk_level = "MEDIUM"
        report.notes.append(
            f"Overlapping files detected ({len(overlapping)}), but AST symbols are disjoint. "
            "Automated resolution via 'along resolve --code' is likely to succeed."
        )

    return report


def format_prediction_report(report: ConflictPredictionReport) -> str:
    """Format prediction report for terminal display."""
    lines: List[str] = [
        "============================================================",
        f"-> Pre-Merge Conflict Prediction: [{report.risk_level}]",
        "============================================================",
        f"Target Branch:      {report.target_branch}",
        f"Merge Base SHA:     {report.merge_base[:12] if report.merge_base else 'None'}",
        f"HEAD Changed Files: {len(report.head_modified_files)}",
        f"Target Changed:     {len(report.target_modified_files)}",
        f"Overlapping Files:  {len(report.overlapping_files)}",
        "------------------------------------------------------------",
    ]

    if report.overlapping_files:
        lines.append("Overlapping Files:")
        for f in report.overlapping_files:
            colliding = report.colliding_symbols.get(f)
            if colliding:
                lines.append(f"  - [COLLISION] {f} (symbols: {', '.join(colliding)})")
            else:
                lines.append(f"  - [DISJOINT]  {f}")
        lines.append("------------------------------------------------------------")

    lines.append("Advisory Notes:")
    for note in report.notes:
        lines.append(f"  - {note}")

    lines.append("============================================================")
    return "\n".join(lines)
