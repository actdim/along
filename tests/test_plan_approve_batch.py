#!/usr/bin/env python3
"""tests/test_plan_approve_batch.py - Hermetic tests for batch plan approval and status: draft."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest


class TestPlanApproveBatch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="along-test-plan-batch-")
        self.scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
        self.along_exec = os.path.join(self.scripts_dir, "along_exec.py")

        # Initialize minimal .along structure
        self.along_dir = os.path.join(self.tmp, ".along")
        self.issues_dir = os.path.join(self.along_dir, "ISSUES")
        os.makedirs(self.issues_dir, exist_ok=True)
        with open(os.path.join(self.along_dir, "ISSUES.md"), "w", encoding="utf-8") as f:
            f.write("# Issues Board\n")

        # Create two sample tickets
        self._create_ticket("task--alpha", "Alpha Task")
        self._create_ticket("feat--beta", "Beta Feature")

        # Create plans directory
        self.plans_dir = os.path.join(self.tmp, "plans")
        os.makedirs(self.plans_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _create_ticket(self, key: str, title: str):
        path = os.path.join(self.issues_dir, f"{key}.md")
        entity_type, slug = key.split("--", 1)
        content = (
            f"---\n"
            f"protocol: along\n"
            f"protocol_version: '4.6.0'\n"
            f"slug: {slug}\n"
            f"type: {entity_type}\n"
            f"status: open\n"
            f"priority: medium\n"
            f"created: 2026-11-06\n"
            f"updated: 2026-11-06\n"
            f"agent: antigravity\n"
            f"tags: []\n"
            f"blocked_by: []\n"
            f"related: []\n"
            f"---\n\n"
            f"# {title}\n\n"
            f"## Requirements\n- REQ-1: Do work.\n\n"
            f"## Acceptance Criteria\n- [ ] Done.\n"
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _run(self, *args):
        cmd = [sys.executable, self.along_exec, *args]
        return subprocess.run(cmd, cwd=self.tmp, capture_output=True, text=True)

    def test_single_plan_approve_refuses_draft(self):
        draft_file = os.path.join(self.plans_dir, "alpha_draft.md")
        with open(draft_file, "w", encoding="utf-8") as f:
            f.write("---\nstatus: draft\n---\n# Living Plan: Alpha\nDraft details.\n")

        res = self._run("plan", "approve", "alpha", "--plan-file", draft_file)
        self.assertEqual(res.returncode, 2)
        self.assertIn("status: draft", res.stderr)

    def test_batch_plan_approve_dry_run(self):
        # 1. Valid plan
        with open(os.path.join(self.plans_dir, "01--task--alpha.md"), "w", encoding="utf-8") as f:
            f.write("# Living Plan: Alpha\nReady content.\n")

        # 2. Draft plan
        with open(os.path.join(self.plans_dir, "02--feat--beta.md"), "w", encoding="utf-8") as f:
            f.write("---\nstatus: draft\n---\n# Living Plan: Beta\nStill drafting.\n")

        res = self._run("plan", "approve", "--from", self.plans_dir, "--dry-run")
        self.assertEqual(res.returncode, 0, f"stdout: {res.stdout}, stderr: {res.stderr}")
        self.assertIn("01--task--alpha.md -> alpha [READY]", res.stdout)
        self.assertIn("02--feat--beta.md -> beta [REFUSED: Plan is marked with status: draft]", res.stdout)

    def test_batch_plan_approve_success(self):
        # Write two valid plans
        with open(os.path.join(self.plans_dir, "01--task--alpha.md"), "w", encoding="utf-8") as f:
            f.write("---\nissue: task--alpha\n---\n# Living Plan: Alpha\nApproved content.\n")
        with open(os.path.join(self.plans_dir, "02--feat--beta.md"), "w", encoding="utf-8") as f:
            f.write("---\nissue: feat--beta\n---\n# Living Plan: Beta\nApproved content.\n")

        res = self._run("plan", "approve", "--from", self.plans_dir)
        self.assertEqual(res.returncode, 0, f"stderr: {res.stderr}")
        self.assertIn("Successfully batch-approved plans for 2 issue(s)", res.stdout)

        # Check that plan files were written
        alpha_plan = os.path.join(self.issues_dir, "task--alpha", "plan.md")
        beta_plan = os.path.join(self.issues_dir, "feat--beta", "plan.md")
        self.assertTrue(os.path.isfile(alpha_plan))
        self.assertTrue(os.path.isfile(beta_plan))

        # Check frontmatter plan_status: approved
        with open(os.path.join(self.issues_dir, "task--alpha.md"), "r", encoding="utf-8") as f:
            self.assertIn("plan_status: approved", f.read())


if __name__ == "__main__":
    unittest.main()
