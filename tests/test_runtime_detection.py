#!/usr/bin/env python3
"""
tests/test_runtime_detection.py - Runtime detection, enforcement level, and doctor output.

Regression suite for [feat--cowork-runtime-support]. Environment-dependent functions are
called with explicit inputs, so results do not depend on the machine running the suite.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import entities, proc, runtime
import hermetic

COWORK_ENV = {"CLAUDE_CODE_HOST_HTTP_PROXY_PORT": "3128", "HOME": "/sessions/rcw-abc"}


class TestCoworkDetection(unittest.TestCase):
    def test_markers(self):
        self.assertTrue(runtime.is_cowork_env(COWORK_ENV))
        self.assertTrue(runtime.is_cowork_env({"ALONG_RUNTIME": "cowork"}))
        self.assertFalse(runtime.is_cowork_env({"CLAUDE_CODE_HOST_HTTP_PROXY_PORT": "1", "HOME": "/home/u"}))
        self.assertFalse(runtime.is_cowork_env({"HOME": "/sessions/x"}))

    def test_detect_agent_prefers_cowork_over_claude_code(self):
        env = dict(COWORK_ENV, CLAUDE_PROJECT_DIR="/x")
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(entities.detect_agent(), "cowork")
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": "/x", "HOME": "/home/u"}, clear=True):
            self.assertEqual(entities.detect_agent(), "claude-code")
        with mock.patch.dict(os.environ, dict(COWORK_ENV, ALONG_AGENT="me"), clear=True):
            self.assertEqual(entities.detect_agent(), "me")
        self.assertEqual(entities.detect_agent("explicit"), "explicit")

    def test_detect_agent_claude_code_shell_markers(self):
        """Markers a Claude Code shell really carries [bug--claude-runtime-not-detected]."""
        for marker in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID"):
            with mock.patch.dict(os.environ, {marker: "1", "HOME": "/home/u"}, clear=True):
                self.assertEqual(entities.detect_agent(), "claude-code", marker)

    def test_detect_agent_cursor_markers(self):
        for marker in ("CURSOR_AGENT", "CURSOR_TRACE_ID", "CURSOR_CLI"):
            with mock.patch.dict(os.environ, {marker: "1", "HOME": "/home/u"}, clear=True):
                self.assertEqual(entities.detect_agent(), "cursor", marker)
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1", "CURSOR_TRACE_ID": "t1", "HOME": "/home/u"}, clear=True):
            self.assertEqual(entities.detect_agent(), "claude-code")


class TestEnforcementLevel(unittest.TestCase):
    def test_cowork_and_unknown_are_advisory(self):
        home = tempfile.mkdtemp(prefix="along-rt-adv-")
        try:
            with mock.patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}):
                for name in ("cowork", "cursor", "unknown", "never-heard-of"):
                    level, why = runtime.enforcement_level(name)
                    self.assertEqual(level, runtime.ADVISORY, name)
                    self.assertTrue(why)
        finally:
            shutil.rmtree(home, ignore_errors=True)

    def test_cursor_enforcement_level_depends_on_registered_hooks(self):
        self.assertEqual(
            runtime.RUNTIME_MATRIX["cursor"]["skills"],
            "rules (.cursor/rules/along.mdc) + auto (~/.cursor/skills)",
        )
        self.assertIs(runtime.RUNTIME_MATRIX["cursor"]["runtime_hooks"], True)
        self.assertEqual(
            runtime.RUNTIME_MATRIX["cursor"]["unexpressible_tools"],
            ["view_image", "send_message", "spawn_subagent"],
        )

        home = tempfile.mkdtemp(prefix="along-rt-cursor-home-")
        repo_dir = tempfile.mkdtemp(prefix="along-rt-cursor-repo-")
        try:
            with mock.patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}):
                self.assertFalse(runtime.along_hooks_registered("cursor", repo_dir))
                level, why = runtime.enforcement_level("cursor", repo_dir)
                self.assertEqual(level, runtime.ADVISORY)
                self.assertIn("along hook install --runtime cursor", why)
                self.assertIn("advisory", why.lower())

                # Non-Along hooks in .cursor/hooks.json do not claim mechanical enforcement
                local_cursor = os.path.join(repo_dir, ".cursor")
                os.makedirs(local_cursor, exist_ok=True)
                local_hooks = os.path.join(local_cursor, "hooks.json")
                with open(local_hooks, "w", encoding="utf-8") as f:
                    f.write('{"version": 1, "hooks": {"preToolUse": [{"command": "echo custom"}]}}')
                self.assertFalse(runtime.along_hooks_registered("cursor", repo_dir))
                self.assertEqual(runtime.enforcement_level("cursor", repo_dir)[0], runtime.ADVISORY)

                # Local .cursor/hooks.json with Along hook enables mechanical enforcement
                with open(local_hooks, "w", encoding="utf-8") as f:
                    f.write('{"version": 1, "hooks": {"preToolUse": [{"command": "python scripts/along_hook.py --runtime cursor --event PreToolUse"}]}}')
                self.assertTrue(runtime.along_hooks_registered("cursor", repo_dir))
                level, why = runtime.enforcement_level("cursor", repo_dir)
                self.assertEqual(level, runtime.MECHANICAL)
                self.assertIn("cursor", why)

                # Global ~/.cursor/hooks.json with Along hook also counts when repo has none
                os.remove(local_hooks)
                self.assertFalse(runtime.along_hooks_registered("cursor", repo_dir))
                global_cursor = os.path.join(home, ".cursor")
                os.makedirs(global_cursor, exist_ok=True)
                with open(os.path.join(global_cursor, "hooks.json"), "w", encoding="utf-8") as f:
                    f.write('{"version": 1, "hooks": {"preToolUse": [{"command": "python ~/.along/bin/along_hook.py --runtime cursor --event PreToolUse"}]}}')
                self.assertTrue(runtime.along_hooks_registered("cursor", repo_dir))
                self.assertEqual(runtime.enforcement_level("cursor", repo_dir)[0], runtime.MECHANICAL)
        finally:
            shutil.rmtree(home, ignore_errors=True)
            shutil.rmtree(repo_dir, ignore_errors=True)

    def test_claude_code_is_mechanical_only_with_registered_hooks(self):
        home = tempfile.mkdtemp(prefix="along-rt-home-")
        try:
            with mock.patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}):
                self.assertEqual(runtime.enforcement_level("claude-code")[0], runtime.ADVISORY)
                os.makedirs(os.path.join(home, ".claude"))
                settings = os.path.join(home, ".claude", "settings.json")
                with open(settings, "w", encoding="utf-8") as f:
                    f.write('{"hooks": {"PreToolUse": [{"matcher": "Bash", "command": '
                            '"python along_hook.py --event PreToolUse"}], "Stop": [{"command": '
                            '"python along_hook.py --event Stop"}]}}')
                level, why = runtime.enforcement_level("claude-code")
                self.assertEqual(level, runtime.ADVISORY)
                self.assertIn("flat schema", why)
                with open(settings, "w", encoding="utf-8") as f:
                    f.write('{"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": '
                            '"python along_hook.py --event PreToolUse"}]}], "Stop": [{"hooks": '
                            '[{"type": "command", "command": "python along_hook.py --event Stop"}]}]}}')
                self.assertEqual(runtime.enforcement_level("claude-code")[0], runtime.MECHANICAL)
        finally:
            shutil.rmtree(home, ignore_errors=True)

    def test_heartbeat_roundtrip(self):
        root = tempfile.mkdtemp(prefix="along-rt-beat-")
        try:
            os.makedirs(os.path.join(root, ".along"))
            self.assertIsNone(runtime.last_heartbeat(root, "claude-code"))
            runtime.record_heartbeat(root, "claude", "2026-10-01T10:00:00Z")
            self.assertEqual(runtime.last_heartbeat(root, "claude-code"), "2026-10-01T10:00:00Z")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_python_floor(self):
        self.assertTrue(runtime.python_supported((3, 10, 0)))
        self.assertFalse(runtime.python_supported((3, 9, 18)))


class TestEnvironmentHazards(unittest.TestCase):
    def test_cross_os_mount(self):
        self.assertTrue(runtime.is_cross_os_mount("/r", fs_type="9p", platform="linux"))
        self.assertTrue(runtime.is_cross_os_mount("/r", fs_type="drvfs", platform="linux"))
        self.assertTrue(runtime.is_cross_os_mount("/r", fs_type="fuse", platform="linux"))
        self.assertTrue(runtime.is_cross_os_mount("/r", fs_type="fuse.sshfs", platform="linux"))
        self.assertTrue(runtime.is_cross_os_mount("/r", fs_type="ext4", core_symlinks="false", platform="linux"))
        self.assertFalse(runtime.is_cross_os_mount("/r", fs_type="ext4", core_symlinks=None, platform="linux"))
        self.assertFalse(runtime.is_cross_os_mount("C:/r", fs_type="9p", core_symlinks="false", platform="win32"))

        # Windows gitdir entries
        tmp = tempfile.mkdtemp(prefix="along-rt-gitdir-")
        try:
            wt_gitdir = os.path.join(tmp, ".git", "worktrees", "w1", "gitdir")
            os.makedirs(os.path.dirname(wt_gitdir), exist_ok=True)
            with open(wt_gitdir, "w", encoding="utf-8") as gf:
                gf.write("C:\\Users\\along\\worktrees\\w1\n")
            self.assertTrue(runtime.is_cross_os_mount(tmp, fs_type="ext4", platform="linux"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        # Windows core.worktree in .git/config
        tmp2 = tempfile.mkdtemp(prefix="along-rt-worktree-")
        try:
            cfg = os.path.join(tmp2, ".git", "config")
            os.makedirs(os.path.dirname(cfg), exist_ok=True)
            with open(cfg, "w", encoding="utf-8") as cf:
                cf.write("[core]\n\tworktree = D:/projects/along\n")
            self.assertTrue(runtime.is_cross_os_mount(tmp2, fs_type="ext4", platform="linux"))
        finally:
            shutil.rmtree(tmp2, ignore_errors=True)

    def test_mount_fs_type_picks_longest_prefix(self):
        root = tempfile.mkdtemp(prefix="along-rt-mounts-")
        try:
            mounts = os.path.join(root, "mounts")
            target = os.path.realpath(root)
            with open(mounts, "w", encoding="utf-8") as f:
                f.write("/dev/sda1 / ext4 rw 0 0\n")
                f.write(f"host {target} 9p rw 0 0\n")
            self.assertEqual(runtime.mount_fs_type(target, mounts_file=mounts), "9p")
            self.assertIsNone(runtime.mount_fs_type(target, mounts_file=os.path.join(root, "missing")))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_stale_index_lock(self):
        root = tempfile.mkdtemp(prefix="along-rt-lock-")
        try:
            os.makedirs(os.path.join(root, ".git"))
            self.assertFalse(runtime.stale_index_lock(root))
            open(os.path.join(root, ".git", "index.lock"), "w").close()
            self.assertTrue(runtime.stale_index_lock(root))
        finally:
            shutil.rmtree(root, ignore_errors=True)


class TestDoctorRuntimeSection(unittest.TestCase):
    def test_doctor_reports_runtime_and_enforcement(self):
        along_exec = os.path.join(SCRIPTS_DIR, "along_exec.py")
        env = hermetic.isolated_home_env()
        env["ALONG_RUNTIME"] = "cowork"
        env.pop("ALONG_AGENT", None)
        with hermetic.repo_fixture(prefix="along-rt-doctor-") as fixture:
            res = proc.run_capture([sys.executable, along_exec, "doctor"], cwd=fixture, env=env)
            self.assertIn("--- Runtime: cowork ---", res.stdout)
            self.assertIn("Gate enforcement: advisory", res.stdout)
            self.assertIn("Python", res.stdout)

    def test_doctor_reports_cursor_enforcement_and_narrowing(self):
        along_exec = os.path.join(SCRIPTS_DIR, "along_exec.py")
        home = self.make_temp_home()
        env = hermetic.isolated_home_env()
        env["HOME"] = home
        env["USERPROFILE"] = home
        env["ALONG_AGENT"] = "cursor"
        with hermetic.repo_fixture(prefix="along-rt-doc-cursor-") as fixture:
            res_adv = proc.run_capture([sys.executable, along_exec, "doctor"], cwd=fixture, env=env)
            self.assertIn("--- Runtime: cursor ---", res_adv.stdout)
            self.assertIn("Gate enforcement: advisory", res_adv.stdout)
            self.assertIn("along hook install --runtime cursor", res_adv.stdout)
            self.assertIn("Runtime hook narrowing (cursor)", res_adv.stdout)

            from alongkit.hooks.config import install_cursor_hooks
            status, _ = install_cursor_hooks(fixture)
            self.assertEqual(status, "installed")
            res_mech = proc.run_capture([sys.executable, along_exec, "doctor"], cwd=fixture, env=env)
            self.assertIn("--- Runtime: cursor ---", res_mech.stdout)
            self.assertIn("Gate enforcement: mechanical", res_mech.stdout)
            self.assertIn("Runtime hook narrowing (cursor)", res_mech.stdout)

    def make_temp_home(self):
        home = tempfile.mkdtemp(prefix="along-rt-doc-home-")
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        return home


if __name__ == "__main__":
    unittest.main(verbosity=2)
