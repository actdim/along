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

    def test_opencode_read_only_and_non_read_only_tools_have_no_unmapped_marker(self):
        from alongkit.hooks.adapters import generic, normalize

        for tool_name in ("read", "glob", "grep", "webfetch", "list", "skill", "task", "todowrite"):
            payload = json.dumps({
                "tool": tool_name,
                "args": {"path": "README.md"},
                "sessionID": "ses-opencode-106",
            })
            ev = self.adapter.parse(payload, event_type=HookEventType.PRE_TOOL_USE)
            norm = normalize.fail_closed(ev)
            self.assertNotIn(
                normalize.UNMAPPED_MARKER,
                norm.tool_args,
                f"OpenCode tool '{tool_name}' should not produce unmapped_tool",
            )
            if tool_name in generic.READ_ONLY_TOOLS:
                self.assertIn(norm.tool_name, normalize.READ_TOOLS + normalize.SEARCH_TOOLS)
        tw_ev = normalize.fail_closed(
            self.adapter.parse(
                json.dumps({"tool": "todowrite", "args": {}, "sessionID": "ses-opencode-107"}),
                event_type=HookEventType.PRE_TOOL_USE,
            )
        )
        self.assertEqual(tw_ev.tool_name, "write_to_file")


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

    def test_doctor_and_enforcement_require_valid_hooks_and_lifecycle_heartbeat(self):
        repo_dir = os.path.join(self.tmp_home, "repo")
        os.makedirs(os.path.join(repo_dir, ".along"), exist_ok=True)
        plugin_dir = os.path.join(self.tmp_home, ".config", "opencode", "plugins")
        os.makedirs(plugin_dir, exist_ok=True)
        plugin_path = os.path.join(plugin_dir, "along-gates.js")

        with mock.patch.dict(os.environ, {"HOME": self.tmp_home, "USERPROFILE": self.tmp_home}):
            # 1. setup-only / dead-hook plugin -> advisory
            with open(plugin_path, "w", encoding="utf-8") as handle:
                handle.write('export default { id: "along-gates", async setup(ctx) { ctx.session.hook("idle", () => {}); } };\n')
            self.assertFalse(runtime.along_hooks_registered("opencode", repo_dir))
            level, why = runtime.enforcement_level("opencode", repo_dir)
            self.assertEqual(level, runtime.ADVISORY)
            self.assertIn("contract validation", why)

            # 2. Valid plugin without lifecycle heartbeat -> advisory
            install_opencode_hooks(is_global=True, target_home=os.path.join(self.tmp_home, ".config", "opencode"))
            self.assertTrue(runtime.along_hooks_registered("opencode", repo_dir))
            runtime.record_heartbeat(repo_dir, "opencode", "2026-11-24T22:00:00Z", event_name="PreToolUse")
            level, why = runtime.enforcement_level("opencode", repo_dir)
            self.assertEqual(level, runtime.ADVISORY)
            self.assertIn("no lifecycle heartbeat", why)

            # 3. Valid plugin + lifecycle heartbeat -> mechanical
            runtime.record_heartbeat(repo_dir, "opencode", "2026-11-24T22:01:00Z", event_name="Stop")
            level, why = runtime.enforcement_level("opencode", repo_dir)
            self.assertEqual(level, runtime.MECHANICAL)

            # 4. Duplicate project copy -> audit reports duplicate_paths
            proj_plugin_dir = os.path.join(repo_dir, ".opencode", "plugins")
            os.makedirs(proj_plugin_dir, exist_ok=True)
            with open(os.path.join(proj_plugin_dir, "along-gates.js"), "w", encoding="utf-8") as handle:
                handle.write('export default { id: "along-gates", async setup(ctx) {} };\n')
            audit = runtime.opencode_plugin_audit(repo_dir)
            self.assertEqual(len(audit["duplicate_paths"]), 2)
            self.assertEqual(len(audit["stale_paths"]), 1)

            # 5. Global install prunes stale project plugin
            status_prune, msg_prune = install_opencode_hooks(
                repo_root=repo_dir,
                is_global=True,
                target_home=os.path.join(self.tmp_home, ".config", "opencode"),
            )
            self.assertEqual(status_prune, "present")
            self.assertIn("pruned", msg_prune)
            self.assertFalse(os.path.exists(os.path.join(proj_plugin_dir, "along-gates.js")))

            # 6. Installer refuses plugin with unsupported hook name
            real_read = textio.read_text
            bad_js = 'export default { id: "along-gates", async setup(ctx) { await ctx.session.hook("bogus", () => {}); } };\n'
            src_plugin = os.path.join(REPO_ROOT, "scripts", "alongkit", "hooks", "opencode_plugin.js")
            with mock.patch("alongkit.textio.read_text", side_effect=lambda p, **kw: bad_js if p == src_plugin else real_read(p, **kw)):
                status_bad, msg_bad = install_opencode_hooks(
                    is_global=True,
                    target_home=os.path.join(self.tmp_home, ".config", "opencode"),
                )
                self.assertEqual(status_bad, "failed")
                self.assertIn("session.bogus", msg_bad)

    def test_issue_find_lint_and_doctor_entities_plan_status(self):
        import io
        from contextlib import redirect_stdout
        import hermetic
        from alongkit.commands.issue import _issue_find

        repo_dir = hermetic.make_repo_fixture(prefix="along-test-ac-")
        try:
            issues_dir = os.path.join(repo_dir, ".along", "ISSUES")
            os.makedirs(issues_dir, exist_ok=True)
            # Legacy issue without title: front matter, only H1
            legacy_path = os.path.join(issues_dir, "bug--legacy-h1.md")
            with open(legacy_path, "w", encoding="utf-8") as handle:
                handle.write(
                    "---\nprotocol: along\nprotocol_version: '4.9.1'\nslug: legacy-h1\n"
                    "type: bug\nstatus: open\npriority: low\ncreated: 2026-11-24\n"
                    "plan_status: approved\n---\n\n# Legacy H1 Title\n\n## Problem\nx\n\n## Acceptance Criteria\n- [ ] y\n"
                )
            plan_dir = os.path.join(issues_dir, "bug--legacy-h1")
            os.makedirs(plan_dir, exist_ok=True)
            with open(os.path.join(plan_dir, "plan.md"), "w", encoding="utf-8") as handle:
                handle.write("# Plan\nStatus: proposed\n")
            with open(os.path.join(repo_dir, ".along", "ISSUES.md"), "w", encoding="utf-8") as handle:
                handle.write("# Active Issues\n\n- [ ] `(bug)` [legacy-h1](ISSUES/bug--legacy-h1.md)\n")

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _issue_find(repo_dir, ["find", "legacy-h1", "--json"])
            self.assertEqual(rc, 0)
            found = json.loads(buf.getvalue())
            self.assertEqual(found[0]["title"], "Legacy H1 Title")

            lint_res = entities.lint_issues(repo_dir)
            self.assertFalse(lint_res["clean"])
            self.assertTrue(any("Status: proposed" in str(f["missing"]) for f in lint_res["findings"]))

            val_res = entities.validate_entities(repo_dir)
            self.assertTrue(any("projection plan note mismatch" in w[1] for w in val_res["warnings"]))
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)

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
    def test_contract_loader_finds_2_3_2_fixture(self):
        contract = runtime.load_opencode_contract(REPO_ROOT)
        self.assertEqual(contract["version"], "2.3.2")
        self.assertEqual(contract["min_supported_version"], runtime.OPENCODE_MIN_VERSION)
        self.assertEqual(contract, runtime.OPENCODE_CONTRACT)
        self.assertIn("experimental.idle", contract["session_hooks"])
        self.assertNotIn("idle", contract["session_hooks"])
        self.assertNotIn("stop", contract["session_hooks"])
        self.assertNotIn("--dir", contract["run_flags"])

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
            "const pyBin = process.argv[2];\n"
            "const mod = await import(pathToFileURL(pluginUrl).href);\n\n"
            "assert.ok(mod.default, 'Must export default definition');\n"
            "assert.strictEqual(mod.default.id, 'along-gates', 'Plugin id must be along-gates');\n"
            "assert.strictEqual(typeof mod.default.setup, 'function', 'Must export setup function');\n"
            "assert.strictEqual(mod.AlongPlugin, undefined, 'V1 AlongPlugin export must be dropped');\n\n"
            "const testTmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'opencode-contract-'));\n"
            "try {\n"
            "  const scriptsDir = path.join(testTmpDir, 'scripts');\n"
            "  fs.mkdirSync(scriptsDir, { recursive: true });\n"
            "  const logFile = path.join(testTmpDir, 'hook_calls.jsonl');\n"
            "  const fakeHook = [\n"
            "    'import json, sys',\n"
            "    'raw = sys.stdin.read()',\n"
            "    'data = json.loads(raw) if raw else {}',\n"
            "    `with open(${JSON.stringify(logFile)}, 'a', encoding='utf-8') as f:`,\n"
            "    `    f.write(json.dumps(data) + '\\\\n')`,\n"
            "  ].join('\\n');\n"
            "  fs.writeFileSync(path.join(scriptsDir, 'along_hook.py'), fakeHook, 'utf8');\n"
            "  process.env.ALONG_PYTHON = pyBin;\n\n"
            "  const registered = [];\n"
            "  const handlers = {};\n"
            "  const makeCtx = () => ({\n"
            "    location: { directory: testTmpDir },\n"
            "    tool: { hook: async (n, fn) => { registered.push('tool.' + n); handlers['tool.' + n] = fn; } },\n"
            "    session: { hook: async (n, fn) => { registered.push('session.' + n); handlers['session.' + n] = fn; } },\n"
            "    shell: { hook: async (n, fn) => { registered.push('shell.' + n); handlers['shell.' + n] = fn; } },\n"
            "    event: { subscribe: () => { registered.push('event.subscribe'); } }\n"
            "  });\n"
            "  const mockCtx = makeCtx();\n\n"
            "  await mod.default.setup(mockCtx);\n"
            "  // Calling setup again with same ctx is a no-op\n"
            "  await mod.default.setup(mockCtx);\n"
            "  assert.strictEqual(registered.filter(x => x === 'session.experimental.idle').length, 1, 'setup must be idempotent for same ctx');\n\n"
            "  // Calling setup with a new ctx from same module URL (reload) re-registers\n"
            "  await mod.default.setup(makeCtx());\n"
            "  assert.strictEqual(registered.filter(x => x === 'session.experimental.idle').length, 2, 'reload with new ctx must re-register');\n\n"
            "  assert.ok(registered.includes('tool.execute.before'), 'Missing tool.execute.before');\n"
            "  assert.ok(registered.includes('tool.execute.after'), 'Missing tool.execute.after');\n"
            "  assert.ok(registered.includes('session.experimental.idle'), 'Missing session.experimental.idle');\n"
            "  assert.ok(registered.includes('session.prompt'), 'Missing session.prompt');\n"
            "  assert.ok(registered.includes('shell.create.before'), 'Missing shell.create.before');\n"
            "  assert.ok(!registered.includes('session.idle'), 'Dead session.idle must not be registered');\n"
            "  assert.ok(!registered.includes('session.stop'), 'Dead session.stop must not be registered');\n"
            "  assert.ok(!registered.includes('shell.env'), 'Dead shell.env must not be registered');\n"
            "  assert.ok(!registered.includes('event.subscribe'), 'Dead event.subscribe must not be called');\n\n"
            "  // Background idle must be skipped\n"
            "  await handlers['session.experimental.idle']({ sessionID: 'ses_real_123', background: true });\n"
            "  // Foreground idle triggers Stop once\n"
            "  await handlers['session.experimental.idle']({ sessionID: 'ses_real_123', background: false });\n"
            "  // Duplicate idle for same session without new activity is deduped\n"
            "  await handlers['session.experimental.idle']({ sessionID: 'ses_real_123', background: false });\n"
            "  // New prompt resets dedupe, then next idle triggers Stop again\n"
            "  await handlers['session.prompt']({ sessionID: 'ses_real_123', prompt: 'hello' });\n"
            "  await handlers['session.experimental.idle']({ sessionID: 'ses_real_123' });\n"
            "  // Missing optional fields must not throw\n"
            "  await handlers['session.experimental.idle']({});\n"
            "  await handlers['session.prompt']({});\n\n"
            "  const v2Event = { command: 'git status', cwd: testTmpDir, env: {} };\n"
            "  await handlers['shell.create.before'](v2Event);\n"
            "  assert.strictEqual(v2Event.env.OPENCODE_SESSION_ID, 'ses_real_123');\n\n"
            "  const calls = fs.readFileSync(logFile, 'utf8').trim().split('\\n').map(l => JSON.parse(l));\n"
            "  const stopCalls = calls.filter(c => c.hook_event_name === 'Stop');\n"
            "  assert.strictEqual(stopCalls.length, 2, 'Expected 2 ses_real_123 Stop calls (deduped empty payload)');\n"
            "  assert.strictEqual(stopCalls[0].session_id, 'ses_real_123');\n"
            "  assert.strictEqual(stopCalls[1].session_id, 'ses_real_123');\n\n"
            "  console.log('NODE_CONTRACT_OK');\n"
            "} finally {\n"
            "  try {\n"
            "    fs.rmSync(testTmpDir, { recursive: true, force: true });\n"
            "  } catch (_) {}\n"
            "}\n"
        )

        res = subprocess.run(
            [node_bin, "--input-type=module", "-e", eval_script, plugin_src, sys.executable],
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
