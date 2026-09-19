#!/usr/bin/env python3
"""
tests/test_hooks_codex.py - Hermetic unit tests for OpenAI Codex hook adapter and installer.

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

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import proc, session

from alongkit.hooks import (
    GateDecision,
    GateResult,
    HookEvent,
    HookEventType,
    get_adapter,
)
from alongkit.hooks.adapters.codex import CodexAdapter
from alongkit.hooks.config import (
    get_codex_hook_manifest,
    install_codex_hooks,
)

EM_DASH = chr(0x2014)


class TestCodexAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = get_adapter("codex")
        self.assertIsInstance(self.adapter, CodexAdapter)

    def test_adapter_resolution(self):
        self.assertIsInstance(get_adapter("codex"), CodexAdapter)
        self.assertIsInstance(get_adapter("openaicodex"), CodexAdapter)
        self.assertIsInstance(get_adapter("openai-codex"), CodexAdapter)

    def test_parse_write_file_and_create_file(self):
        # Case 1: write_file with file_path and content
        payload1 = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "write_file",
            "tool_input": {
                "file_path": "src/main.py",
                "content": "def main(): pass\n",
            },
            "cwd": "/workspace/repo",
            "session_id": "session-123",
        })
        event1 = self.adapter.parse(payload1)
        self.assertEqual(event1.event_type, HookEventType.PRE_TOOL_USE)
        self.assertEqual(event1.tool_name, "write_to_file")
        self.assertEqual(event1.tool_args["TargetFile"], "src/main.py")
        self.assertEqual(event1.tool_args["CodeContent"], "def main(): pass\n")
        self.assertEqual(event1.workspace_root, "/workspace/repo")
        self.assertEqual(event1.conversation_id, "session-123")
        self.assertEqual(event1.runtime, "codex")

        # Case 2: create_file with path and text
        payload2 = json.dumps({
            "tool_name": "create_file",
            "parameters": {
                "path": "src/new.py",
                "text": "x = 42\n",
            },
        })
        event2 = self.adapter.parse(payload2)
        self.assertEqual(event2.tool_name, "write_to_file")
        self.assertEqual(event2.tool_args["TargetFile"], "src/new.py")
        self.assertEqual(event2.tool_args["CodeContent"], "x = 42\n")

    def test_parse_edit_file_and_patch(self):
        # Case 1: edit_file with old_string and new_string
        payload1 = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "edit_file",
            "tool_input": {
                "file_path": "src/utils.py",
                "old_string": "x = 1",
                "new_string": "x = 2",
            },
        })
        event1 = self.adapter.parse(payload1)
        self.assertEqual(event1.event_type, HookEventType.PRE_TOOL_USE)
        self.assertEqual(event1.tool_name, "replace_file_content")
        self.assertEqual(event1.tool_args["TargetFile"], "src/utils.py")
        self.assertEqual(event1.tool_args["ReplacementContent"], "x = 2")
        self.assertEqual(event1.tool_args["content"], "x = 2")
        self.assertEqual(event1.tool_args["old_string"], "x = 1")

        # Case 2: patch with old_string and replacement
        payload2 = json.dumps({
            "tool_name": "patch",
            "arguments": {
                "path": "src/patch.py",
                "old_string": "foo",
                "replacement": "bar",
            },
        })
        event2 = self.adapter.parse(payload2)
        self.assertEqual(event2.tool_name, "replace_file_content")
        self.assertEqual(event2.tool_args["TargetFile"], "src/patch.py")
        self.assertEqual(event2.tool_args["ReplacementContent"], "bar")
        self.assertEqual(event2.tool_args["content"], "bar")
        self.assertEqual(event2.tool_args["old_string"], "foo")

        # Case 3: edit_file with new_content
        payload3 = json.dumps({
            "tool_name": "edit_file",
            "args": {
                "filePath": "src/config.py",
                "old_string": "old",
                "new_content": "updated",
            },
        })
        event3 = self.adapter.parse(payload3)
        self.assertEqual(event3.tool_name, "replace_file_content")
        self.assertEqual(event3.tool_args["TargetFile"], "src/config.py")
        self.assertEqual(event3.tool_args["ReplacementContent"], "updated")
        self.assertEqual(event3.tool_args["content"], "updated")
        self.assertEqual(event3.tool_args["old_string"], "old")

    def test_parse_shell_exec_bash(self):
        # Case 1: shell with command
        payload1 = json.dumps({
            "tool_name": "shell",
            "tool_input": {
                "command": "git status",
            },
        })
        event1 = self.adapter.parse(payload1)
        self.assertEqual(event1.tool_name, "run_command")
        self.assertEqual(event1.tool_args["CommandLine"], "git status")

        # Case 2: exec with cmd
        payload2 = json.dumps({
            "tool_name": "exec",
            "parameters": {
                "cmd": "pytest -q",
            },
        })
        event2 = self.adapter.parse(payload2)
        self.assertEqual(event2.tool_name, "run_command")
        self.assertEqual(event2.tool_args["CommandLine"], "pytest -q")

        # Case 3: bash with command
        payload3 = json.dumps({
            "tool_name": "bash",
            "arguments": {
                "command": "echo test",
            },
        })
        event3 = self.adapter.parse(payload3)
        self.assertEqual(event3.tool_name, "run_command")
        self.assertEqual(event3.tool_args["CommandLine"], "echo test")

    def test_parse_stop_event(self):
        payload = json.dumps({
            "hook_event_name": "Stop",
            "cwd": "/workspace/repo",
            "session_id": "session-stop",
        })
        event = self.adapter.parse(payload)
        self.assertEqual(event.event_type, HookEventType.STOP)
        self.assertEqual(event.workspace_root, "/workspace/repo")
        self.assertEqual(event.conversation_id, "session-stop")

    def test_parse_stringified_json_arguments(self):
        # Case 1: stringified JSON in arguments
        payload1 = json.dumps({
            "tool_name": "write_file",
            "arguments": json.dumps({
                "file_path": "str_args.py",
                "content": "val = 1\n",
            }),
        })
        event1 = self.adapter.parse(payload1)
        self.assertEqual(event1.tool_name, "write_to_file")
        self.assertEqual(event1.tool_args["TargetFile"], "str_args.py")
        self.assertEqual(event1.tool_args["CodeContent"], "val = 1\n")

        # Case 2: stringified JSON in tool_input inside tool_call
        payload2 = json.dumps({
            "tool_call": {
                "name": "edit_file",
                "tool_input": json.dumps({
                    "file_path": "edit_str.py",
                    "old_string": "x",
                    "new_string": "y",
                }),
            }
        })
        event2 = self.adapter.parse(payload2)
        self.assertEqual(event2.tool_name, "replace_file_content")
        self.assertEqual(event2.tool_args["TargetFile"], "edit_str.py")
        self.assertEqual(event2.tool_args["ReplacementContent"], "y")
        self.assertEqual(event2.tool_args["old_string"], "x")

    def test_parse_empty_and_malformed_json_payloads(self):
        # Empty string
        event1 = self.adapter.parse("")
        self.assertEqual(event1.event_type, HookEventType.PRE_TOOL_USE)
        self.assertEqual(event1.tool_name, "")
        self.assertEqual(event1.tool_args, {})

        # Whitespace only
        event2 = self.adapter.parse("   \n\t ")
        self.assertEqual(event2.tool_name, "")

        # Malformed JSON
        event3 = self.adapter.parse("{not valid json: true,")
        self.assertEqual(event3.tool_name, "")
        self.assertEqual(event3.tool_args, {})

        # Non-dict JSON (e.g. list, integer, string)
        event4 = self.adapter.parse("[1, 2, 3]")
        self.assertEqual(event4.tool_name, "")
        self.assertEqual(event4.tool_args, {})

        # Stringified arguments that are malformed JSON
        payload5 = json.dumps({
            "tool_name": "write_file",
            "arguments": "not-valid-json",
        })
        event5 = self.adapter.parse(payload5)
        self.assertEqual(event5.tool_name, "write_to_file")
        self.assertEqual(event5.tool_args, {})

    def test_format_response_allow(self):
        result = GateResult(decision=GateDecision.ALLOW)
        code, output_str = self.adapter.format_response(result)
        self.assertEqual(code, 0)
        self.assertEqual(output_str, "")

    def test_format_response_deny(self):
        result = GateResult(decision=GateDecision.DENY, reason="Typography violation detected.")
        code, output_str = self.adapter.format_response(result)
        self.assertEqual(code, 2)
        self.assertEqual(output_str, "Typography violation detected.")

        # Default fallback reason when reason is empty
        result_no_reason = GateResult(decision=GateDecision.DENY, reason="")
        code2, output_str2 = self.adapter.format_response(result_no_reason)
        self.assertEqual(code2, 2)
        self.assertTrue(len(output_str2) > 0)


class TestCodexEndToEnd(unittest.TestCase):
    def test_cli_invocation_clean_payload_exits_zero(self):
        script_path = os.path.join(SCRIPTS_DIR, "along_hook.py")
        input_payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "write_file",
            "tool_input": {
                "file_path": "src/clean.py",
                "content": "val = 'clean ascii'\n",
            },
        })

        with tempfile.TemporaryDirectory() as tmp:
            along_dir = os.path.join(tmp, ".along")
            os.makedirs(along_dir, exist_ok=True)
            session.approve_plan(tmp)
            res = proc.run_capture(
                [sys.executable, script_path, "--runtime", "codex", "--event", "PreToolUse", "--repo-root", tmp],
                stdin_text=input_payload,
            )

            self.assertEqual(res.returncode, 0)
            self.assertEqual(res.stdout.strip(), "")
            clean_stderr = "\n".join(
                line for line in res.stderr.splitlines()
                if not line.startswith("-> [Along] resolving dependencies")
            ).strip()
            self.assertEqual(clean_stderr, "")

    def test_cli_invocation_write_file_typography_violation_exits_two(self):
        script_path = os.path.join(SCRIPTS_DIR, "along_hook.py")
        bad_text = f"val = 'hello {EM_DASH} world'\n"
        input_payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "write_file",
            "tool_input": {
                "file_path": "src/bad.py",
                "content": bad_text,
            },
        })

        with tempfile.TemporaryDirectory() as tmp:
            along_dir = os.path.join(tmp, ".along")
            os.makedirs(along_dir, exist_ok=True)
            res = proc.run_capture(
                [sys.executable, script_path, "--runtime", "codex", "--event", "PreToolUse", "--repo-root", tmp],
                stdin_text=input_payload,
            )
            self.assertEqual(res.returncode, 2)
            self.assertEqual(res.stdout.strip(), "")
            self.assertIn("Typography", res.stderr)
            self.assertIn("em dash", res.stderr)

    def test_cli_invocation_edit_file_typography_violation_exits_two(self):
        script_path = os.path.join(SCRIPTS_DIR, "along_hook.py")
        bad_text = f"val = 'bad {EM_DASH} replace'\n"
        input_payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "edit_file",
            "tool_input": {
                "file_path": "src/bad_edit.py",
                "old_string": "val = 'old'\n",
                "new_string": bad_text,
            },
        })

        with tempfile.TemporaryDirectory() as tmp:
            along_dir = os.path.join(tmp, ".along")
            os.makedirs(along_dir, exist_ok=True)
            res = proc.run_capture(
                [sys.executable, script_path, "--runtime", "codex", "--event", "PreToolUse", "--repo-root", tmp],
                stdin_text=input_payload,
            )
            self.assertEqual(res.returncode, 2)
            self.assertIn("Typography", res.stderr)

    def test_cli_invocation_cli_safety_heredoc_exits_two(self):
        script_path = os.path.join(SCRIPTS_DIR, "along_hook.py")
        input_payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "shell",
            "tool_input": {
                "command": "cat <<EOF > test.py\nx = 1\nEOF",
            },
        })

        with tempfile.TemporaryDirectory() as tmp:
            along_dir = os.path.join(tmp, ".along")
            os.makedirs(along_dir, exist_ok=True)
            res = proc.run_capture(
                [
                    sys.executable,
                    script_path,
                    "--runtime",
                    "codex",
                    "--event",
                    "PreToolUse",
                    "--mode",
                    "enforce",
                    "--repo-root",
                    tmp,
                ],
                stdin_text=input_payload,
            )
            self.assertEqual(res.returncode, 2)
            self.assertIn("Heredoc", res.stderr)


class TestInstallCodexHooks(unittest.TestCase):
    def test_clean_install_creates_hooks_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, msg = install_codex_hooks(tmp)
            self.assertEqual(status, "installed")
            target = os.path.join(tmp, ".codex", "hooks.json")
            self.assertTrue(os.path.isfile(target))
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("hooks", data)
            self.assertIn("PreToolUse", data["hooks"])
            self.assertIn("PostToolUse", data["hooks"])
            self.assertIn("Stop", data["hooks"])

            # Idempotency check
            status2, _ = install_codex_hooks(tmp)
            self.assertEqual(status2, "present")

    def test_existing_third_party_hooks_and_keys_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_dir = os.path.join(tmp, ".codex")
            os.makedirs(codex_dir, exist_ok=True)
            target = os.path.join(codex_dir, "hooks.json")
            initial_data = {
                "custom_engine": "gpt-4",
                "custom_settings": {"timeout": 30},
                "hooks": {
                    "PreToolUse": [
                        {"matcher": "custom_tool", "command": "echo custom"}
                    ]
                },
            }
            with open(target, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, indent=2)

            status, _ = install_codex_hooks(tmp)
            self.assertEqual(status, "installed")
            with open(target, "r", encoding="utf-8") as f:
                updated_data = json.load(f)

            self.assertEqual(updated_data["custom_engine"], "gpt-4")
            self.assertEqual(updated_data["custom_settings"]["timeout"], 30)
            # Third-party custom hook must still exist
            pre_hooks = updated_data["hooks"]["PreToolUse"]
            self.assertTrue(any(h.get("command") == "echo custom" for h in pre_hooks))
            self.assertTrue(any("along_hook.py" in h.get("command", "") for h in pre_hooks))

    def test_dry_run_does_not_mutate_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, _ = install_codex_hooks(tmp, dry_run=True)
            self.assertEqual(status, "dry-run")
            target = os.path.join(tmp, ".codex", "hooks.json")
            self.assertFalse(os.path.exists(target))

    def test_cli_install_subcommand_with_runtime_codex(self):
        script_path = os.path.join(SCRIPTS_DIR, "along_hook.py")
        with tempfile.TemporaryDirectory() as tmp:
            res = proc.run_capture(
                [sys.executable, script_path, "install", "--runtime", "codex", "--repo-root", tmp],
            )
            self.assertEqual(res.returncode, 0)
            self.assertIn("updated", res.stdout)
            target = os.path.join(tmp, ".codex", "hooks.json")
            self.assertTrue(os.path.isfile(target))


if __name__ == "__main__":
    unittest.main()
