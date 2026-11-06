#!/usr/bin/env python3
"""
tests/test_cross_repo_entities.py - Cross-repo and submodule entity references.
[feat--cross-repo-entity-references]
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import entities


def _cre_write_file(root: str, rel: str, text: str) -> str:
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as h:
        h.write(text)
    return path


def _make_issue(slug: str, itype: str = "feat", status: str = "open",
                parent: str = "", children: list = None, related: list = None,
                extra: str = "") -> str:
    lines = [
        "---",
        "protocol: along",
        f"slug: {slug}",
        f"type: {itype}",
        f"status: {status}",
        "priority: medium",
        "created: 2026-10-01",
        "updated: 2026-10-01",
    ]
    if parent:
        lines.append(f"parent: {parent}")
    if children:
        lines.append("children:")
        for c in children:
            lines.append(f"  - {c}")
    if related:
        lines.append("related:")
        for r in related:
            lines.append(f"  - {r}")
    if extra:
        lines.append(extra)
    lines.extend([
        "---",
        f"# {slug}",
        "",
        "## Problem",
        "Problem statement.",
        "",
        "## Acceptance Criteria",
        "- [ ] Task done",
        "",
    ])
    return "\n".join(lines)


class TestCrossRepoEntityReferences(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="along-cross-repo-")
        # Root repo
        _cre_write_file(self.tmp, "AGENTS.md", "# Test Superproject\n")
        _cre_write_file(self.tmp, ".along/ISSUES.md", "# Active Issues\n")
        # Subproject repo
        self.sub = os.path.join(self.tmp, "src", "packages", "ui-core")
        _cre_write_file(self.sub, "AGENTS.md", "# Subproject UI Core\n")
        _cre_write_file(self.sub, ".along/ISSUES.md", "# Active Issues\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ref_key_parser(self):
        self.assertEqual(entities._ref_key("root:feat--super"), ("root", "feat--super"))
        self.assertEqual(entities._ref_key("sub:feat--button"), ("sub", "feat--button"))
        self.assertEqual(
            entities._ref_key("src/packages/ui-core:feat--button"),
            ("src/packages/ui-core", "feat--button"),
        )
        self.assertEqual(
            entities._ref_key("src\\packages\\ui-core:feat--button"),
            ("src/packages/ui-core", "feat--button"),
        )
        self.assertEqual(entities._ref_key("feat--button"), ("", "feat--button"))

    def test_valid_cross_repo_reference_passes_validation(self):
        # Create child in subproject
        _cre_write_file(
            self.sub,
            ".along/ISSUES/feat--button.md",
            _make_issue("button", parent="root:feat--super-epic"),
        )
        # Create umbrella in root referencing subproject child
        _cre_write_file(
            self.tmp,
            ".along/ISSUES/feat--super-epic.md",
            _make_issue("super-epic", children=["src/packages/ui-core:feat--button"]),
        )

        res = entities.validate_entities(self.tmp)
        integrity_errors = [msg for _, msg in res["errors"] if entities.is_integrity_error(msg)]
        self.assertEqual(integrity_errors, [])

    def test_dangling_reference_in_existing_subproject_fails_validation(self):
        # Umbrella references a non-existent child in existing subproject
        _cre_write_file(
            self.tmp,
            ".along/ISSUES/feat--super-epic.md",
            _make_issue("super-epic", children=["src/packages/ui-core:feat--missing"]),
        )

        res = entities.validate_entities(self.tmp)
        integrity_errors = [msg for _, msg in res["errors"] if entities.is_integrity_error(msg)]
        self.assertTrue(any("dangling children reference: 'src/packages/ui-core:feat--missing'" in msg for msg in integrity_errors))

    def test_uninitialized_subproject_yields_warning_not_integrity_error(self):
        # Umbrella references a path that is not checked out / has no .along
        _cre_write_file(
            self.tmp,
            ".along/ISSUES/feat--super-epic.md",
            _make_issue("super-epic", children=["src/uninitialized-sub:feat--child"]),
        )

        res = entities.validate_entities(self.tmp)
        integrity_errors = [msg for _, msg in res["errors"] if entities.is_integrity_error(msg)]
        self.assertEqual(integrity_errors, [])
        self.assertTrue(any("uninitialized or missing subproject" in msg for _, msg in res["warnings"]))

    def test_board_renders_external_children_from_frontmatter(self):
        _cre_write_file(
            self.sub,
            ".along/ISSUES/feat--button.md",
            _make_issue("button"),
        )
        _cre_write_file(
            self.tmp,
            ".along/ISSUES/feat--super-epic.md",
            _make_issue("super-epic", children=["src/packages/ui-core:feat--button"]),
        )

        board = entities.compile_issues_board(self.tmp)
        self.assertIn("ui-core:feat--button", board)
        self.assertIn("src/packages/ui-core/.along/ISSUES/feat--button.md", board)
        self.assertIn("External Children:", board)

    def test_board_renders_external_children_from_child_parent(self):
        # Child explicitly declares parent as root:feat--super-epic
        _cre_write_file(
            self.sub,
            ".along/ISSUES/feat--button.md",
            _make_issue("button", parent="root:feat--super-epic"),
        )
        _cre_write_file(
            self.tmp,
            ".along/ISSUES/feat--super-epic.md",
            _make_issue("super-epic"),
        )

        board = entities.compile_issues_board(self.tmp)
        self.assertIn("ui-core:feat--button", board)
        self.assertIn("External Children:", board)


if __name__ == "__main__":
    unittest.main()
