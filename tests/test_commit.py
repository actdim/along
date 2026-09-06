#!/usr/bin/env python3
"""
tests/test_commit.py - Comprehensive tests for along-commit and issue binding.

Covers REQ-1 through REQ-6 of bug--commit-binds-arbitrary-active-issue:
- REQ-1: Explicit --issue / -i flag.
- REQ-2: Deterministic resolution priority (explicit -> branch -> single in-progress -> refuse).
- REQ-3: Read from SSOT entity files (.along/ISSUES/*.md), not derived ISSUES.md.
- REQ-4: No accidental alphabetical binding when multiple in-progress issues exist.
- REQ-5: Shared format_board_entry and parse_board_entry round-trip.
- REQ-6: Zero, one, multiple in-progress issues, and strict mode.
"""

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import along_commit
from alongkit import entities, proc, textio
from tests.hermetic import repo_fixture

SAMPLE_ISSUE_TEMPLATE = """---
protocol: along
protocol_version: "2.2.8"
slug: {slug}
type: {itype}
status: {status}
priority: {priority}
created: 2026-09-01
updated: 2026-09-01
agent: test-suite
tags: [fixture]
---

# {title}

Description for {slug}.
"""


class TestAlongCommitResolution(unittest.TestCase):
    """Hermetic tests for deterministic issue resolution from SSOT."""

    def _write_issue(self, root: str, slug: str, itype: str = "feat",
                     status: str = "open", priority: str = "medium") -> str:
        sdir = os.path.join(root, ".along", "ISSUES")
        os.makedirs(sdir, exist_ok=True)
        fname = f"{itype}--{slug}.md"
        fpath = os.path.join(sdir, fname)
        textio.write_text(
            fpath,
            SAMPLE_ISSUE_TEMPLATE.format(
                slug=slug,
                itype=itype,
                status=status,
                priority=priority,
                title=slug.replace("-", " ").title(),
            )
        )
        return fpath

    def test_01_board_entry_roundtrip(self):
        """REQ-5: format_board_entry and parse_board_entry produce and consume the same format."""
        entry = entities.format_board_entry("feat", "new-feature", done=False)
        self.assertEqual(entry, "- [ ] `(feat)` [new-feature](ISSUES/feat--new-feature.md)")
        parsed = entities.parse_board_entry(entry)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["type"], "feat")
        self.assertEqual(parsed["slug"], "new-feature")
        self.assertFalse(parsed["done"])
        self.assertEqual(parsed["link"], "ISSUES/feat--new-feature.md")

        done_entry = entities.format_board_entry("bug", "fix-leak", done=True)
        self.assertEqual(done_entry, "- [x] `(bug)` [fix-leak](ISSUES/done/bug--fix-leak.md)")
        parsed_done = entities.parse_board_entry(done_entry)
        self.assertIsNotNone(parsed_done)
        self.assertEqual(parsed_done["type"], "bug")
        self.assertEqual(parsed_done["slug"], "fix-leak")
        self.assertTrue(parsed_done["done"])

    def test_02_explicit_issue_valid(self):
        """REQ-1: Explicit --issue / -i binds directly to the named issue."""
        with repo_fixture(prefix="commit-explicit-") as root:
            self._write_issue(root, "first-issue", itype="bug", status="open")
            self._write_issue(root, "second-issue", itype="feat", status="in-progress")

            iss, warnings = entities.resolve_active_issue(root, explicit_slug="first-issue")
            self.assertIsNotNone(iss)
            self.assertEqual(iss["slug"], "first-issue")
            self.assertEqual(iss["type"], "bug")
            self.assertEqual(len(warnings), 0)

            iss_canon, _ = entities.resolve_active_issue(root, explicit_slug="feat--second-issue")
            self.assertIsNotNone(iss_canon)
            self.assertEqual(iss_canon["slug"], "second-issue")

    def test_03_explicit_issue_unknown_rejected(self):
        """REQ-6: Unknown explicit slug is rejected and raises in strict mode."""
        with repo_fixture(prefix="commit-unknown-") as root:
            iss, warnings = entities.resolve_active_issue(root, explicit_slug="nonexistent-slug", strict=False)
            self.assertIsNone(iss)
            self.assertTrue(any("Unknown issue slug" in w for w in warnings))

            with self.assertRaises(ValueError) as ctx:
                entities.resolve_active_issue(root, explicit_slug="nonexistent-slug", strict=True)
            self.assertIn("nonexistent-slug", str(ctx.exception))

    def test_04_single_in_progress_auto_binds(self):
        """REQ-2, REQ-6: Exactly one in-progress issue binds automatically."""
        with repo_fixture(prefix="commit-single-") as root:
            task_path = os.path.join(root, ".along", "ISSUES", "task--fixture-sample-task.md")
            if os.path.exists(task_path):
                os.remove(task_path)

            self._write_issue(root, "aaa-open-task", itype="task", status="open")
            self._write_issue(root, "zzz-in-progress-fix", itype="bug", status="in-progress")

            iss, warnings = entities.resolve_active_issue(root, branch_name="main")
            self.assertIsNotNone(iss)
            self.assertEqual(iss["slug"], "zzz-in-progress-fix")
            self.assertEqual(iss["type"], "bug")

    def test_05_multiple_in_progress_does_not_guess(self):
        """REQ-4, REQ-6: Multiple in-progress issues do NOT pick alphabetically first."""
        with repo_fixture(prefix="commit-multi-") as root:
            task_path = os.path.join(root, ".along", "ISSUES", "task--fixture-sample-task.md")
            if os.path.exists(task_path):
                os.remove(task_path)

            self._write_issue(root, "alpha-task", itype="feat", status="in-progress")
            self._write_issue(root, "beta-task", itype="bug", status="in-progress")

            iss, warnings = entities.resolve_active_issue(root, branch_name="main", strict=False)
            self.assertIsNone(iss)
            self.assertTrue(any("Multiple in-progress issues found" in w for w in warnings))
            self.assertTrue(any("alpha-task" in w and "beta-task" in w for w in warnings))

            with self.assertRaises(ValueError) as ctx:
                entities.resolve_active_issue(root, branch_name="main", strict=True)
            self.assertIn("multiple in-progress issues", str(ctx.exception).lower())

    def test_06_zero_in_progress_does_not_guess(self):
        """REQ-2: Zero in-progress issues do NOT guess from open issues."""
        with repo_fixture(prefix="commit-zero-") as root:
            task_path = os.path.join(root, ".along", "ISSUES", "task--fixture-sample-task.md")
            if os.path.exists(task_path):
                os.remove(task_path)

            self._write_issue(root, "open-task-one", itype="task", status="open")
            self._write_issue(root, "open-task-two", itype="feat", status="open")

            iss, warnings = entities.resolve_active_issue(root, branch_name="main", strict=False)
            self.assertIsNone(iss)
            self.assertTrue(any("No in-progress issue found" in w for w in warnings))

            with self.assertRaises(ValueError):
                entities.resolve_active_issue(root, branch_name="main", strict=True)

    def test_07_branch_name_matches_in_progress(self):
        """REQ-2: Git branch encoding a slug resolves to that issue even with multiple in-progress."""
        with repo_fixture(prefix="commit-branch-") as root:
            task_path = os.path.join(root, ".along", "ISSUES", "task--fixture-sample-task.md")
            if os.path.exists(task_path):
                os.remove(task_path)

            self._write_issue(root, "alpha-feature", itype="feat", status="in-progress")
            self._write_issue(root, "beta-bugfix", itype="bug", status="in-progress")

            iss, warnings = entities.resolve_active_issue(root, branch_name="feat/alpha-feature")
            self.assertIsNotNone(iss)
            self.assertEqual(iss["slug"], "alpha-feature")

            iss_b, warnings_b = entities.resolve_active_issue(root, branch_name="bug--beta-bugfix")
            self.assertIsNotNone(iss_b)
            self.assertEqual(iss_b["slug"], "beta-bugfix")

    def test_08_format_commit_message(self):
        """Format commit message preserves conventional commits or prefixes correctly."""
        iss = {"type": "bug", "slug": "leak-fix"}
        msg = along_commit.format_commit_message("close file handles", iss)
        self.assertEqual(msg, "fix: close file handles (refs #leak-fix)")

        iss_feat = {"type": "feat", "slug": "new-ui"}
        msg_conv = along_commit.format_commit_message("feat(ui): add button", iss_feat)
        self.assertEqual(msg_conv, "feat(ui): add button (refs #new-ui)")

        msg_no_issue = along_commit.format_commit_message("clean up whitespace", None)
        self.assertEqual(msg_no_issue, "clean up whitespace")

        msg_conv_no_issue = along_commit.format_commit_message("docs: update readme", None)
        self.assertEqual(msg_conv_no_issue, "docs: update readme")


if __name__ == "__main__":
    unittest.main()

