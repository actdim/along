#!/usr/bin/env python3
"""
tests/test_worktree.py - Hermetic tests for Git worktree workspace isolation.

Verifies feat--runtime-worktree-isolation:
- REQ-1: Architectural rules and fail-fast contract
- REQ-2: Worktree isolation engine (alongkit.worktree)
- REQ-3: CLI integration (along worktree) and declarative gates
- REQ-4: Dependency linking, config propagation, and blackboard preservation
- REQ-5: Safe teardown without parent dependency destruction and Windows lock resilience
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
TESTS_DIR = os.path.join(REPO_ROOT, "tests")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

from alongkit import proc, repo, textio, worktree
from alongkit.hooks import models, predicates
from alongkit.install import is_link
import hermetic


class TestWorktreeIsolation(unittest.TestCase):

    def setUp(self):
        self.root = hermetic.make_repo_fixture(prefix="along-wt-test-")
        # Initialize throwaway Git repository
        proc.git(["init"], cwd=self.root)
        proc.git(["config", "user.name", "Test Committer"], cwd=self.root)
        proc.git(["config", "user.email", "test@example.com"], cwd=self.root)
        proc.git(["config", "commit.gpgSign", "false"], cwd=self.root)
        # Create initial commit so HEAD resolves
        proc.git(["add", "."], cwd=self.root)
        proc.git(["commit", "-m", "initial commit [feat--base-setup]"], cwd=self.root)

    def tearDown(self):
        # Reset CWD to REPO_ROOT before teardown to avoid Windows handle locks
        try:
            os.chdir(REPO_ROOT)
        except OSError:
            pass
        # Unlink all worktrees if present
        wt_dir = os.path.join(self.root, ".along", "worktrees")
        if os.path.isdir(wt_dir):
            for item in os.listdir(wt_dir):
                sub = os.path.join(wt_dir, item)
                worktree.unlink_environment(sub)
        shutil.rmtree(self.root, ignore_errors=True)

    def test_01_is_supported_in_git_repo(self):
        supported, reason = worktree.is_worktree_supported(self.root)
        self.assertTrue(supported, f"Expected worktree supported in clean Git repo, got: {reason}")

        # In a bare non-git directory:
        non_git = hermetic.make_repo_fixture(prefix="along-nongit-")
        try:
            n_sup, n_reason = worktree.is_worktree_supported(non_git)
            self.assertFalse(n_sup)
            self.assertIn("Git", n_reason)
        finally:
            shutil.rmtree(non_git, ignore_errors=True)

    def test_02_create_worktree_and_environment_links(self):
        # Create primary repository dependencies and configs
        nm_dir = os.path.join(self.root, "node_modules", "sample-pkg")
        os.makedirs(nm_dir, exist_ok=True)
        textio.write_text(os.path.join(nm_dir, "index.js"), "module.exports = 'sample';\n")

        venv_dir = os.path.join(self.root, ".venv", "lib")
        os.makedirs(venv_dir, exist_ok=True)

        env_file = os.path.join(self.root, ".env")
        textio.write_text(env_file, "API_KEY=secret-token-123\n")

        # Create worktree
        info = worktree.create_worktree(self.root, "feat-test-worker")
        self.assertEqual(info.slug, "feat-test-worker")
        self.assertEqual(info.branch, "along/feat-test-worker")
        self.assertTrue(os.path.isdir(info.path))
        self.assertTrue(worktree.is_worktree(info.path))

        # Verify dependency directory is linked
        wt_nm = os.path.join(info.path, "node_modules")
        self.assertTrue(os.path.exists(wt_nm))
        self.assertTrue(is_link(wt_nm) or os.path.islink(wt_nm))
        self.assertTrue(os.path.isfile(os.path.join(wt_nm, "sample-pkg", "index.js")))

        # Verify .env was propagated (copied)
        wt_env = os.path.join(info.path, ".env")
        self.assertTrue(os.path.isfile(wt_env))
        self.assertEqual(textio.read_text(wt_env).strip(), "API_KEY=secret-token-123")

        # Verify manifest
        manifest_path = os.path.join(info.path, ".along-worktree.json")
        self.assertTrue(os.path.isfile(manifest_path))
        data = json.loads(textio.read_text(manifest_path))
        self.assertEqual(data["slug"], "feat-test-worker")
        self.assertIn("node_modules", data["linked_dirs"])
        self.assertIn(".env", data["copied_files"])

    def test_03_worktree_isolation_protects_primary_tree(self):
        info = worktree.create_worktree(self.root, "feat-isolated-run")

        # Mutate a file strictly inside the worktree
        wt_file = os.path.join(info.path, "isolated_change.py")
        textio.write_text(wt_file, "print('isolated')\n")

        # Verify primary repository working tree remains clean
        status_res = proc.git(["status", "--porcelain"], cwd=self.root)
        self.assertEqual(status_res.stdout.strip(), "", "Primary working tree was contaminated by worktree edit")

    def test_04_session_blackboard_real_time_sharing_and_preservation(self):
        info = worktree.create_worktree(self.root, "feat-blackboard-test")

        # Write review report inside worktree blackboard
        wt_review_dir = os.path.join(info.path, ".along", ".session", "feat-blackboard-test", "reviews")
        os.makedirs(wt_review_dir, exist_ok=True)
        wt_review_file = os.path.join(wt_review_dir, "step-1.md")
        textio.write_text(wt_review_file, "# Review Step 1\nVERDICT: PASS\n")

        # Verify review file is immediately visible in primary repository blackboard
        primary_review_file = os.path.join(self.root, ".along", ".session", "feat-blackboard-test", "reviews", "step-1.md")
        self.assertTrue(os.path.isfile(primary_review_file))
        self.assertEqual(textio.read_text(primary_review_file), "# Review Step 1\nVERDICT: PASS\n")

        # Tear down worktree
        removed = worktree.remove_worktree(self.root, "feat-blackboard-test", force=True)
        self.assertTrue(removed)
        self.assertFalse(os.path.exists(info.path))

        # Verify session blackboard in primary repo survives teardown!
        self.assertTrue(os.path.isfile(primary_review_file))
        self.assertEqual(textio.read_text(primary_review_file), "# Review Step 1\nVERDICT: PASS\n")

    def test_05_teardown_does_not_delete_parent_dependencies(self):
        # Create primary dependency folder
        nm_dir = os.path.join(self.root, "node_modules", "critical-pkg")
        os.makedirs(nm_dir, exist_ok=True)
        pkg_file = os.path.join(nm_dir, "lib.js")
        textio.write_text(pkg_file, "module.exports = 42;\n")

        # Create worktree, then tear it down
        info = worktree.create_worktree(self.root, "feat-teardown-safe")
        self.assertTrue(os.path.exists(os.path.join(info.path, "node_modules", "critical-pkg", "lib.js")))

        removed = worktree.remove_worktree(self.root, "feat-teardown-safe", force=True)
        self.assertTrue(removed)

        # Primary repository dependency file MUST still exist!
        self.assertTrue(os.path.isfile(pkg_file), "Primary repository node_modules was destroyed by worktree removal!")
        self.assertEqual(textio.read_text(pkg_file), "module.exports = 42;\n")

    def test_06_merge_worktree_squash(self):
        info = worktree.create_worktree(self.root, "feat-feature-branch")

        # Create commit in worktree
        feature_file = os.path.join(info.path, "feature.txt")
        textio.write_text(feature_file, "implemented feature\n")
        proc.git(["add", "feature.txt"], cwd=info.path)
        proc.git(["commit", "-m", "add feature [feat--feature-branch]"], cwd=info.path)

        # Merge squash into primary repo
        res = worktree.merge_worktree(self.root, "feat-feature-branch", strategy="squash")
        self.assertTrue(res.ok, f"Merge failed: {res.stderr}")

        # Verify feature.txt is now present and staged in primary working tree
        primary_feature = os.path.join(self.root, "feature.txt")
        self.assertTrue(os.path.isfile(primary_feature))
        status_res = proc.git(["status", "--porcelain"], cwd=self.root)
        self.assertIn("feature.txt", status_res.stdout)

    def test_07_cli_worktree_lifecycle(self):
        along_exec = os.path.join(SCRIPTS_DIR, "along_exec.py")

        # 1. status empty
        res = proc.run_capture([sys.executable, along_exec, "worktree", "status"], cwd=self.root)
        self.assertTrue(res.ok)
        self.assertIn("No active Along worktrees", res.stdout)

        # 2. create
        res = proc.run_capture([sys.executable, along_exec, "worktree", "create", "cli-test-wt"], cwd=self.root)
        self.assertTrue(res.ok, f"Create failed: {res.stderr}")
        self.assertIn("Created isolated worktree", res.stdout)

        # 3. list --json
        res = proc.run_capture([sys.executable, along_exec, "worktree", "list", "--json"], cwd=self.root)
        self.assertTrue(res.ok)
        data = json.loads(res.stdout)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["slug"], "cli-test-wt")

        # 4. gc
        res = proc.run_capture([sys.executable, along_exec, "worktree", "gc"], cwd=self.root)
        self.assertTrue(res.ok)
        self.assertIn("Pruned worktrees", res.stdout)

        # 5. remove
        res = proc.run_capture([sys.executable, along_exec, "worktree", "remove", "cli-test-wt", "--force"], cwd=self.root)
        self.assertTrue(res.ok, f"Remove failed: {res.stderr}")
        self.assertIn("Successfully removed worktree", res.stdout)

    def test_08_fail_fast_on_repo_without_head(self):
        # Create fresh git repo without commits
        empty_git = hermetic.make_repo_fixture(prefix="along-nohead-")
        try:
            proc.git(["init"], cwd=empty_git)
            with self.assertRaises(RuntimeError) as ctx:
                worktree.create_worktree(empty_git, "no-head-test")
            self.assertIn("fail-fast", str(ctx.exception))
        finally:
            shutil.rmtree(empty_git, ignore_errors=True)

    def test_09_predicate_worktree_env_readiness(self):
        # Primary repo has node_modules
        os.makedirs(os.path.join(self.root, "node_modules"), exist_ok=True)

        # Create worktree
        info = worktree.create_worktree(self.root, "feat-pred-test")

        # Event targeting worktree with linked environment
        event_ok = models.HookEvent(
            event_type=models.HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": os.path.join(info.path, "test.py"), "CodeContent": "pass\n"},
        )
        violation = predicates.check_worktree_env_readiness(event_ok, repo_root=self.root)
        self.assertIsNone(violation, f"Expected no violation for ready worktree, got: {violation}")

        # Simulate unlinked dependency directory in worktree
        worktree.unlink_directory(os.path.join(info.path, "node_modules"))
        violation_bad = predicates.check_worktree_env_readiness(event_ok, repo_root=self.root)
        self.assertIsNotNone(violation_bad, "Expected violation when node_modules is missing from worktree")
        self.assertIn("Worktree Environment Readiness Violation", violation_bad)
        self.assertIn("[gate: worktree-env-readiness]", violation_bad)

    def test_10_cross_os_mount_rejection_and_force_flag(self):
        # 1. Simulate POSIX host with core.symlinks=false
        proc.git(["config", "core.symlinks", "false"], cwd=self.root)
        with mock.patch("sys.platform", "linux"):
            supported, reason = worktree.is_worktree_supported(self.root)
            self.assertFalse(supported)
            self.assertIn("Cross-OS mounted repository detected", reason)
            self.assertIn("--force-cross-os", reason)

            # create_worktree must refuse without touching .git/worktrees
            with self.assertRaises(RuntimeError) as ctx:
                worktree.create_worktree(self.root, "cross-os-refused")
            self.assertIn("fail-fast check", str(ctx.exception))
            self.assertIn("Cross-OS", str(ctx.exception))
            git_wt_dir = os.path.join(self.root, ".git", "worktrees")
            self.assertFalse(os.path.exists(git_wt_dir), ".git/worktrees must not be modified or created on refusal")

            # --force-cross-os bypasses the refusal
            supported_forced, _ = worktree.is_worktree_supported(self.root, force_cross_os=True)
            self.assertTrue(supported_forced)
            info = worktree.create_worktree(self.root, "cross-os-forced", force_cross_os=True)
            self.assertEqual(info.slug, "cross-os-forced")
            self.assertTrue(os.path.isdir(info.path))
            self.assertTrue(worktree.is_worktree(info.path))

    def test_11_cross_os_mount_simulated_inputs(self):
        # Reset core.symlinks
        proc.git(["config", "--unset", "core.symlinks"], cwd=self.root)

        with mock.patch("sys.platform", "linux"):
            # a) 9p, drvfs, fuse filesystem types
            with mock.patch("alongkit.runtime.mount_fs_type", return_value="9p"):
                self.assertTrue(worktree.is_cross_os_mount(self.root))
                sup, _ = worktree.is_worktree_supported(self.root)
                self.assertFalse(sup)

            with mock.patch("alongkit.runtime.mount_fs_type", return_value="drvfs"):
                self.assertTrue(worktree.is_cross_os_mount(self.root))
                sup, _ = worktree.is_worktree_supported(self.root)
                self.assertFalse(sup)

            with mock.patch("alongkit.runtime.mount_fs_type", return_value="fuse.sshfs"):
                self.assertTrue(worktree.is_cross_os_mount(self.root))
                sup, _ = worktree.is_worktree_supported(self.root)
                self.assertFalse(sup)

            # Clean ext4 fs with no cross-os markers should be supported
            with mock.patch("alongkit.runtime.mount_fs_type", return_value="ext4"):
                self.assertFalse(worktree.is_cross_os_mount(self.root))

            # b) Windows-style gitdir entries in .git/worktrees/*/gitdir
            wt_gitdir = os.path.join(self.root, ".git", "worktrees", "simulated-win", "gitdir")
            os.makedirs(os.path.dirname(wt_gitdir), exist_ok=True)
            textio.write_text(wt_gitdir, "C:\\Users\\tester\\repo\\.along\\worktrees\\simulated-win\n")
            with mock.patch("alongkit.runtime.mount_fs_type", return_value="ext4"):
                self.assertTrue(worktree.is_cross_os_mount(self.root))
                sup, _ = worktree.is_worktree_supported(self.root)
                self.assertFalse(sup)

            # Clean up gitdir entry
            shutil.rmtree(os.path.join(self.root, ".git", "worktrees"))

            # c) Windows-style core.worktree config
            proc.git(["config", "core.worktree", "D:/projects/along"], cwd=self.root)
            with mock.patch("alongkit.runtime.mount_fs_type", return_value="ext4"):
                self.assertTrue(worktree.is_cross_os_mount(self.root))
                sup, _ = worktree.is_worktree_supported(self.root)
                self.assertFalse(sup)

    def test_12_cli_worktree_create_and_force_flag(self):
        # Configure cross-os indicator
        proc.git(["config", "core.symlinks", "false"], cwd=self.root)
        import along_exec

        # 1. without --force-cross-os -> exit code 1, stderr contains failure message
        err = io.StringIO()
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            with mock.patch("sys.platform", "linux"):
                with self.assertRaises(SystemExit) as ctx:
                    along_exec.handle_worktree_command(self.root, ["create", "cli-cross-test"])
                self.assertEqual(ctx.exception.code, 1)
        self.assertIn("Cross-OS", err.getvalue())
        self.assertFalse(os.path.exists(os.path.join(self.root, ".git", "worktrees")))

        # 2. with --force-cross-os -> exit code 0, success
        err = io.StringIO()
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            with mock.patch("sys.platform", "linux"):
                with self.assertRaises(SystemExit) as ctx:
                    along_exec.handle_worktree_command(self.root, ["create", "cli-cross-test", "--force-cross-os"])
                self.assertEqual(ctx.exception.code, 0)
        self.assertIn("Created isolated worktree", out.getvalue())

    def test_13_along_start_worktree_degrades_gracefully(self):
        # Create a mock issue in .along/ISSUES
        issue_file = os.path.join(self.root, ".along", "ISSUES", "task--degrade-test.md")
        os.makedirs(os.path.dirname(issue_file), exist_ok=True)
        content = (
            "---\n"
            "protocol: along\n"
            "protocol_version: '4.2.0'\n"
            "slug: degrade-test\n"
            "type: task\n"
            "status: open\n"
            "priority: medium\n"
            "---\n"
            "# Degrade Test\n"
        )
        textio.write_text(issue_file, content)

        # Configure cross-os indicator
        proc.git(["config", "core.symlinks", "false"], cwd=self.root)
        import along_exec

        err = io.StringIO()
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            with mock.patch("sys.platform", "linux"):
                with self.assertRaises(SystemExit) as ctx:
                    along_exec.handle_start_command(self.root, ["degrade-test", "--approved", "--worktree"])
                self.assertEqual(ctx.exception.code, 0)

        err_output = err.getvalue()
        out_output = out.getvalue()
        # Warning should be issued
        self.assertIn("Worktree unavailable on cross-OS mount", err_output)
        self.assertIn("degrading to in-place mode", err_output)
        # Session bound in-place
        self.assertIn("Ready to work on issue 'degrade-test'", out_output)
        # Worktree path should NOT have been created
        wt_path = os.path.join(self.root, ".along", "worktrees", "degrade-test")
        self.assertFalse(os.path.exists(wt_path), "Worktree directory must not be created when degraded")



if __name__ == "__main__":
    unittest.main()
