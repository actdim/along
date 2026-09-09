#!/usr/bin/env python3
"""
alongkit.patcher - Deterministic AST-based Python code patching.

Replaces functions and class methods safely using Python ast line mapping:
- Locates target function or method definition by name
- Locates replacement function in replacement source
- Preserves surrounding comments, docstrings, imports, and indentation
- Validates resulting code syntax and compilation before writing to disk
- Rejects invalid replacements without modifying disk files
"""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: python .along/scripts/test.py"
    )

import ast
import os
from typing import List, Optional, Tuple, Union

from . import textio


class PatcherError(RuntimeError):
    """Raised when AST code patching fails."""


def _get_node_span(node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> Tuple[int, int]:
    """Get 1-indexed (start_line, end_line) including any decorators."""
    start = node.lineno
    if hasattr(node, "decorator_list") and node.decorator_list:
        start = min([start] + [d.lineno for d in node.decorator_list])
    end = getattr(node, "end_lineno", node.lineno)
    return start, end


def _find_target_function(tree: ast.AST, function_name: str) -> Optional[Tuple[Union[ast.FunctionDef, ast.AsyncFunctionDef], int]]:
    """Locate target FunctionDef or AsyncFunctionDef by name or ClassName.method_name.

    Returns (node, col_offset) or None.
    """
    if "." in function_name:
        parts = function_name.split(".", 1)
        class_name, method_name = parts[0], parts[1]
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for sub in ast.iter_child_nodes(node):
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name == method_name:
                        return sub, sub.col_offset
        return None

    # Top-level functions
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return node, node.col_offset

    # Methods inside classes
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            for sub in ast.iter_child_nodes(node):
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name == function_name:
                    return sub, sub.col_offset

    return None


def _find_replacement_function(tree: ast.AST, target_name: str) -> Optional[Tuple[Union[ast.FunctionDef, ast.AsyncFunctionDef], int]]:
    """Locate replacement function in AST.

    Prefers exact name match; falls back to single top-level function.
    """
    base_name = target_name.split(".")[-1]
    res = _find_target_function(tree, base_name)
    if res:
        return res

    top_funcs = [
        n for n in ast.iter_child_nodes(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if len(top_funcs) == 1:
        return top_funcs[0], top_funcs[0].col_offset

    return None


def replace_function(target_source: str, function_name: str, replacement_source: str,
                     target_filename: str = "<target>",
                     replacement_filename: str = "<replacement>") -> str:
    """Replace a function or method in target_source with replacement_source using AST mapping.

    Returns the new source string. Raises PatcherError on syntax or resolution errors.
    """
    try:
        target_tree = ast.parse(target_source, filename=target_filename)
    except (SyntaxError, IndentationError) as exc:
        raise PatcherError(f"Cannot parse target '{target_filename}': {exc}") from exc

    try:
        repl_tree = ast.parse(replacement_source, filename=replacement_filename)
    except (SyntaxError, IndentationError) as exc:
        raise PatcherError(f"Cannot parse replacement '{replacement_filename}': {exc}") from exc

    target_res = _find_target_function(target_tree, function_name)
    if not target_res:
        raise PatcherError(f"Target function '{function_name}' not found in '{target_filename}'")
    target_node, target_col = target_res

    repl_res = _find_replacement_function(repl_tree, function_name)
    if not repl_res:
        raise PatcherError(f"Replacement function for '{function_name}' not found in '{replacement_filename}'")
    repl_node, repl_col = repl_res

    target_start, target_end = _get_node_span(target_node)
    repl_start, repl_end = _get_node_span(repl_node)

    target_lines = target_source.splitlines()
    repl_lines = replacement_source.splitlines()

    # Extract replacement slice
    repl_slice = repl_lines[repl_start - 1:repl_end]

    # Adjust indentation to match target
    indent_diff = target_col - repl_col
    adjusted_repl: List[str] = []
    for line in repl_slice:
        if not line.strip():
            adjusted_repl.append("")
        elif indent_diff > 0:
            adjusted_repl.append((" " * indent_diff) + line)
        elif indent_diff < 0:
            remove_spaces = min(abs(indent_diff), len(line) - len(line.lstrip(" ")))
            adjusted_repl.append(line[remove_spaces:])
        else:
            adjusted_repl.append(line)

    # Splice target lines
    new_lines = target_lines[:target_start - 1] + adjusted_repl + target_lines[target_end:]

    # Detect newline
    nl = "\r\n" if "\r\n" in target_source else "\n"
    new_source = nl.join(new_lines)
    if target_source.endswith(("\r\n", "\n")):
        new_source += nl

    # Pre-write verification: parse and compile
    try:
        ast.parse(new_source, filename=target_filename)
        compile(new_source, target_filename, "exec")
    except (SyntaxError, IndentationError) as exc:
        raise PatcherError(f"Patched code failed syntax compilation: {exc}") from exc

    return new_source


def replace_function_in_file(target_file: str, function_name: str, replacement_file: str) -> bool:
    """Safely replace function in target_file using AST validation.

    Writes to disk only after successful compilation. Returns True on success.
    """
    if not os.path.isfile(target_file):
        raise PatcherError(f"Target file not found: '{target_file}'")
    if not os.path.isfile(replacement_file):
        raise PatcherError(f"Replacement file not found: '{replacement_file}'")

    try:
        target_source = textio.read_text(target_file, strict=True)
    except (OSError, UnicodeDecodeError) as exc:
        raise PatcherError(f"Cannot read target file '{target_file}': {exc}") from exc

    try:
        replacement_source = textio.read_text(replacement_file, strict=True)
    except (OSError, UnicodeDecodeError) as exc:
        raise PatcherError(f"Cannot read replacement file '{replacement_file}': {exc}") from exc

    nl = textio.detect_newline(target_source)
    new_source = replace_function(
        target_source, function_name, replacement_source,
        target_filename=target_file,
        replacement_filename=replacement_file,
    )

    textio.write_text(target_file, new_source, newline=nl)
    return True
