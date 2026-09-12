#!/usr/bin/env python3
"""
tests/test_hooks_core.py - Hermetic unit tests for the core hook engine and gates.

Banned characters are constructed with chr() so this test file itself remains clean.
All tests execute in isolated throwaway directories without touching repo state.
"""

from __future__ import annotations

import io
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

from alongkit import proc
from alongkit.hooks import (
    GateDecision,
    GateResult,
    HookEngine,
    HookEvent,
    HookEventType,
    HooksConfig,
    evaluate_event,
    get_adapter,
)
from alongkit.hooks.config import HookMode
from alongkit.hooks.gates import (
    CliSafetyGate,
    ProjectionProtectionGate,
    TypographyGate,
)

EM_DASH = chr(0x2014)
LEFT_CURLY_QUOTE = chr(0x201C)
RIGHT_CURLY_QUOTE = chr(0x201D)
NBSP = chr(0x00A0)
ELLIPSIS_GLYPH = chr(0x2026)


class TestTypographyGate(unittest.TestCase):
    def setUp(self):
        self.gate = TypographyGate()

    def test_clean_ascii_is_allowed(self):
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": "src/main.py", "CodeContent": "x = 'hello world'\n"},
        )
        result = self.gate.evaluate(event)
        self.assertEqual(result.decision, GateDecision.ALLOW)

    def test_em_dash_in_write_to_file_is_denied(self):
        bad_text = f"title = 'hello {EM_DASH} world'\n"
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": "docs/guide.md", "CodeContent": bad_text},
        )
        result = self.gate.evaluate(event)
        self.assertEqual(result.decision, GateDecision.DENY)
        self.assertIn("Typography Gate Violation", result.reason or "")
        self.assertIn("em dash", result.reason or "")
        self.assertIn("line", result.reason or "")

    def test_curly_quotes_in_replace_file_content_is_denied(self):
        bad_text = f"value = {LEFT_CURLY_QUOTE}quoted{RIGHT_CURLY_QUOTE}\n"
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="replace_file_content",
            tool_args={"TargetFile": "src/utils.py", "ReplacementContent": bad_text},
        )
        result = self.gate.evaluate(event)
        self.assertEqual(result.decision, GateDecision.DENY)
        self.assertIn("curly double quote", result.reason or "")

    def test_localized_directories_are_skipped(self):
        bad_text = f"welcome = 'bonjour {LEFT_CURLY_QUOTE}'\n"
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": "locales/fr.json", "CodeContent": bad_text},
        )
        result = self.gate.evaluate(event)
        self.assertEqual(result.decision, GateDecision.ALLOW)

    def test_non_governed_extensions_are_skipped(self):
        bad_text = f"binary data with {EM_DASH}"
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": "assets/data.bin", "CodeContent": bad_text},
        )
        result = self.gate.evaluate(event)
        self.assertEqual(result.decision, GateDecision.ALLOW)


class TestProjectionProtectionGate(unittest.TestCase):
    def setUp(self):
        self.gate = ProjectionProtectionGate()

    def test_direct_edit_to_issues_projection_is_denied(self):
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": ".along/ISSUES.md", "CodeContent": "# Fake Edit\n"},
        )
        result = self.gate.evaluate(event)
        self.assertEqual(result.decision, GateDecision.DENY)
        self.assertIn("Projection Protection Violation", result.reason or "")
        self.assertIn("Single Source of Truth", result.reason or "")

    def test_direct_edit_to_docs_index_is_denied(self):
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="replace_file_content",
            tool_args={"TargetFile": "docs/INDEX.md", "ReplacementContent": "# Index\n"},
        )
        result = self.gate.evaluate(event)
        self.assertEqual(result.decision, GateDecision.DENY)
        self.assertIn("Projection Protection Violation", result.reason or "")

    def test_edit_to_atomic_issue_is_allowed(self):
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": ".along/ISSUES/feat--sample.md", "CodeContent": "---\n---\n"},
        )
        result = self.gate.evaluate(event)
        self.assertEqual(result.decision, GateDecision.ALLOW)


class TestCliSafetyGate(unittest.TestCase):
    def setUp(self):
        self.gate = CliSafetyGate()

    def test_clean_shell_command_is_allowed(self):
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": "pytest -q"},
        )
        result = self.gate.evaluate(event)
        self.assertEqual(result.decision, GateDecision.ALLOW)

    def test_heredoc_is_denied(self):
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": "cat <<EOF > test.py\nx = 1\nEOF"},
        )
        result = self.gate.evaluate(event)
        self.assertEqual(result.decision, GateDecision.DENY)
        self.assertIn("Heredoc syntax", result.reason or "")

    def test_inline_python_writer_is_denied(self):
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": "python -c \"open('out.py', 'w').write('data')\""},
        )
        result = self.gate.evaluate(event)
        self.assertEqual(result.decision, GateDecision.DENY)
        self.assertIn("Inline Python file writer", result.reason or "")

    def test_destructive_git_wipe_is_denied(self):
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": "git reset --hard HEAD~1"},
        )
        result = self.gate.evaluate(event)
        self.assertEqual(result.decision, GateDecision.DENY)
        self.assertIn("git reset --hard", result.reason or "")

    def test_global_npm_install_is_denied(self):
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": "npm install -g along-tools"},
        )
        result = self.gate.evaluate(event)
        self.assertEqual(result.decision, GateDecision.DENY)
        self.assertIn("npm -g", result.reason or "")


class TestAntigravityAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = get_adapter("antigravity")

    def test_parse_pre_tool_use(self):
        raw_json = json.dumps({
            "toolCall": {
                "name": "write_to_file",
                "args": {
                    "TargetFile": "test.txt",
                    "CodeContent": "hello",
                },
            },
            "stepIdx": 5,
            "conversationId": "conv-123",
            "workspacePaths": ["/workspace/proj"],
        })
        event = self.adapter.parse(raw_json, event_type=HookEventType.PRE_TOOL_USE)
        self.assertEqual(event.event_type, HookEventType.PRE_TOOL_USE)
        self.assertEqual(event.tool_name, "write_to_file")
        self.assertEqual(event.tool_args["TargetFile"], "test.txt")
        self.assertEqual(event.workspace_root, "/workspace/proj")
        self.assertEqual(event.conversation_id, "conv-123")
        self.assertEqual(event.step_idx, 5)

    def test_format_allow_response(self):
        result = GateResult(decision=GateDecision.ALLOW)
        code, output_str = self.adapter.format_response(result)
        self.assertEqual(code, 0)
        data = json.loads(output_str)
        self.assertEqual(data["decision"], "allow")

    def test_format_deny_response(self):
        result = GateResult(decision=GateDecision.DENY, reason="Forbidden character")
        code, output_str = self.adapter.format_response(result)
        self.assertEqual(code, 0)
        data = json.loads(output_str)
        self.assertEqual(data["decision"], "deny")
        self.assertEqual(data["reason"], "Forbidden character")


class TestEngineGovernanceAndAudit(unittest.TestCase):
    def test_shadow_mode_permits_execution_and_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            along_dir = os.path.join(tmp, ".along")
            os.makedirs(along_dir, exist_ok=True)

            config = HooksConfig(
                mode=HookMode.SHADOW,
                gates={"typography": HookMode.SHADOW},
            )
            engine = HookEngine(config=config)

            bad_text = f"bad {EM_DASH} text\n"
            event = HookEvent(
                event_type=HookEventType.PRE_TOOL_USE,
                tool_name="write_to_file",
                tool_args={"TargetFile": "foo.py", "CodeContent": bad_text},
                workspace_root=tmp,
            )

            result = engine.evaluate(event, repo_root=tmp)
            # In shadow mode, decision remains ALLOW
            self.assertEqual(result.decision, GateDecision.ALLOW)

            # Audit file must be created
            audit_file = os.path.join(along_dir, "diagnostics", "hooks_audit.jsonl")
            self.assertTrue(os.path.isfile(audit_file))
            with open(audit_file, "r", encoding="utf-8") as handle:
                lines = handle.readlines()
            self.assertEqual(len(lines), 1)
            record = json.loads(lines[0])
            self.assertEqual(record["gate"], "typography")
            self.assertEqual(record["mode"], HookMode.SHADOW)
            self.assertEqual(record["decision"], "deny")

    def test_enforce_mode_blocks_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            along_dir = os.path.join(tmp, ".along")
            os.makedirs(along_dir, exist_ok=True)

            config = HooksConfig(
                mode=HookMode.ENFORCE,
                gates={"typography": HookMode.ENFORCE},
            )
            engine = HookEngine(config=config)

            bad_text = f"bad {EM_DASH} text\n"
            event = HookEvent(
                event_type=HookEventType.PRE_TOOL_USE,
                tool_name="write_to_file",
                tool_args={"TargetFile": "foo.py", "CodeContent": bad_text},
                workspace_root=tmp,
            )

            result = engine.evaluate(event, repo_root=tmp)
            self.assertEqual(result.decision, GateDecision.DENY)
            self.assertIn("em dash", result.reason or "")

            audit_file = os.path.join(along_dir, "diagnostics", "hooks_audit.jsonl")
            self.assertTrue(os.path.isfile(audit_file))


class TestAlongHookCliE2E(unittest.TestCase):
    def test_cli_invocation_returns_valid_antigravity_json(self):
        script_path = os.path.join(SCRIPTS_DIR, "along_hook.py")
        input_payload = json.dumps({
            "toolCall": {
                "name": "write_to_file",
                "args": {
                    "TargetFile": "test.py",
                    "CodeContent": f"bad {EM_DASH} code\n",
                },
            },
        })

        with tempfile.TemporaryDirectory() as tmp:
            along_dir = os.path.join(tmp, ".along")
            os.makedirs(along_dir, exist_ok=True)
            res = proc.run_capture(
                [sys.executable, script_path, "--runtime", "antigravity", "--event", "PreToolUse", "--repo-root", tmp],
                stdin_text=input_payload,
            )
            self.assertEqual(res.returncode, 0)
            data = json.loads(res.stdout)
            self.assertEqual(data["decision"], "deny")
            self.assertIn("Typography Gate Violation", data["reason"])


class TestInstallAntigravityHooks(unittest.TestCase):
    def test_clean_install_creates_hooks_json(self):
        from alongkit.hooks.config import install_antigravity_hooks
        with tempfile.TemporaryDirectory() as tmp:
            status, msg = install_antigravity_hooks(tmp)
            self.assertEqual(status, "installed")
            target = os.path.join(tmp, ".agents", "hooks.json")
            self.assertTrue(os.path.isfile(target))
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("along-runtime-gates", data)
            self.assertIn("PreToolUse", data["along-runtime-gates"])

            # Idempotency check
            status2, _ = install_antigravity_hooks(tmp)
            self.assertEqual(status2, "present")

    def test_existing_custom_hooks_are_preserved(self):
        from alongkit.hooks.config import install_antigravity_hooks
        with tempfile.TemporaryDirectory() as tmp:
            agents_dir = os.path.join(tmp, ".agents")
            os.makedirs(agents_dir, exist_ok=True)
            target = os.path.join(agents_dir, "hooks.json")
            with open(target, "w", encoding="utf-8") as f:
                json.dump({"user-lint": {"PostToolUse": []}}, f)

            status, _ = install_antigravity_hooks(tmp)
            self.assertEqual(status, "installed")
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("user-lint", data)
            self.assertIn("along-runtime-gates", data)

    def test_dry_run_does_not_mutate_disk(self):
        from alongkit.hooks.config import install_antigravity_hooks
        with tempfile.TemporaryDirectory() as tmp:
            status, _ = install_antigravity_hooks(tmp, dry_run=True)
            self.assertEqual(status, "dry-run")
            target = os.path.join(tmp, ".agents", "hooks.json")
            self.assertFalse(os.path.exists(target))


if __name__ == "__main__":
    unittest.main()

