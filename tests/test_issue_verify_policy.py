#!/usr/bin/env python3
"""
tests/test_issue_verify_policy.py - Tests for issue-level verify policy (REQ-2, 3, 4, 7).

Covers:
- CLI flags on issue create and update write and validate the verify block.
- plan approve snapshots the verify block and refuses an invalid block.
- gates run under effective policy and pass ALONG_TEST_* env variables to hook.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import entities, gates, proc, session, textio, verify
import hermetic


class TestIssueVerifyPolicy(unittest.TestCase):
    def setUp(self):
        self.root = hermetic.make_repo_fixture(prefix="along-issue-verify-")
        textio.write_text(
            os.path.join(self.root, ".along", "config.json"),
            json.dumps({"verify": {"scopes": {"api": ["src/api/**"]}}}) + "\n",
        )
        for cmd in (
            ["git", "init", "-q"],
            ["git", "config", "user.email", "t@example.com"],
            ["git", "config", "user.name", "T"],
            ["git", "add", "-A"],
            ["git", "commit", "-q", "-m", "init"],
        ):
            proc.run_capture(cmd, cwd=self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_01_cli_create_and_update_verify_flags(self):
        along_exec = os.path.join(SCRIPTS_DIR, "along_exec.py")

        # Create with invalid scope fails with code 2
        res_bad = proc.run_capture(
            [
                sys.executable, along_exec, "issue", "create", "feat", "bad-scope",
                "--title", "Bad Scope",
                "--verify-tests", "scoped",
                "--verify-scope", "invalid-scope",
                "--verify-reason", "testing",
            ],
            cwd=self.root,
        )
        self.assertEqual(res_bad.returncode, 2)
        self.assertIn("not declared in verify.scopes", res_bad.stderr or res_bad.stdout)

        # Create with valid verify flags succeeds
        res_ok = proc.run_capture(
            [
                sys.executable, along_exec, "issue", "create", "feat", "api-feature",
                "--title", "API Feature",
                "--verify-tests", "scoped",
                "--verify-scope", "api",
                "--verify-reason", "API only",
            ],
            cwd=self.root,
        )
        self.assertEqual(res_ok.returncode, 0)

        iss = entities.find_issue_by_slug(self.root, "api-feature")
        self.assertIsNotNone(iss)
        v = iss["frontmatter"].get("verify")
        self.assertEqual(v["tests"], "scoped")
        self.assertEqual(v["scope"], "api")
        self.assertEqual(v["reason"], "API only")

        # Update verify flags
        res_up = proc.run_capture(
            [
                sys.executable, along_exec, "issue", "update", "api-feature",
                "--verify-tests", "affected",
                "--verify-reason", "affected only",
            ],
            cwd=self.root,
        )
        self.assertEqual(res_up.returncode, 0)
        iss_up = entities.find_issue_by_slug(self.root, "api-feature")
        v_up = iss_up["frontmatter"].get("verify")
        self.assertEqual(v_up["tests"], "affected")
        self.assertEqual(v_up["reason"], "affected only")

        # Update with --verify-clear removes verify
        res_clear = proc.run_capture(
            [sys.executable, along_exec, "issue", "update", "api-feature", "--verify-clear"],
            cwd=self.root,
        )
        self.assertEqual(res_clear.returncode, 0)
        iss_cleared = entities.find_issue_by_slug(self.root, "api-feature")
        self.assertFalse(iss_cleared["frontmatter"].get("verify"))

    def test_02_plan_approve_snapshots_verify_and_refuses_invalid(self):
        along_exec = os.path.join(SCRIPTS_DIR, "along_exec.py")

        # Create issue with valid verify
        proc.run_capture(
            [
                sys.executable, along_exec, "issue", "create", "feat", "snap-test",
                "--title", "Snapshot Test",
                "--verify-tests", "scoped",
                "--verify-scope", "api",
                "--verify-reason", "api tests",
            ],
            cwd=self.root,
        )

        # Replace scaffold stub with real requirements
        iss_file = entities.find_issue_by_slug(self.root, "snap-test")["file_path"]
        textio.write_text(
            iss_file,
            "---\nprotocol: along\nprotocol_version: \"4.8.1\"\nslug: snap-test\ntype: feat\nstatus: open\n"
            "priority: medium\ncreated: 2026-11-13\nupdated: 2026-11-13\nagent: antigravity\ntags: []\n"
            "blocked_by: []\nrelated: []\nverify: {tests: scoped, scope: api, reason: \"api tests\"}\n---\n\n"
            "# Snapshot Test\n\nReal problem statement.\n\n## Requirements\n- REQ-1: Real requirement.\n\n"
            "## Acceptance Criteria\n- [ ] Concrete criterion.\n",
        )

        plan_path = os.path.join(self.root, "plan.md")
        textio.write_text(plan_path, "# Plan\n1. Step\n")

        # Approve ahead snapshots verify block
        res_app = proc.run_capture(
            [sys.executable, along_exec, "plan", "approve", "snap-test", "--plan-file", plan_path],
            cwd=self.root,
        )
        self.assertEqual(res_app.returncode, 0, res_app.stderr)
        snap = session.approved_verify_snapshot(self.root, "snap-test")
        self.assertIsNotNone(snap)
        self.assertEqual(snap["tests"], "scoped")
        self.assertEqual(snap["scope"], "api")
        self.assertEqual(snap["reason"], "api tests")

        # Now tamper issue frontmatter to make it invalid directly
        entities.update_issue_frontmatter(
            self.root, "snap-test",
            {"verify": {"tests": "scoped", "scope": "undeclared", "reason": "bad"}},
        )
        # Attempt to re-approve: must refuse
        res_refuse = proc.run_capture(
            [sys.executable, along_exec, "plan", "approve", "snap-test", "--plan-file", plan_path],
            cwd=self.root,
        )
        self.assertNotEqual(res_refuse.returncode, 0)
        self.assertIn("Plan approval refused", res_refuse.stderr or res_refuse.stdout)

    def test_03_gate_passes_env_to_runner_and_cleans_temp_file(self):
        along_exec = os.path.join(SCRIPTS_DIR, "along_exec.py")

        # Create test hook that dumps env variables to a file
        env_dump_path = os.path.join(self.root, "env_dump.json").replace("\\", "/")
        scripts_dir = os.path.join(self.root, ".along", "scripts")
        os.makedirs(scripts_dir, exist_ok=True)
        hook_py = os.path.join(scripts_dir, "test.py")
        textio.write_text(
            hook_py,
            "import json, os, sys, unittest\n"
            f"dump_path = '{env_dump_path}'\n"
            "data = {\n"
            "    'mode': os.environ.get('ALONG_TEST_MODE'),\n"
            "    'scope': os.environ.get('ALONG_TEST_SCOPE'),\n"
            "    'files_path': os.environ.get('ALONG_ATTRIBUTED_FILES'),\n"
            "}\n"
            "fp = data['files_path']\n"
            "if fp and os.path.isfile(fp):\n"
            "    with open(fp, 'r', encoding='utf-8') as h:\n"
            "        data['attributed_files'] = h.read().splitlines()\n"
            "with open(dump_path, 'w', encoding='utf-8') as h:\n"
            "    json.dump(data, h)\n"
            "class T(unittest.TestCase):\n"
            "    def test_one(self):\n"
            "        pass\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n",
        )

        proc.run_capture(
            [
                sys.executable, along_exec, "issue", "create", "feat", "env-test",
                "--title", "Env Test",
                "--verify-tests", "affected",
                "--verify-reason", "affected tests only",
            ],
            cwd=self.root,
        )
        iss_file = entities.find_issue_by_slug(self.root, "env-test")["file_path"]
        textio.write_text(
            iss_file,
            "---\nprotocol: along\nprotocol_version: \"4.8.1\"\nslug: env-test\ntype: feat\nstatus: open\n"
            "priority: medium\ncreated: 2026-11-13\nupdated: 2026-11-13\nagent: antigravity\ntags: []\n"
            "blocked_by: []\nrelated: []\nverify: {tests: affected, reason: \"affected tests only\"}\n---\n\n"
            "# Env Test\n\nReal problem statement.\n\n## Requirements\n- REQ-1: Real requirement.\n\n"
            "## Acceptance Criteria\n- [ ] Concrete criterion.\n",
        )
        plan_path = os.path.join(self.root, "plan.md")
        textio.write_text(plan_path, "# Plan\n1. Step\n")
        res_p = proc.run_capture(
            [sys.executable, along_exec, "plan", "approve", "env-test", "--plan-file", plan_path],
            cwd=self.root,
        )
        self.assertEqual(res_p.returncode, 0, res_p.stderr)

        outcome = gates.run_test_gate(
            self.root,
            label="Test Gate",
            slug="env-test",
            files=["src/api/handler.py", "docs/guide.md"],
        )
        self.assertEqual(outcome, gates.TESTS_PASSED)
        self.assertTrue(os.path.isfile(env_dump_path))
        with open(env_dump_path, "r", encoding="utf-8") as h:
            dumped = json.load(h)

        self.assertEqual(dumped["mode"], "affected")
        self.assertEqual(dumped["scope"], "")
        temp_files_path = dumped["files_path"]
        self.assertTrue(temp_files_path and len(temp_files_path) > 0)
        self.assertEqual(dumped["attributed_files"], ["src/api/handler.py", "docs/guide.md"])
        # Temp file must be deleted after gate completes
        self.assertFalse(os.path.exists(temp_files_path), "Attributed temp file must be unlinked in finally block")

    def test_04_along_exec_strips_test_mode_flags_from_hook_argv(self):
        along_exec = os.path.join(REPO_ROOT, "scripts", "along_exec.py")
        argv_dump_path = os.path.join(self.root, "argv.json")
        hook_path = os.path.join(self.root, ".along", "scripts", "test.py")
        textio.write_text(
            hook_path,
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            f"with open(r'{argv_dump_path}', 'w', encoding='utf-8') as h:\n"
            "    json.dump(sys.argv[1:], h)\n"
            "sys.exit(0)\n",
        )
        res = proc.run_capture(
            [sys.executable, along_exec, "test", "--scope", "api", "--extra-flag", "val"],
            cwd=self.root,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue(os.path.isfile(argv_dump_path))
        with open(argv_dump_path, "r", encoding="utf-8") as h:
            argv = json.load(h)
        self.assertNotIn("--scope", argv)
        self.assertNotIn("api", argv)
        self.assertEqual(argv, ["--extra-flag", "val"])


if __name__ == "__main__":
    unittest.main()
