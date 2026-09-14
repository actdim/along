#!/usr/bin/env python3
"""
tests/test_hooks_claude.py - Hermetic unit tests for Claude Code hook adapter and installer.

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
from alongkit.hooks.adapters.claude import ClaudeCodeAdapter
from alongkit.hooks.config import (
    get_claude_hook_manifest,
    install_claude_hooks,
)

EM_DASH = chr(0x2014)


class TestClaudeCodeAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = get_adapter("claude")
        self.assertIsInstance(self.adapter, ClaudeCodeAdapter)

    def test_parse_write_tool(self):
        raw_payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": "src/main.py",
                "content": "def main(): pass\n",
            },
            "cwd": "/workspace/repo",
            "session_id": "session-xyz",
        })
        event = self.adapter.parse(raw_payload)
        self.assertEqual(event.event_type, HookEventType.PRE_TOOL_USE)
        self.assertEqual(event.tool_name, "write_to_file")
        self.assertEqual(event.tool_args["TargetFile"], "src/main.py")
        self.assertEqual(event.tool_args["CodeContent"], "def main(): pass\n")
        self.assertEqual(event.workspace_root, "/workspace/repo")
        self.assertEqual(event.conversation_id, "session-xyz")
        self.assertEqual(event.runtime, "claude")

    def test_parse_edit_tool_with_new_string(self):
        raw_payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "src/utils.py",
                "old_string": "x = 1",
                "new_string": "x = 2",
            },
            "cwd": "/workspace/repo",
        })
        event = self.adapter.parse(raw_payload)
        self.assertEqual(event.event_type, HookEventType.PRE_TOOL_USE)
        self.assertEqual(event.tool_name, "replace_file_content")
        self.assertEqual(event.tool_args["TargetFile"], "src/utils.py")
        self.assertEqual(event.tool_args["ReplacementContent"], "x = 2")
        self.assertEqual(event.tool_args["content"], "x = 2")
        self.assertEqual(event.tool_args["old_string"], "x = 1")

    def test_parse_bash_tool(self):
        raw_payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {
                "command": "git status",
            },
            "cwd": "/workspace/repo",
        })
        event = self.adapter.parse(raw_payload)
        self.assertEqual(event.event_type, HookEventType.PRE_TOOL_USE)
        self.assertEqual(event.tool_name, "run_command")
        self.assertEqual(event.tool_args["CommandLine"], "git status")

    def test_parse_stop_event(self):
        raw_payload = json.dumps({
            "hook_event_name": "Stop",
            "cwd": "/workspace/repo",
            "session_id": "session-stop",
        })
        event = self.adapter.parse(raw_payload)
        self.assertEqual(event.event_type, HookEventType.STOP)
        self.assertEqual(event.workspace_root, "/workspace/repo")
        self.assertEqual(event.conversation_id, "session-stop")

    def test_format_allow_response(self):
        result = GateResult(decision=GateDecision.ALLOW)
        code, output_str = self.adapter.format_response(result)
        self.assertEqual(code, 0)
        self.assertEqual(output_str, "")

    def test_format_deny_response(self):
        result = GateResult(decision=GateDecision.DENY, reason="Typography violation detected.")
        code, output_str = self.adapter.format_response(result)
        self.assertEqual(code, 2)
        self.assertEqual(output_str, "Typography violation detected.")


class TestClaudeCodeEndToEnd(unittest.TestCase):
    def test_cli_invocation_clean_payload_exits_zero(self):
        script_path = os.path.join(SCRIPTS_DIR, "along_hook.py")
        input_payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": "src/clean.py",
                "content": "val = 'clean ascii'\n",
            },
        })

        with tempfile.TemporaryDirectory() as tmp:
            along_dir = os.path.join(tmp, ".along")
            os.makedirs(along_dir, exist_ok=True)
            res = proc.run_capture(
                [sys.executable, script_path, "--runtime", "claude", "--event", "PreToolUse", "--repo-root", tmp],
                stdin_text=input_payload,
            )
            self.assertEqual(res.returncode, 0)
            self.assertEqual(res.stdout.strip(), "")
            self.assertEqual(res.stderr.strip(), "")

    def test_cli_invocation_typography_violation_exits_two_and_writes_stderr(self):
        script_path = os.path.join(SCRIPTS_DIR, "along_hook.py")
        bad_text = f"val = 'hello {EM_DASH} world'\n"
        input_payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": "src/bad.py",
                "content": bad_text,
            },
        })

        with tempfile.TemporaryDirectory() as tmp:
            along_dir = os.path.join(tmp, ".along")
            os.makedirs(along_dir, exist_ok=True)
            res = proc.run_capture(
                [sys.executable, script_path, "--runtime", "claude", "--event", "PreToolUse", "--repo-root", tmp],
                stdin_text=input_payload,
            )
            self.assertEqual(res.returncode, 2)
            self.assertEqual(res.stdout.strip(), "")
            self.assertIn("Typography", res.stderr)
            self.assertIn("em dash", res.stderr)

    def test_cli_invocation_edit_typography_violation_in_new_string(self):
        script_path = os.path.join(SCRIPTS_DIR, "along_hook.py")
        bad_text = f"val = 'bad {EM_DASH} replace'\n"
        input_payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Edit",
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
                [sys.executable, script_path, "--runtime", "claude", "--event", "PreToolUse", "--repo-root", tmp],
                stdin_text=input_payload,
            )
            self.assertEqual(res.returncode, 2)
            self.assertIn("Typography", res.stderr)

    def test_cli_invocation_cli_safety_heredoc_exits_two(self):
        script_path = os.path.join(SCRIPTS_DIR, "along_hook.py")
        input_payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {
                "command": "cat <<EOF > test.py\nx = 1\nEOF",
            },
        })

        with tempfile.TemporaryDirectory() as tmp:
            along_dir = os.path.join(tmp, ".along")
            os.makedirs(along_dir, exist_ok=True)
            # cli_safety is currently shadow by default; pass --mode enforce
            res = proc.run_capture(
                [
                    sys.executable,
                    script_path,
                    "--runtime",
                    "claude",
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


class TestInstallClaudeHooks(unittest.TestCase):
    def test_clean_install_creates_settings_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, msg = install_claude_hooks(tmp)
            self.assertEqual(status, "installed")
            target = os.path.join(tmp, ".claude", "settings.json")
            self.assertTrue(os.path.isfile(target))
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("hooks", data)
            self.assertIn("PreToolUse", data["hooks"])
            self.assertIn("PostToolUse", data["hooks"])
            self.assertIn("Stop", data["hooks"])

            # Idempotency check
            status2, _ = install_claude_hooks(tmp)
            self.assertEqual(status2, "present")

    def test_existing_custom_settings_and_hooks_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = os.path.join(tmp, ".claude")
            os.makedirs(claude_dir, exist_ok=True)
            target = os.path.join(claude_dir, "settings.json")
            initial_data = {
                "theme": "dark",
                "permissions": {"allow": ["Read"]},
                "hooks": {
                    "PreToolUse": [
                        {"matcher": "Read", "command": "echo read"}
                    ]
                },
            }
            with open(target, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, indent=2)

            status, _ = install_claude_hooks(tmp)
            self.assertEqual(status, "installed")
            with open(target, "r", encoding="utf-8") as f:
                updated_data = json.load(f)

            self.assertEqual(updated_data["theme"], "dark")
            self.assertEqual(updated_data["permissions"]["allow"], ["Read"])
            # User custom hook must still exist
            pre_hooks = updated_data["hooks"]["PreToolUse"]
            self.assertTrue(any(h.get("command") == "echo read" for h in pre_hooks))
            self.assertTrue(any("along_hook.py" in h.get("command", "") for h in pre_hooks))

    def test_dry_run_does_not_mutate_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, _ = install_claude_hooks(tmp, dry_run=True)
            self.assertEqual(status, "dry-run")
            target = os.path.join(tmp, ".claude", "settings.json")
            self.assertFalse(os.path.exists(target))

    def test_cli_install_subcommand_with_runtime_claude(self):
        script_path = os.path.join(SCRIPTS_DIR, "along_hook.py")
        with tempfile.TemporaryDirectory() as tmp:
            res = proc.run_capture(
                [sys.executable, script_path, "install", "--runtime", "claude", "--repo-root", tmp],
            )
            self.assertEqual(res.returncode, 0)
            self.assertIn("updated", res.stdout)
            target = os.path.join(tmp, ".claude", "settings.json")
            self.assertTrue(os.path.isfile(target))


if __name__ == "__main__":
    unittest.main()
