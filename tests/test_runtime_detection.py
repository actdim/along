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


class TestEnforcementLevel(unittest.TestCase):
    def test_cowork_and_unknown_are_advisory(self):
        for name in ("cowork", "cursor", "unknown", "never-heard-of"):
            level, why = runtime.enforcement_level(name)
            self.assertEqual(level, runtime.ADVISORY, name)
            self.assertTrue(why)

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
        self.assertTrue(runtime.is_cross_os_mount("/r", fs_type="fuse.sshfs", platform="linux"))
        self.assertTrue(runtime.is_cross_os_mount("/r", fs_type="ext4", core_symlinks="false", platform="linux"))
        self.assertFalse(runtime.is_cross_os_mount("/r", fs_type="ext4", core_symlinks=None, platform="linux"))
        self.assertFalse(runtime.is_cross_os_mount("C:/r", fs_type="9p", core_symlinks="false", platform="win32"))

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
            res = proc.run_capture([sys.executable, along_exec, "doctor"], cwd=fixture, env=env,
                                   trip_on_anomaly=False)
            self.assertIn("--- Runtime: cowork ---", res.stdout)
            self.assertIn("Gate enforcement: advisory", res.stdout)
            self.assertIn("Python", res.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
