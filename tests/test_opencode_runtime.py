#!/usr/bin/env python3
"""
tests/test_opencode_runtime.py - Unit tests for OpenCode runtime hook integration.
"""

from __future__ import annotations

import json
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

from alongkit import entities, runtime, session
from alongkit.hooks import HookEventType, get_adapter
from alongkit.hooks.adapters.opencode import OpenCodeAdapter
from alongkit.hooks.config import install_opencode_hooks


class TestOpenCodeAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = OpenCodeAdapter()

    def test_adapter_registry(self):
        resolved = get_adapter("opencode")
        self.assertIsInstance(resolved, OpenCodeAdapter)
        self.assertEqual(resolved.runtime_name, "opencode")

    def test_parse_bash_tool(self):
        payload = json.dumps({
            "tool": "bash",
            "args": {"command": "git status"},
            "sessionID": "ses-opencode-101",
            "cwd": "/workspace",
        })
        event = self.adapter.parse(payload, event_type=HookEventType.PRE_TOOL_USE)
        self.assertEqual(event.tool_name, "run_command")
        self.assertEqual(event.tool_args.get("CommandLine"), "git status")
        self.assertEqual(event.conversation_id, "ses-opencode-101")
        self.assertEqual(event.runtime, "opencode")

    def test_parse_write_tool(self):
        payload = json.dumps({
            "tool": "write",
            "args": {"filePath": "src/main.py", "content": "print('hello')"},
            "sessionID": "ses-opencode-102",
        })
        event = self.adapter.parse(payload, event_type=HookEventType.PRE_TOOL_USE)
        self.assertEqual(event.tool_name, "write_to_file")
        self.assertEqual(event.tool_args.get("TargetFile"), "src/main.py")
        self.assertEqual(event.tool_args.get("CodeContent"), "print('hello')")
        self.assertEqual(event.conversation_id, "ses-opencode-102")

    def test_parse_edit_tool(self):
        payload = json.dumps({
            "tool": "edit",
            "args": {"filePath": "src/main.py", "new_string": "print('world')"},
            "sessionID": "ses-opencode-103",
        })
        event = self.adapter.parse(payload, event_type=HookEventType.PRE_TOOL_USE)
        self.assertEqual(event.tool_name, "replace_file_content")
        self.assertEqual(event.tool_args.get("TargetFile"), "src/main.py")
        self.assertEqual(event.tool_args.get("ReplacementContent"), "print('world')")


class TestOpenCodeSessionAndDetection(unittest.TestCase):
    def test_detect_agent_from_session_id(self):
        with mock.patch.dict(os.environ, {"OPENCODE_SESSION_ID": "opencode-session-123"}, clear=True):
            self.assertEqual(entities.detect_agent(), "opencode")

    def test_session_key_resolution(self):
        env = {"OPENCODE_SESSION_ID": "sess-xyz-987"}
        key = session.current_session_key(env)
        self.assertEqual(key, "opencode--sess-xyz-987")


class TestOpenCodeHookInstallAndRegistration(unittest.TestCase):
    def setUp(self):
        self.tmp_home = tempfile.mkdtemp(prefix="along-opencode-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp_home, ignore_errors=True)

    def test_install_and_registration(self):
        status, msg = install_opencode_hooks(
            is_global=True, target_home=os.path.join(self.tmp_home, ".config", "opencode")
        )
        self.assertEqual(status, "installed")
        plugin_path = os.path.join(self.tmp_home, ".config", "opencode", "plugins", "along-gates.js")
        self.assertTrue(os.path.isfile(plugin_path))

        # Re-running install reports already up to date
        status_repeat, _ = install_opencode_hooks(
            is_global=True, target_home=os.path.join(self.tmp_home, ".config", "opencode")
        )
        self.assertEqual(status_repeat, "present")

        # Runtime detection sees registered hooks
        with mock.patch.dict(os.environ, {"HOME": self.tmp_home, "USERPROFILE": self.tmp_home}):
            self.assertTrue(runtime.along_hooks_registered("opencode"))
            level, why = runtime.enforcement_level("opencode")
            self.assertEqual(level, runtime.MECHANICAL)
            self.assertIn("Along hooks are registered for opencode", why)


if __name__ == "__main__":
    unittest.main()
