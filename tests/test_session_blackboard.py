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

        # 5. scratch purge: refused while role-based steps are open
        # [feat--along-team-step-enforcement], then forced with a reason
        res = proc.run_capture([
            sys.executable, script_path, "scratch", "purge", slug
        ], cwd=self.repo)
        self.assertEqual(res.returncode, 2)
        self.assertIn("Refusing to purge", res.stderr)
        res = proc.run_capture([
            sys.executable, script_path, "scratch", "purge", slug, "--force"
        ], cwd=self.repo)
        self.assertEqual(res.returncode, 2, "--force without --reason is refused")
        res = proc.run_capture([
            sys.executable, script_path, "scratch", "purge", slug, "--force", "--reason", "test teardown"
        ], cwd=self.repo)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Purged session blackboard", res.stdout)

    def test_merge_patch_nested_and_null_deletion(self):
        base = {
            "active_hypotheses": {"H1": {"status": "testing", "desc": "initial"}},
            "discovered_symbols": ["sym1"],
            "touched_files": ["a.py"],
            "open_defects": {"D1": "bug"},
            "custom": {"nested": {"k1": "v1", "k2": "v2"}, "flag": True},
        }
        delta = {
            "active_hypotheses": {"H1": {"status": "confirmed"}, "H2": "new"},
            "touched_files": ["b.py", "a.py"],
            "custom": {"nested": {"k2": None, "k3": "v3"}, "flag": False},
        }
        res = session.merge_patch(base, delta)
        self.assertEqual(res["active_hypotheses"]["H1"], {"status": "confirmed", "desc": "initial"})
        self.assertEqual(res["active_hypotheses"]["H2"], "new")
        self.assertEqual(res["touched_files"], ["a.py", "b.py"])
        self.assertEqual(res["custom"]["nested"], {"k1": "v1", "k3": "v3"})
        self.assertFalse(res["custom"]["flag"])

    def test_merge_patch_null_deletes_top_level_key(self):
        base = session.make_default_blackboard()
        base["active_hypotheses"] = {"H1": "active"}
        delta = {"active_hypotheses": None}
        res = session.merge_patch(base, delta)
        self.assertNotIn("active_hypotheses", res)

    def test_validate_blackboard_patch_rejects_disallowed_keys(self):
        with self.assertRaises(ValueError) as ctx:
            session.validate_blackboard_patch({"unknown_key": "val"})
        self.assertIn("Invalid blackboard key 'unknown_key'", str(ctx.exception))

    def test_validate_blackboard_patch_rejects_invalid_types(self):
        with self.assertRaises(ValueError):
            session.validate_blackboard_patch({"touched_files": "not-a-list"})
        with self.assertRaises(ValueError):
            session.validate_blackboard_patch({"touched_files": [123]})
        with self.assertRaises(ValueError):
            session.validate_blackboard_patch({"custom": ["not-a-dict"]})

    def test_patch_blackboard_persists_to_disk(self):
        slug = "patch-persist-task"
        session.init_session(self.repo, slug)
        res = session.patch_blackboard(self.repo, slug, {
            "active_hypotheses": {"H1": "testing"},
            "touched_files": ["foo.py"],
            "custom": {"metric": 42},
        })
        self.assertEqual(res["active_hypotheses"], {"H1": "testing"})
        self.assertEqual(res["touched_files"], ["foo.py"])
        self.assertEqual(res["custom"], {"metric": 42})

        loaded = session.load_blackboard(self.repo, slug)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["active_hypotheses"], {"H1": "testing"})
        self.assertEqual(loaded["touched_files"], ["foo.py"])
        self.assertEqual(loaded["custom"], {"metric": 42})

    def test_scratch_cli_patch_and_show(self):
        slug = "cli-patch-task"
        script_path = os.path.join(hermetic.REPO_ROOT, "scripts", "along_exec.py")
        session.init_session(self.repo, slug)

        # 1. Patch inline with --show
        patch_json = json.dumps({"active_hypotheses": {"H1": "testing"}, "touched_files": ["src/main.py"]})
        res = proc.run_capture([
            sys.executable, script_path, "scratch", "patch", slug, patch_json, "--show"
        ], cwd=self.repo)
        self.assertEqual(res.returncode, 0, f"patch failed: {res.stderr}")
        self.assertIn("Patched blackboard for session: cli-patch-task", res.stdout)
        data = json.loads(res.stdout.split("Patched blackboard for session: cli-patch-task\n", 1)[1])
        self.assertEqual(data["active_hypotheses"]["H1"], "testing")
        self.assertEqual(data["touched_files"], ["src/main.py"])

        # 2. Patch via --file with null-deletion
        file_path = os.path.join(self.repo, "delta.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({"active_hypotheses": {"H1": None}, "custom": {"key": "val"}}, f)
        res = proc.run_capture([
            sys.executable, script_path, "scratch", "patch", slug, "--file", "delta.json", "--show"
        ], cwd=self.repo)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout.split("Patched blackboard for session: cli-patch-task\n", 1)[1])
        self.assertNotIn("H1", data["active_hypotheses"])
        self.assertEqual(data["custom"]["key"], "val")

        # 3. Invalid JSON error handling
        res_bad = proc.run_capture([
            sys.executable, script_path, "scratch", "patch", slug, "{not-json}"
        ], cwd=self.repo)
        self.assertEqual(res_bad.returncode, 1)
        self.assertIn("Invalid JSON patch", res_bad.stderr)

        # 4. Schema validation error handling
        bad_schema = json.dumps({"invalid_field": 123})
        res_schema = proc.run_capture([
            sys.executable, script_path, "scratch", "patch", slug, bad_schema
        ], cwd=self.repo)
        self.assertEqual(res_schema.returncode, 1)
        self.assertIn("Schema validation failed", res_schema.stderr)

    def test_patch_blackboard_unrecorded_files_and_render(self):
        slug = "patch-unrecorded-task"
        session.init_session(self.repo, slug)
        session.patch_blackboard(self.repo, slug, {
            "active_hypotheses": {"H1": {"status": "proven"}},
            "touched_files": ["app.py"],
            "custom": {"env": "prod"},
        })

        unrecorded = session.unrecorded_files(self.repo, slug)
        self.assertEqual(unrecorded, [])

        md = session.render_blackboard_markdown(self.repo, slug)
        self.assertIn("### Structured Working Context", md)
        self.assertIn("#### Active Hypotheses", md)
        self.assertIn("proven", md)
        self.assertIn("#### Touched Files", md)
        self.assertIn("app.py", md)
        self.assertIn("#### Custom Variables", md)
        self.assertIn("prod", md)


