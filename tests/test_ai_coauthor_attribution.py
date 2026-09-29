#!/usr/bin/env python3
"""
tests/test_ai_coauthor_attribution.py - AI co-author trailers stay out of commits.

Covers [feat--suppress-ai-coauthor-attribution]: the trailer helpers in
`alongkit.attribution`, the `commit_no_ai_coauthor` gate predicate, the runtime
config writers used by `along hook install`, and the repository opt-out.
All filesystem work happens in throwaway temp directories.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import attribution
from alongkit.hooks import HookEvent, HookEventType
from alongkit.hooks.config import install_claude_hooks, install_cursor_hooks, reconcile_attribution
from alongkit.hooks.declarative import get_all_declarative_gates
from alongkit.hooks.predicates import check_ai_coauthor

CLAUDE_TRAILER = "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
GEMINI_TRAILER = "Co-Authored-By: Antigravity (Gemini) <noreply@google.com>"
HUMAN_TRAILER = "Co-Authored-By: Jane Doe <jane@example.com>"


def _command_event(command):
    return HookEvent(event_type=HookEventType.PRE_TOOL_USE, tool_name="run_command",
                     tool_args={"CommandLine": command}, runtime="generic")


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f)


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class TemporaryRepoCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along-attribution-")
        os.makedirs(os.path.join(self.root, ".along"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def opt_out(self):
        _write_json(os.path.join(self.root, ".along", "config.json"),
                    {"commits": {"allow_ai_coauthor": True}})


class TestTrailerHelpers(unittest.TestCase):
    def test_strip_removes_ai_trailers_and_keeps_human(self):
        msg = f"feat: x\n\nbody\n\n{HUMAN_TRAILER}\n{CLAUDE_TRAILER}\n{GEMINI_TRAILER}\n"
        self.assertEqual(attribution.strip_ai_coauthor_trailers(msg),
                         f"feat: x\n\nbody\n\n{HUMAN_TRAILER}\n")

    def test_strip_drops_trailing_blank_lines(self):
        self.assertEqual(attribution.strip_ai_coauthor_trailers(f"fix: y\n\n{CLAUDE_TRAILER}"), "fix: y")

    def test_strip_leaves_clean_message_untouched(self):
        msg = f"fix: y\n\n{HUMAN_TRAILER}\n"
        self.assertIs(attribution.strip_ai_coauthor_trailers(msg), msg)

    def test_find_in_command_line(self):
        cmd = f'git commit -m "feat: x" -m "{CLAUDE_TRAILER}"'
        self.assertEqual(attribution.find_ai_coauthor(cmd), CLAUDE_TRAILER)
        self.assertIsNone(attribution.find_ai_coauthor(f'git commit -m "x" -m "{HUMAN_TRAILER}"'))

    def test_case_insensitive_trailer_key(self):
        self.assertTrue(attribution.is_ai_coauthor_line("co-authored-by: Codex <noreply@openai.com>"))


class TestGatePredicate(TemporaryRepoCase):
    def test_denies_ai_trailer_in_message_flag(self):
        reason = check_ai_coauthor(_command_event(f'git commit -m "feat: x" -m "{CLAUDE_TRAILER}"'), self.root)
        self.assertIsNotNone(reason)
        self.assertIn("commit-no-ai-coauthor", reason)

    def test_denies_ai_trailer_in_heredoc(self):
        cmd = f"git commit -m \"$(cat <<'EOF'\nfeat: x\n\n{GEMINI_TRAILER}\nEOF\n)\""
        self.assertIsNotNone(check_ai_coauthor(_command_event(cmd), self.root))

    def test_denies_ai_trailer_in_message_file(self):
        with open(os.path.join(self.root, "msg.txt"), "w", encoding="utf-8") as f:
            f.write(f"feat: x\n\n{CLAUDE_TRAILER}\n")
        self.assertIsNotNone(check_ai_coauthor(_command_event("git commit -F msg.txt"), self.root))

    def test_allows_human_coauthor(self):
        self.assertIsNone(check_ai_coauthor(_command_event(f'git commit -m "x" -m "{HUMAN_TRAILER}"'), self.root))

    def test_ignores_non_commit_commands(self):
        self.assertIsNone(check_ai_coauthor(_command_event(f'echo "{CLAUDE_TRAILER}"'), self.root))

    def test_catches_chained_commit(self):
        cmd = f'git add -A && git commit -m "x" -m "{CLAUDE_TRAILER}"'
        self.assertIsNotNone(check_ai_coauthor(_command_event(cmd), self.root))

    def test_opt_out_allows_ai_trailer(self):
        self.opt_out()
        self.assertIsNone(check_ai_coauthor(_command_event(f'git commit -m "x" -m "{CLAUDE_TRAILER}"'), self.root))

    def test_gate_registered_in_catalogue(self):
        names = {getattr(g, "name", "") for g in get_all_declarative_gates(self.root)}
        self.assertIn("commit_no_ai_coauthor", names)


class TestClaudeSettings(TemporaryRepoCase):
    def settings_path(self):
        return os.path.join(self.root, ".claude", "settings.json")

    def test_install_writes_attribution_and_keeps_foreign_keys(self):
        _write_json(self.settings_path(), {"theme": "dark", "attribution": {"pr": "custom"}})
        status, _ = install_claude_hooks(self.root)
        self.assertEqual(status, "installed")
        data = _read_json(self.settings_path())
        self.assertEqual(data["attribution"], {"pr": "custom", "commit": ""})
        self.assertIs(data["includeCoAuthoredBy"], False)
        self.assertEqual(data["theme"], "dark")
        self.assertEqual(install_claude_hooks(self.root)[0], "present")

    def test_install_restores_removed_attribution(self):
        install_claude_hooks(self.root)
        data = _read_json(self.settings_path())
        data["attribution"]["commit"] = "Co-Authored-By: Claude <noreply@anthropic.com>"
        _write_json(self.settings_path(), data)
        self.assertEqual(install_claude_hooks(self.root)[0], "installed")
        self.assertEqual(_read_json(self.settings_path())["attribution"]["commit"], "")

    def test_opt_out_leaves_attribution_alone(self):
        self.opt_out()
        install_claude_hooks(self.root)
        data = _read_json(self.settings_path())
        self.assertNotIn("attribution", data)
        self.assertNotIn("includeCoAuthoredBy", data)


class TestCursorConfig(unittest.TestCase):
    def test_global_install_writes_cli_config(self):
        with tempfile.TemporaryDirectory() as home:
            _write_json(os.path.join(home, "cli-config.json"), {"editor": {"vimMode": True}})
            install_cursor_hooks(None, is_global=True, target_home=home)
            data = _read_json(os.path.join(home, "cli-config.json"))
            self.assertIs(data["attribution"]["attributeCommitsToAgent"], False)
            self.assertEqual(data["editor"], {"vimMode": True})

    def test_local_install_does_not_touch_cli_config(self):
        with tempfile.TemporaryDirectory() as root:
            install_cursor_hooks(root)
            self.assertFalse(os.path.exists(os.path.join(root, ".cursor", "cli-config.json")))


class TestReconcileAttribution(TemporaryRepoCase):
    def setUp(self):
        super().setUp()
        self.home = tempfile.mkdtemp(prefix="along-attr-home-")
        self.addCleanup(shutil.rmtree, self.home, True)
        self.claude = os.path.join(self.home, ".claude")
        self.cursor = os.path.join(self.home, ".cursor")

    def reconcile(self, **kwargs):
        return reconcile_attribution(claude_home=self.claude, cursor_home=self.cursor,
                                     repo_root=self.root, **kwargs)

    def test_missing_runtime_homes_are_not_created(self):
        self.assertEqual(self.reconcile(), [])
        self.assertFalse(os.path.exists(self.claude))
        self.assertFalse(os.path.exists(self.cursor))

    def test_writes_only_attribution_keys_and_is_idempotent(self):
        _write_json(os.path.join(self.claude, "settings.json"), {"theme": "dark"})
        os.makedirs(self.cursor)
        self.assertEqual([s for s, _ in self.reconcile()], ["installed", "installed"])
        claude = _read_json(os.path.join(self.claude, "settings.json"))
        self.assertEqual(claude, {"theme": "dark", "attribution": {"commit": ""}, "includeCoAuthoredBy": False})
        self.assertNotIn("hooks", claude)
        self.assertIs(_read_json(os.path.join(self.cursor, "cli-config.json"))["attribution"]["attributeCommitsToAgent"], False)
        self.assertEqual([s for s, _ in self.reconcile()], ["present", "present"])

    def test_runtime_filter(self):
        os.makedirs(self.claude)
        os.makedirs(self.cursor)
        self.reconcile(runtimes=("cursor",))
        self.assertFalse(os.path.exists(os.path.join(self.claude, "settings.json")))

    def test_dry_run_writes_nothing(self):
        os.makedirs(self.claude)
        self.assertEqual([s for s, _ in self.reconcile(dry_run=True)], ["dry-run"])
        self.assertFalse(os.path.exists(os.path.join(self.claude, "settings.json")))

    def test_opt_out(self):
        os.makedirs(self.claude)
        self.opt_out()
        self.reconcile()
        self.assertFalse(os.path.exists(os.path.join(self.claude, "settings.json")))

    def test_cli_subcommand(self):
        os.makedirs(self.cursor)
        script = os.path.join(SCRIPTS_DIR, "along_hook.py")
        res = subprocess.run(
            [sys.executable, script, "attribution", "--runtime", "cursor",
             "--cursor-home", self.cursor, "--repo-root", self.root],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.cursor, "cli-config.json")))


if __name__ == "__main__":
    unittest.main()
