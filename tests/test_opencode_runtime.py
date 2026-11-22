#!/usr/bin/env python3
"""
tests/test_opencode_runtime.py - Unit tests for OpenCode runtime hook integration.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
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

from alongkit import entities, runtime, session, textio
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

    def test_parse_edit_tool_camel_case(self):
        payload = json.dumps({
            "tool": "edit",
            "args": {
                "filePath": "src/app.py",
                "oldString": "def old():",
                "newString": "def new():",
                "replaceAll": False
            },
            "sessionID": "ses-opencode-104",
        })
        event = self.adapter.parse(payload, event_type=HookEventType.PRE_TOOL_USE)
        self.assertEqual(event.tool_name, "replace_file_content")
        self.assertEqual(event.tool_args.get("TargetFile"), "src/app.py")
        self.assertEqual(event.tool_args.get("ReplacementContent"), "def new():")
        self.assertEqual(event.tool_args.get("OldString"), "def old():")
        self.assertEqual(event.tool_args.get("Target"), "def old():")

    def test_parse_execute_code_tool(self):
        payload = json.dumps({
            "tool": "execute",
            "args": {"code": "pytest -q tests/test_core.py"},
            "sessionID": "ses-opencode-105",
        })
        event = self.adapter.parse(payload, event_type=HookEventType.PRE_TOOL_USE)
        self.assertEqual(event.tool_name, "run_command")
        self.assertEqual(event.tool_args.get("CommandLine"), "pytest -q tests/test_core.py")


class TestOpenCodeSessionAndDetection(unittest.TestCase):
    def test_detect_agent_from_session_id(self):
        with mock.patch.dict(os.environ, {"OPENCODE_SESSION_ID": "opencode-session-123"}, clear=True):
            self.assertEqual(entities.detect_agent(), "opencode")

    def test_detect_agent_ignores_boolean_agent_flag(self):
        with mock.patch.dict(os.environ, {"AGENT": "1", "OPENCODE_SESSION_ID": "ses-123"}, clear=True):
            self.assertEqual(entities.detect_agent(), "opencode")

    def test_detect_agent_ignores_boolean_agent_flag_without_markers(self):
        with mock.patch.dict(os.environ, {"AGENT": "1"}, clear=True):
            self.assertEqual(entities.detect_agent(), "unknown")

    def test_detect_agent_accepts_valid_agent_string(self):
        with mock.patch.dict(os.environ, {"AGENT": "custom-bot"}, clear=True):
            self.assertEqual(entities.detect_agent(), "custom-bot")

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

    def test_install_idempotency_with_crlf(self):
        target_home = os.path.join(self.tmp_home, ".config", "opencode")
        status, _ = install_opencode_hooks(is_global=True, target_home=target_home)
        self.assertEqual(status, "installed")

        # Simulate CRLF line endings on disk in target file
        plugin_path = os.path.join(target_home, "plugins", "along-gates.js")
        content = textio.read_text(plugin_path, strict=False)
        with open(plugin_path, "wb") as handle:
            handle.write(content.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))

        status_repeat, _ = install_opencode_hooks(is_global=True, target_home=target_home)
        self.assertEqual(status_repeat, "present")

        # Simulate CRLF line endings in source template
        src_plugin = os.path.join(REPO_ROOT, "scripts", "alongkit", "hooks", "opencode_plugin.js")
        crlf_content = content.replace("\r\n", "\n").replace("\n", "\r\n")
        real_read_text = textio.read_text
        with mock.patch("alongkit.textio.read_text", side_effect=lambda path, **kw: crlf_content if path == src_plugin else real_read_text(path, **kw)):
            status_crlf_template, _ = install_opencode_hooks(is_global=True, target_home=target_home)
            self.assertEqual(status_crlf_template, "present")


class TestOpenCodeNodePluginContract(unittest.TestCase):
    def test_node_plugin_module_contract(self):
        node_bin = shutil.which("node")
        if not node_bin:
            self.skipTest("node binary not found on PATH")

        plugin_src = os.path.join(REPO_ROOT, "scripts", "alongkit", "hooks", "opencode_plugin.js")
        self.assertTrue(os.path.isfile(plugin_src))

        eval_script = (
            "import { pathToFileURL } from 'node:url';\n"
            "import fs from 'node:fs';\n"
            "import os from 'node:os';\n"
            "import path from 'node:path';\n"
            "import assert from 'node:assert';\n\n"
            "const pluginUrl = process.argv[1];\n"
            "const mod = await import(pathToFileURL(pluginUrl).href);\n\n"
            "assert.ok(mod.default, 'Must export default definition');\n"
            "assert.strictEqual(mod.default.id, 'along-gates', 'Plugin id must be along-gates');\n"
            "assert.strictEqual(typeof mod.default.setup, 'function', 'Must export setup function');\n"
            "assert.strictEqual(typeof mod.AlongPlugin, 'function', 'Must export AlongPlugin function');\n\n"
            "const testTmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'opencode-contract-'));\n"
            "try {\n"
            "  const registered = [];\n"
            "  const handlers = {};\n"
            "  const mockCtx = {\n"
            "    location: { directory: testTmpDir },\n"
            "    tool: { hook: async (n, fn) => { registered.push('tool.' + n); handlers['tool.' + n] = fn; } },\n"
            "    session: { hook: async (n, fn) => { registered.push('session.' + n); handlers['session.' + n] = fn; } },\n"
            "    shell: { hook: async (n, fn) => { registered.push('shell.' + n); handlers['shell.' + n] = fn; } },\n"
            "    event: { subscribe: (fn) => { registered.push('event.subscribe'); handlers['event.subscribe'] = fn; } }\n"
            "  };\n\n"
            "  await mod.default.setup(mockCtx);\n"
            "  assert.ok(registered.includes('tool.execute.before'), 'Missing tool.execute.before');\n"
            "  assert.ok(registered.includes('tool.execute.after'), 'Missing tool.execute.after');\n"
            "  assert.ok(registered.includes('session.idle'), 'Missing session.idle');\n"
            "  assert.ok(registered.includes('session.stop'), 'Missing session.stop');\n"
            "  assert.ok(registered.includes('session.prompt'), 'Missing session.prompt');\n"
            "  assert.ok(registered.includes('shell.env'), 'Missing shell.env');\n"
            "  assert.ok(registered.includes('shell.create.before'), 'Missing shell.create.before');\n"
            "  assert.ok(registered.includes('event.subscribe'), 'Missing event.subscribe');\n\n"
            "  // Invoke shell.create.before with single argument (V2 contract, output is undefined)\n"
            "  const v2Event = { command: 'git status', cwd: testTmpDir, env: {} };\n"
            "  await handlers['shell.create.before'](v2Event);\n"
            "  // In V2, event.env should be populated if sid resolved\n"
            "  assert.ok(v2Event.env !== undefined);\n\n"
            "  // Invoke shell.env with V1 contract (input, output)\n"
            "  const v1Output = { env: {} };\n"
            "  await handlers['shell.env']({ cwd: testTmpDir }, v1Output);\n\n"
            "  // Invoke session lifecycle handlers defensively without throwing\n"
            "  await handlers['session.idle']({ sessionID: 'ses-1' });\n"
            "  await handlers['session.stop']({ sessionID: 'ses-1' });\n"
            "  await handlers['session.prompt']({ prompt: 'test prompt' });\n"
            "  await handlers['event.subscribe']({ type: 'session.idle' });\n\n"
            "  console.log('NODE_CONTRACT_OK');\n"
            "} finally {\n"
            "  try {\n"
            "    fs.rmSync(testTmpDir, { recursive: true, force: true });\n"
            "  } catch (_) {}\n"
            "}\n"
        )

        res = subprocess.run(
            [node_bin, "--input-type=module", "-e", eval_script, plugin_src],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 0, f"Node contract failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        self.assertIn("NODE_CONTRACT_OK", res.stdout)


    def test_opencode_plugin_windows_hide(self):
        plugin_src = os.path.join(REPO_ROOT, "scripts", "alongkit", "hooks", "opencode_plugin.js")
        content = textio.read_text(plugin_src, strict=False)
        self.assertIn("windowsHide: true", content, "opencode_plugin.js MUST specify windowsHide: true for spawnSync")

    def test_proc_windows_no_window_flag(self):
        from alongkit import proc
        if os.name == "nt":
            kw = proc.spawn_group_kwargs()
            flag = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            self.assertTrue(bool(kw.get("creationflags", 0) & flag), "spawn_group_kwargs MUST include CREATE_NO_WINDOW on Windows")


if __name__ == "__main__":
    unittest.main()
