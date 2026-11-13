#!/usr/bin/env python3
"""
tests/test_multi_subproject_find.py - Unit tests for multi-subproject issue discovery,
start navigation hints, and projection plan status alignment.
"""

from __future__ import annotations

import json
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

from alongkit import entities, textio
from alongkit.commands.issue import handle_issue_command
from alongkit.commands.lifecycle import handle_start_command
from alongkit.entities.projections import _PLAN_STATUS_NOTES, compile_issues_board
from alongkit.entities.stubs import lint_issues
from alongkit.entities.validation import validate_entities
from alongkit.exceptions import CommandError


class TestMultiSubprojectFindAndStartHint(unittest.TestCase):
    def setUp(self):
        self.tmp_root = tempfile.mkdtemp(prefix="along-find-test-")
        # Root .along/
        os.makedirs(os.path.join(self.tmp_root, ".along", "ISSUES"), exist_ok=True)
        # Subproject src/core/.along/
        self.sub_core = os.path.join(self.tmp_root, "src", "core")
        os.makedirs(os.path.join(self.sub_core, ".along", "ISSUES"), exist_ok=True)

        # Root issue
        textio.write_text(
            os.path.join(self.tmp_root, ".along", "ISSUES", "feat--root-feature.md"),
            "---\nslug: root-feature\ntype: feat\nstatus: open\nplan_status: approved\n---\n\n"
            "# Root Feature\n\n## Problem\nNone\n\n## Requirements\nNone\n\n## Acceptance Criteria\n- [ ] Task requirement 1\n",
        )

        # Subproject issue
        textio.write_text(
            os.path.join(self.sub_core, ".along", "ISSUES", "bug--timeout-error.md"),
            "---\nslug: timeout-error\ntype: bug\nstatus: open\nplan_status: needs-approval\n---\n\n"
            "# Timeout Error\n\n## Problem\nTimeout in test\n\n## Requirements\nFix timeout\n\n## Acceptance Criteria\n- [ ] Task requirement 1\n",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_find_discovers_root_and_subproject_issues(self):
        # Find root issue
        rc_root = handle_issue_command(self.tmp_root, ["find", "root-feature"])
        self.assertEqual(rc_root, 0)

        # Find subproject issue by slug
        rc_sub = handle_issue_command(self.tmp_root, ["find", "timeout-error"])
        self.assertEqual(rc_sub, 0)

        # Find subproject issue by canonical key
        rc_key = handle_issue_command(self.tmp_root, ["find", "bug--timeout-error"])
        self.assertEqual(rc_key, 0)

        # Nonexistent issue
        rc_none = handle_issue_command(self.tmp_root, ["find", "unknown-slug"])
        self.assertEqual(rc_none, 1)

    def test_start_hints_nested_subproject_navigation(self):
        with self.assertRaises(CommandError) as cm:
            handle_start_command(self.tmp_root, ["timeout-error"])
        err = str(cm.exception)
        self.assertIn("was not found in the current context", err)
        self.assertIn("belongs to subproject 'src/core'", err)
        self.assertIn("(cd src/core && along start timeout-error)", err)


class TestPlanStatusWordingAndLint(unittest.TestCase):
    def setUp(self):
        self.tmp_root = tempfile.mkdtemp(prefix="along-plan-test-")
        os.makedirs(os.path.join(self.tmp_root, ".along", "ISSUES"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_plan_status_notes_wording(self):
        self.assertEqual(_PLAN_STATUS_NOTES.get("approved"), " - plan approved")
        self.assertEqual(_PLAN_STATUS_NOTES.get("needs-approval"), " - plan: needs approval")

    def test_board_compiles_plan_approved(self):
        textio.write_text(
            os.path.join(self.tmp_root, ".along", "ISSUES", "feat--approved-feat.md"),
            "---\nslug: approved-feat\ntype: feat\nstatus: open\nplan_status: approved\n---\n\n# Approved\n",
        )
        board = compile_issues_board(self.tmp_root)
        self.assertIn("[approved-feat](ISSUES/feat--approved-feat.md) - plan approved", board)

    def test_lint_catches_stale_plan_body_header(self):
        iss_path = os.path.join(self.tmp_root, ".along", "ISSUES", "feat--stale-plan.md")
        textio.write_text(
            iss_path,
            "---\nslug: stale-plan\ntype: feat\nstatus: open\nplan_status: approved\n---\n\n"
            "# Stale Plan\n\n## Problem\nNone\n\n## Requirements\nNone\n\n## Acceptance Criteria\n- [ ] Task requirement 1\n",
        )
        plan_dir = os.path.join(self.tmp_root, ".along", "ISSUES", "feat--stale-plan")
        os.makedirs(plan_dir, exist_ok=True)
        textio.write_text(
            os.path.join(plan_dir, "plan.md"),
            "# Living Plan: stale-plan\n\nStatus: proposed (needs user approval)\n\n## Steps\n- [ ] Step 1: do it\n",
        )
        report = lint_issues(self.tmp_root)
        self.assertFalse(report["clean"])
        findings = [f for f in report["findings"] if f["slug"] == "stale-plan"]
        self.assertTrue(len(findings) > 0)
        self.assertTrue(any("stale status header" in m for m in findings[0]["missing"]))


if __name__ == "__main__":
    unittest.main()
