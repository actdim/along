#!/usr/bin/env python3
"""
tests/test_hooks_generic.py - Hermetic unit tests for GenericCliAdapter, Cursor hooks, and along run.

Banned characters are constructed with chr() so this test file itself remains clean.
All tests execute in isolated throwaway directories without touching repo state.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import proc
from alongkit.hooks import (
    GateDecision,
    GateResult,
    HookEvent,
    HookEventType,
    get_adapter,
)
from alongkit.hooks.adapters.generic import GenericCliAdapter
from alongkit.hooks.config import (
    get_cursor_hook_manifest,
    install_cursor_hooks,
    purge_local_along_hooks,
)

EM_DASH = chr(0x2014)


class TestGenericCliAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = get_adapter("generic")
        self.assertIsInstance(self.adapter, GenericCliAdapter)

    def test_adapter_resolution_aliases(self):
        for name in ("generic", "cli", "generic-cli", "generic_cli", "cursor", "opencode", "open-code"):
            ad = get_adapter(name)
            self.assertIsInstance(ad, GenericCliAdapter)

    def test_parse_write_tool_json(self):
        raw_payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "write_file",
            "tool_input": {
                "file_path": "src/module.py",
                "content": "def run(): pass\n",
            },
            "cwd": "/workspace/test",
            "session_id": "sess-001",
        })
        event = self.adapter.parse(raw_payload)
        self.assertEqual(event.event_type, HookEventType.PRE_TOOL_USE)
        self.assertEqual(event.tool_name, "write_to_file")
        self.assertEqual(event.tool_args["TargetFile"], "src/module.py")
        self.assertEqual(event.tool_args["CodeContent"], "def run(): pass\n")
        self.assertEqual(event.workspace_root, "/workspace/test")
        self.assertEqual(event.conversation_id, "sess-001")

    def test_parse_edit_tool_json(self):
        raw_payload = json.dumps({
            "hook_event_name": "preToolUse",
            "tool_name": "edit_file",
            "parameters": {
                "path": "src/module.py",
                "replacement": "def run(): return 42\n",
            },
            "cwd": "/workspace/test",
        })
        event = self.adapter.parse(raw_payload)
        self.assertEqual(event.event_type, HookEventType.PRE_TOOL_USE)
        self.assertEqual(event.tool_name, "replace_file_content")
        self.assertEqual(event.tool_args["TargetFile"], "src/module.py")
        self.assertEqual(event.tool_args["ReplacementContent"], "def run(): return 42\n")

    def test_parse_run_command_json(self):
        raw_payload = json.dumps({
            "event_type": "beforeShellExecution",
            "tool": "bash",
            "arguments": {
                "command": "python -m unittest",
            },
            "cwd": "/workspace/test",
        })
        event = self.adapter.parse(raw_payload)
        self.assertEqual(event.event_type, HookEventType.PRE_TOOL_USE)
        self.assertEqual(event.tool_name, "run_command")
        self.assertEqual(event.tool_args["CommandLine"], "python -m unittest")

    def test_parse_plain_string_fallback(self):
        raw_input = "git commit -m \"feat: test\""
        event = self.adapter.parse(raw_input)
        self.assertEqual(event.event_type, HookEventType.PRE_TOOL_USE)
        self.assertEqual(event.tool_name, "run_command")
        self.assertEqual(event.tool_args["CommandLine"], raw_input)

    def test_parse_empty_input_fallback(self):
        event = self.adapter.parse("")
        self.assertEqual(event.tool_name, "")
        self.assertEqual(event.tool_args, {})

    def test_format_allow_and_deny_responses(self):
        allow_res = GateResult(decision=GateDecision.ALLOW)
        code, out = self.adapter.format_response(allow_res)
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

        deny_res = GateResult(decision=GateDecision.DENY, reason="Blocked by gate.")
        code, out = self.adapter.format_response(deny_res)
        self.assertEqual(code, 2)
        self.assertEqual(out, "Blocked by gate.")


class TestAlongRunCliProxy(unittest.TestCase):
    def test_along_run_benign_command_exits_zero(self):
        script_path = os.path.join(SCRIPTS_DIR, "along_exec.py")
        with tempfile.TemporaryDirectory() as tmp:
            along_dir = os.path.join(tmp, ".along")
            os.makedirs(os.path.join(along_dir, "ISSUES"), exist_ok=True)
            res = proc.run_capture(
                [sys.executable, script_path, "run", sys.executable, "-c", "print('proxy-test-ok')"],
                cwd=tmp,
            )
            self.assertEqual(res.returncode, 0)
            self.assertIn("proxy-test-ok", res.stdout)

    def test_along_run_force_push_blocked_in_enforce_mode(self):
        # A force-push is always held by destructive_command; the generic runtime cannot ask.
        # If the gate ever let it through, the push fails harmlessly (no remote).
        script_path = os.path.join(SCRIPTS_DIR, "along_exec.py")
        with tempfile.TemporaryDirectory() as tmp:
            along_dir = os.path.join(tmp, ".along")
            os.makedirs(os.path.join(along_dir, "ISSUES"), exist_ok=True)
            env = dict(os.environ)
            env["ALONG_HOOK_MODE"] = "enforce"
            res = proc.run_capture(
                [sys.executable, script_path, "run", "git push --force"],
                cwd=tmp,
                env=env,
            )
            self.assertEqual(res.returncode, 2)
            self.assertIn("destructive-command", res.stderr)

    def test_along_hook_run_benign_command(self):
        script_path = os.path.join(SCRIPTS_DIR, "along_hook.py")
        with tempfile.TemporaryDirectory() as tmp:
            along_dir = os.path.join(tmp, ".along")
            os.makedirs(os.path.join(along_dir, "ISSUES"), exist_ok=True)
            res = proc.run_capture(
                [sys.executable, script_path, "run", sys.executable, "-c", "print('hook-run-ok')"],
                cwd=tmp,
            )
            self.assertEqual(res.returncode, 0)
            self.assertIn("hook-run-ok", res.stdout)


class TestInstallCursorHooks(unittest.TestCase):
    def test_cursor_manifest_includes_before_submit_prompt(self):
        local_manifest = get_cursor_hook_manifest(is_global=False)
        self.assertIn("beforeSubmitPrompt", local_manifest["hooks"])
        local_cmd = local_manifest["hooks"]["beforeSubmitPrompt"][0]["command"]
        self.assertIn("--runtime cursor", local_cmd)
        self.assertIn("--event UserPromptSubmit", local_cmd)

        global_manifest = get_cursor_hook_manifest(is_global=True)
        self.assertIn("beforeSubmitPrompt", global_manifest["hooks"])
        global_cmd = global_manifest["hooks"]["beforeSubmitPrompt"][0]["command"]
        self.assertIn("along_hook.py", global_cmd)
        self.assertIn("--runtime cursor", global_cmd)
        self.assertIn("--event UserPromptSubmit", global_cmd)
        self.assertNotIn("\\", global_cmd)

    def test_generic_adapter_parses_before_submit_prompt(self):
        adapter = get_adapter("cursor")
        raw = json.dumps({
            "hook_event_name": "beforeSubmitPrompt",
            "prompt": "proceed",
            "workspace_roots": ["/workspace/cursor-test"],
            "conversation_id": "conv-cur-1",
        })
        ev = adapter.parse(raw)
        self.assertEqual(ev.event_type, HookEventType.USER_PROMPT_SUBMIT)
        self.assertEqual(ev.workspace_root, "/workspace/cursor-test")
        self.assertEqual(ev.conversation_id, "conv-cur-1")

    def test_install_cursor_hooks_creates_valid_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, msg = install_cursor_hooks(tmp)
            self.assertEqual(status, "installed")

            hooks_path = os.path.join(tmp, ".cursor", "hooks.json")
            self.assertTrue(os.path.isfile(hooks_path))

            with open(hooks_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.assertEqual(data.get("version"), 1)
            hooks = data.get("hooks", {})
            self.assertIn("preToolUse", hooks)
            self.assertIn("postToolUse", hooks)
            self.assertIn("stop", hooks)
            self.assertIn("beforeSubmitPrompt", hooks)

            pre_hooks = hooks["preToolUse"]
            self.assertTrue(any("along_hook.py" in str(h.get("command")) for h in pre_hooks))
            prompt_hooks = hooks["beforeSubmitPrompt"]
            self.assertTrue(any("--event UserPromptSubmit" in str(h.get("command")) for h in prompt_hooks))

    def test_install_cursor_hooks_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            status1, _ = install_cursor_hooks(tmp)
            self.assertEqual(status1, "installed")

            status2, _ = install_cursor_hooks(tmp)
            self.assertEqual(status2, "present")

            hooks_path = os.path.join(tmp, ".cursor", "hooks.json")
            with open(hooks_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(len(data["hooks"]["beforeSubmitPrompt"]), 1)

    def test_install_cursor_hooks_preserves_custom_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            cursor_dir = os.path.join(tmp, ".cursor")
            os.makedirs(cursor_dir, exist_ok=True)
            hooks_path = os.path.join(cursor_dir, "hooks.json")
            initial = {
                "version": 1,
                "customSetting": "preserved",
                "hooks": {
                    "preToolUse": [
                        {"command": "echo custom-hook"}
                    ],
                    "beforeSubmitPrompt": [
                        {"command": "echo custom-prompt-hook"}
                    ],
                }
            }
            with open(hooks_path, "w", encoding="utf-8") as f:
                json.dump(initial, f)

            status, _ = install_cursor_hooks(tmp)
            self.assertEqual(status, "installed")

            with open(hooks_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.assertEqual(data.get("customSetting"), "preserved")
            pre_hooks = data["hooks"]["preToolUse"]
            # Both custom-hook and along_hook should exist
            self.assertTrue(any("custom-hook" in str(h.get("command")) for h in pre_hooks))
            self.assertTrue(any("along_hook.py" in str(h.get("command")) for h in pre_hooks))
            prompt_hooks = data["hooks"]["beforeSubmitPrompt"]
            self.assertTrue(any("custom-prompt-hook" in str(h.get("command")) for h in prompt_hooks))
            self.assertTrue(any("--event UserPromptSubmit" in str(h.get("command")) for h in prompt_hooks))

            # Purging Along hooks removes all Along events including beforeSubmitPrompt, keeping foreign hooks
            actions = purge_local_along_hooks(tmp, dry_run=False)
            self.assertTrue(actions)
            with open(hooks_path, "r", encoding="utf-8") as f:
                purged = json.load(f)
            self.assertEqual(purged["hooks"]["preToolUse"], [{"command": "echo custom-hook"}])
            self.assertEqual(purged["hooks"]["beforeSubmitPrompt"], [{"command": "echo custom-prompt-hook"}])
            self.assertNotIn("postToolUse", purged["hooks"])
            self.assertNotIn("stop", purged["hooks"])

    def test_install_cursor_hooks_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, _ = install_cursor_hooks(tmp, dry_run=True)
            self.assertEqual(status, "dry-run")
            self.assertFalse(os.path.exists(os.path.join(tmp, ".cursor", "hooks.json")))

    def test_cli_along_hook_install_runtime_cursor(self):
        script_path = os.path.join(SCRIPTS_DIR, "along_hook.py")
        with tempfile.TemporaryDirectory() as tmp:
            res = proc.run_capture(
                [sys.executable, script_path, "install", "--runtime", "cursor", "--repo-root", tmp],
            )
            self.assertEqual(res.returncode, 0)
            self.assertIn("updated", res.stdout)
            self.assertTrue(os.path.isfile(os.path.join(tmp, ".cursor", "hooks.json")))

    def test_cli_along_hook_eval_with_payload_opt(self):
        script_path = os.path.join(SCRIPTS_DIR, "along_hook.py")
        with tempfile.TemporaryDirectory() as tmp:
            payload = json.dumps({"tool_name": "run_command", "tool_args": {"CommandLine": "dir"}})
            res = proc.run_capture(
                [sys.executable, script_path, "eval", "PreToolUse", "--payload", payload, "--repo-root", tmp],
            )
            self.assertEqual(res.returncode, 0)

    def test_cli_along_hook_eval_with_positional_payload_denied(self):
        script_path = os.path.join(SCRIPTS_DIR, "along_hook.py")
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, ".along", "ISSUES"), exist_ok=True)
            payload = json.dumps({"tool_name": "run_command", "tool_args": {"CommandLine": "git commit -m \"feat: bad message\""}})
            res = proc.run_capture(
                [sys.executable, script_path, "eval", "PreToolUse", payload, "--repo-root", tmp],
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("commit-issue-binding", res.stderr + res.stdout)

    def test_cli_along_hook_eval_stdin_pipe(self):
        script_path = os.path.join(SCRIPTS_DIR, "along_hook.py")
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, ".along", "ISSUES"), exist_ok=True)
            payload = json.dumps({"tool_name": "run_command", "tool_args": {"CommandLine": "dir"}})
            res = proc.run_capture(
                [sys.executable, script_path, "eval", "PreToolUse", "--repo-root", tmp],
                stdin_text=payload,
            )
            self.assertEqual(res.returncode, 0)


if __name__ == "__main__":
    unittest.main()
