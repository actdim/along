#!/usr/bin/env python3
"""
tests/test_hooks_dsh.py - Tests for DeepSeek Harness (DSH) adapter and hook configuration.
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

from alongkit import install, runtime
from alongkit.hooks import GateDecision, GateResult, HookEventType, evaluate_event, get_adapter
from alongkit.hooks.adapters.dsh import DeepSeekHarnessAdapter, DSH_TOOL_NAME_MAP
from alongkit.hooks.config import install_dsh_hooks


class TestDshAdapter(unittest.TestCase):
    """Unit tests for DeepSeekHarnessAdapter parsing and response formatting."""

    def setUp(self):
        self.adapter = DeepSeekHarnessAdapter()

    def test_adapter_registry(self):
        self.assertIsInstance(get_adapter("dsh"), DeepSeekHarnessAdapter)
        self.assertIsInstance(get_adapter("deepseek"), DeepSeekHarnessAdapter)
        self.assertIsInstance(get_adapter("deepseek-harness"), DeepSeekHarnessAdapter)

    def test_pwsh_tool_mapping(self):
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "tool-pwsh",
            "tool_input": {"script": "Get-ChildItem -Path ."},
            "cwd": "C:/fake/path",
        }
        event = self.adapter.parse(json.dumps(payload))
        self.assertEqual(event.tool_name, "run_command")
        self.assertEqual(event.tool_args.get("CommandLine"), "Get-ChildItem -Path .")
        self.assertEqual(event.runtime, "dsh")

    def test_bash_tool_mapping(self):
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "tool-bash",
            "tool_input": {"command": "ls -la"},
            "cwd": "/fake/path",
        }
        event = self.adapter.parse(json.dumps(payload))
        self.assertEqual(event.tool_name, "run_command")
        self.assertEqual(event.tool_args.get("CommandLine"), "ls -la")

    def test_fs_tool_write_action_mapping(self):
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "tool-fs",
            "tool_input": {
                "action": "write",
                "path": "src/app.py",
                "content": "print('hello')",
            },
        }
        event = self.adapter.parse(json.dumps(payload))
        self.assertEqual(event.tool_name, "write_to_file")
        self.assertEqual(event.tool_args.get("Path"), "src/app.py")

    def test_fs_tool_edit_action_mapping(self):
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "tool-fs",
            "tool_input": {
                "action": "edit",
                "file_path": "src/app.py",
                "old_string": "foo",
                "new_string": "bar",
            },
        }
        event = self.adapter.parse(json.dumps(payload))
        self.assertEqual(event.tool_name, "replace_file_content")
        self.assertEqual(event.tool_args.get("Path"), "src/app.py")

    def test_fs_search_mapping(self):
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "tool-fs-search",
            "tool_input": {"pattern": "*.py"},
        }
        event = self.adapter.parse(json.dumps(payload))
        self.assertEqual(event.tool_name, "find_by_name")

    def test_format_response_deny(self):
        res = GateResult(decision=GateDecision.DENY, reason="Blocked by gate", exit_code=2)
        code, msg = self.adapter.format_response(res)
        self.assertEqual(code, 2)
        self.assertIn("Blocked by gate", msg)

    def test_format_response_allow(self):
        res = GateResult(decision=GateDecision.ALLOW, exit_code=0)
        code, msg = self.adapter.format_response(res)
        self.assertEqual(code, 0)


class TestDshHookConfig(unittest.TestCase):
    """Tests for cordis.patch.yml hook installation and idempotency."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="along-dsh-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_install_local_dsh_hooks(self):
        repo_root = os.path.join(self.tmp, "repo")
        os.makedirs(repo_root)

        status, msg = install_dsh_hooks(repo_root=repo_root, dry_run=False, is_global=False)
        self.assertEqual(status, "installed")

        patch_file = os.path.join(repo_root, ".dsh", "cordis.patch.yml")
        self.assertTrue(os.path.isfile(patch_file))
        content = open(patch_file, "r", encoding="utf-8").read()
        self.assertIn("@deepseek-ai/dsh-hooks-claude-code", content)
        self.assertIn("along-hooks-bridge", content)

        # Second run should be idempotent
        status2, msg2 = install_dsh_hooks(repo_root=repo_root, dry_run=False, is_global=False)
        self.assertEqual(status2, "present")

    def test_install_global_dsh_hooks(self):
        dsh_home = os.path.join(self.tmp, ".dsh")
        profiles_dir = os.path.join(dsh_home, "profiles")
        desktop_dir = os.path.join(profiles_dir, "desktop")
        os.makedirs(desktop_dir)

        status, msg = install_dsh_hooks(target_home=dsh_home, dry_run=False, is_global=True)
        self.assertEqual(status, "installed")

        patch_file = os.path.join(desktop_dir, "cordis.patch.yml")
        self.assertTrue(os.path.isfile(patch_file))
        content = open(patch_file, "r", encoding="utf-8").read()
        self.assertIn("along-hooks-bridge", content)


class TestDshProviderInstall(unittest.TestCase):
    """Tests for DSH skill installation planning and homes."""

    def test_dsh_in_providers(self):
        self.assertIn("dsh", install.PROVIDERS)
        self.assertIn("dsh", install.FOLDER_PROVIDERS)

    def test_homes_default_dsh(self):
        home = tempfile.mkdtemp(prefix="along-home-")
        try:
            homes = install.Homes.defaults(home)
            self.assertEqual(homes.dsh, os.path.join(home, ".dsh"))
            self.assertEqual(homes.provider_home("dsh"), os.path.join(home, ".dsh"))
        finally:
            shutil.rmtree(home, ignore_errors=True)

    def test_dsh_runtime_matrix(self):
        self.assertIn("dsh", runtime.RUNTIME_MATRIX)
        self.assertTrue(runtime.RUNTIME_MATRIX["dsh"]["runtime_hooks"])


if __name__ == "__main__":
    unittest.main()
