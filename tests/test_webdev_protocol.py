#!/usr/bin/env python3
"""tests.test_webdev_protocol - Tests for Along WebDev protocol integration and wrap verification gate (REQ-14)."""

import os
import shutil
import tempfile
import unittest

from alongkit import lifecycle, verify


class TestWebdevProtocolGate(unittest.TestCase):
    """Protocol verification policy and wrap refusal gate tests (REQ-14)."""

    def setUp(self):
        self.temp_repo = tempfile.mkdtemp()
        self.sdir = os.path.join(self.temp_repo, ".along")
        self.issues_dir = os.path.join(self.sdir, "ISSUES")
        os.makedirs(self.issues_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_repo, ignore_errors=True)

    def test_verify_checks_allows_webdev(self):
        pol = verify.policy_from_block(
            {"tests": "required", "checks": ["webdev"]},
            source="issue",
            issue="test-issue",
        )
        problems = verify.policy_problems(self.temp_repo, pol, issue_type="feat")
        self.assertEqual(problems, [])
        self.assertIn("webdev", pol.checks)

    def test_check_webdev_wrap_blockers_missing_results(self):
        issue_path = os.path.join(self.issues_dir, "feat--ui-feature.md")
        content = (
            "---\nprotocol: along\nslug: ui-feature\ntype: feat\nstatus: in-progress\n---\n\n"
            "# UI Feature\n\n"
            "## Description\nSome description without verification section.\n"
        )
        with open(issue_path, "w", encoding="utf-8") as f:
            f.write(content)

        blockers = lifecycle._check_webdev_wrap_blockers(self.temp_repo, "ui-feature")
        self.assertTrue(len(blockers) > 0)
        self.assertIn("No '## Browser Verification Results' section found", blockers[0])

    def test_check_webdev_wrap_blockers_failing_check(self):
        issue_path = os.path.join(self.issues_dir, "feat--ui-feature.md")
        content = (
            "---\nprotocol: along\nslug: ui-feature\ntype: feat\nstatus: in-progress\n---\n\n"
            "# UI Feature\n\n"
            "## Browser Verification Results\n\n"
            "| Check | AC | Viewport | Theme | Status | Reason | Evidence |\n"
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
            "| C1 | AC-1 | mobile-375x812 | light | **FAIL** | timeout waiting for button | shot.png |\n"
        )
        with open(issue_path, "w", encoding="utf-8") as f:
            f.write(content)

        blockers = lifecycle._check_webdev_wrap_blockers(self.temp_repo, "ui-feature")
        self.assertTrue(len(blockers) > 0)
        self.assertIn("failed: timeout waiting for button", blockers[0])

    def test_check_webdev_wrap_blockers_unreasoned_not_run(self):
        issue_path = os.path.join(self.issues_dir, "feat--ui-feature.md")
        content = (
            "---\nprotocol: along\nslug: ui-feature\ntype: feat\nstatus: in-progress\n---\n\n"
            "# UI Feature\n\n"
            "## Browser Verification Results\n\n"
            "| Check | AC | Viewport | Theme | Status | Reason | Evidence |\n"
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
            "| C1 | AC-1 | mobile-375x812 | light | NOT RUN | not-compiled | - |\n"
        )
        with open(issue_path, "w", encoding="utf-8") as f:
            f.write(content)

        blockers = lifecycle._check_webdev_wrap_blockers(self.temp_repo, "ui-feature")
        self.assertTrue(len(blockers) > 0)
        self.assertIn("without an approved platform limit substitute", blockers[0])

    def test_check_webdev_wrap_blockers_passes_with_pass_and_platform_limit(self):
        issue_path = os.path.join(self.issues_dir, "feat--ui-feature.md")
        content = (
            "---\nprotocol: along\nslug: ui-feature\ntype: feat\nstatus: in-progress\n---\n\n"
            "# UI Feature\n\n"
            "## Browser Verification Results\n\n"
            "| Check | AC | Viewport | Theme | Status | Reason | Evidence |\n"
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
            "| C1 | AC-1 | mobile-375x812 | light | **PASS** | - | shot.png |\n"
            "| C2 | AC-2 | desktop-1440x900 | dark | NOT RUN | platform-limit:os-media-flyout | - |\n"
        )
        with open(issue_path, "w", encoding="utf-8") as f:
            f.write(content)

        blockers = lifecycle._check_webdev_wrap_blockers(self.temp_repo, "ui-feature")
        self.assertEqual(blockers, [])


if __name__ == "__main__":
    unittest.main()
