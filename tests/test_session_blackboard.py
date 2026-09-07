#!/usr/bin/env python3
"""
tests/test_session_blackboard.py - Tests for alongkit.session and along scratch CLI.
"""

from __future__ import annotations

import json
import os
import sys
import unittest

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

import shutil
import hermetic
from alongkit import proc, session


class TestSessionBlackboard(unittest.TestCase):

    def setUp(self):
        self.repo = hermetic.make_repo_fixture(prefix="along-session-test-")

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_init_session_creates_directory_and_state(self):
        slug = "sample-task"
        st = session.init_session(self.repo, slug, title="Sample Task", total_steps=4)
        self.assertEqual(st["slug"], slug)
        self.assertEqual(st["title"], "Sample Task")
        self.assertEqual(st["status"], "in-progress")
        self.assertEqual(st["current_step"], 1)
        self.assertEqual(st["plan_revision"], 1)
        self.assertEqual(st["retry_limit"], 2)
        self.assertEqual(len(st["steps"]), 4)
        self.assertEqual(st["steps"][0]["status"], "pending")
        self.assertEqual(st["steps"][1]["status"], "pending")

        sdir = session.get_session_dir(self.repo, slug)
        self.assertTrue(os.path.isdir(sdir))
        self.assertTrue(os.path.isfile(os.path.join(sdir, "state.json")))
        self.assertTrue(os.path.isfile(os.path.join(sdir, "plan.md")))

    def test_init_session_is_idempotent_unless_force_restart(self):
        slug = "idempotent-task"
        st1 = session.init_session(self.repo, slug, title="First Title", total_steps=3)
        session.update_state(self.repo, slug, current_step=2, step_status="passed")

        # Second init without restart preserves existing state
        st2 = session.init_session(self.repo, slug, title="Second Title", total_steps=5)
        self.assertEqual(st2["current_step"], 2)
        self.assertEqual(len(st2["steps"]), 3)
        self.assertEqual(st2["plan_revision"], 1)

        # Force restart resets steps and bumps plan_revision
        st3 = session.init_session(self.repo, slug, title="Restarted Title", total_steps=5, force_restart=True)
        self.assertEqual(st3["current_step"], 1)
        self.assertEqual(len(st3["steps"]), 5)
        self.assertEqual(st3["plan_revision"], 2)

    def test_update_state_and_retry_budget_enforcement(self):
        slug = "retry-task"
        session.init_session(self.repo, slug, title="Retry Task", total_steps=3)

        # Retry 1
        st, exhausted = session.update_state(self.repo, slug, increment_retry=True)
        self.assertFalse(exhausted)
        self.assertEqual(st["steps"][0]["retries"], 1)

        # Retry 2 (at budget)
        st, exhausted = session.update_state(self.repo, slug, increment_retry=True)
        self.assertFalse(exhausted)
        self.assertEqual(st["steps"][0]["retries"], 2)

        # Retry 3 (exceeds budget of 2)
        st, exhausted = session.update_state(self.repo, slug, increment_retry=True)
        self.assertTrue(exhausted)
        self.assertEqual(st["steps"][0]["retries"], 3)
        self.assertEqual(st["steps"][0]["status"], "failed")

    def test_purge_session(self):
        slug = "purge-task"
        session.init_session(self.repo, slug)
        sdir = session.get_session_dir(self.repo, slug)
        self.assertTrue(os.path.exists(sdir))

        purged = session.purge_session(self.repo, slug)
        self.assertTrue(purged)
        self.assertFalse(os.path.exists(sdir))

        # Purging already clean session returns False
        purged_again = session.purge_session(self.repo, slug)
        self.assertFalse(purged_again)

    def test_scratch_cli_lifecycle(self):
        slug = "cli-blackboard-test"
        script_path = os.path.join(hermetic.REPO_ROOT, "scripts", "along_exec.py")

        # 1. scratch init
        res = proc.run_capture([
            sys.executable, script_path, "scratch", "init", slug,
            "--title", "CLI Task", "--steps", "3"
        ], cwd=self.repo)
        self.assertEqual(res.returncode, 0, f"init failed: {res.stderr}")
        self.assertIn("Initialized session blackboard", res.stdout)

        # 2. scratch state --json
        res = proc.run_capture([
            sys.executable, script_path, "scratch", "state", slug, "--json"
        ], cwd=self.repo)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["slug"], slug)
        self.assertEqual(data["current_step"], 1)
        self.assertEqual(len(data["steps"]), 3)

        # 3. scratch update step 1 passed
        res = proc.run_capture([
            sys.executable, script_path, "scratch", "update", slug,
            "--step", "1", "--step-status", "passed"
        ], cwd=self.repo)
        self.assertEqual(res.returncode, 0)
        self.assertIn("[1] Step 1 (passed", res.stdout)

        # 4. scratch update step 2 with retries exceeding limit
        proc.run_capture([
            sys.executable, script_path, "scratch", "update", slug,
            "--step", "2", "--step-status", "in-progress"
        ], cwd=self.repo)
        proc.run_capture([
            sys.executable, script_path, "scratch", "update", slug, "--inc-retry"
        ], cwd=self.repo)
        proc.run_capture([
            sys.executable, script_path, "scratch", "update", slug, "--inc-retry"
        ], cwd=self.repo)
        res_fail = proc.run_capture([
            sys.executable, script_path, "scratch", "update", slug, "--inc-retry"
        ], cwd=self.repo)
        self.assertEqual(res_fail.returncode, 2, "Should exit with code 2 on retry exhaustion")
        self.assertIn("exceeded the retry budget", res_fail.stderr)

        # 5. scratch purge
        res = proc.run_capture([
            sys.executable, script_path, "scratch", "purge", slug
        ], cwd=self.repo)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Purged session blackboard", res.stdout)

