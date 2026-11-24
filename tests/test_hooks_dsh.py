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
from alongkit.hooks.adapters import normalize
from alongkit.hooks.config import (
    DSH_PRE_TOOL_MATCHER,
    get_dsh_hook_manifest,
    install_dsh_hooks,
)
from alongkit.hooks.adapters import can_ask


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

        # The bridge must mount the DSH hooks file, not the Claude manifest: the harness
        # matches a matcher against its own tool names, and the Claude list admits none.
        self.assertIn("along-hooks.json", content)
        self.assertNotIn(".claude/settings.json", content)
        hooks_file = os.path.join(repo_root, ".dsh", "along-hooks.json")
        self.assertTrue(os.path.isfile(hooks_file), "the mounted hooks file was not written")

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
        hooks_file = os.path.join(desktop_dir, "along-hooks.json")
        self.assertTrue(os.path.isfile(hooks_file))
        self.assertIn(os.path.abspath(hooks_file).replace("\\", "/"), content)
        self.assertNotIn("./.dsh/along-hooks.json", content)
        hooks_data = json.loads(open(hooks_file, "r", encoding="utf-8").read())
        pre_cmd = hooks_data["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        self.assertNotIn("scripts/along_hook.py", pre_cmd)
        self.assertIn("--runtime dsh", pre_cmd)


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

    def test_dsh_planned_skills_install(self):
        home = tempfile.mkdtemp(prefix="along-dsh-skills-")
        try:
            homes = install.Homes.defaults(home)
            plan = install.planned_files(REPO_ROOT, homes, providers=("dsh",))
            expected_skill = os.path.join(homes.dsh, "skills", "along-init", "SKILL.md")
            self.assertIn(expected_skill, plan)
            self.assertEqual(
                os.path.normpath(plan[expected_skill]),
                os.path.normpath(os.path.join(REPO_ROOT, "skills", "along-init", "SKILL.md")),
            )
        finally:
            shutil.rmtree(home, ignore_errors=True)

    def test_dsh_runtime_matrix(self):
        self.assertIn("dsh", runtime.RUNTIME_MATRIX)
        self.assertTrue(runtime.RUNTIME_MATRIX["dsh"]["runtime_hooks"])


def bridge_payload(tool_name: str, tool_args=None) -> str:
    """A Claude-dialect DSH bridge payload carrying a model-facing tool name.

    Shape taken from `@deepseek-ai/dsh-hooks-claude-code`: session_id, an intentionally empty
    transcript_path, cwd, hook_event_name, tool_name, tool_input.
    """
    return json.dumps({
        "session_id": "ses-along-test",
        "transcript_path": "",
        "cwd": REPO_ROOT,
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": tool_args or {},
    })


#: The names DeepSeek Harness publishes to the model: dsh-tool-fs -> read/write/edit,
#: dsh-tool-fs-search -> glob/grep, dsh-tool-todo -> todo_write.
MODEL_FACING_TOOL_NAMES = ("read", "write", "edit", "glob", "grep", "todo_write")


class TestDshModelFacingToolNames(unittest.TestCase):
    """The bridge sends model-facing names, not the composition entry ids.

    The classes above pin the `tool-fs` / `tool-pwsh` aliases, which is what a cordis patch
    row is called. A real session sends `read`, `write`, `edit`, `glob`, `grep`, `todo_write`.
    See [bug--dsh-tool-name-map-and-ask-capability].
    """

    def setUp(self):
        self.adapter = DeepSeekHarnessAdapter()

    def test_no_model_facing_name_stays_unmapped(self):
        for name in MODEL_FACING_TOOL_NAMES:
            with self.subTest(tool=name):
                event = normalize.fail_closed(self.adapter.parse(bridge_payload(name)))
                self.assertNotIn(
                    normalize.UNMAPPED_MARKER,
                    event.tool_args,
                    "'%s' reaches no gate: workspace_containment declares view_file, grep_search "
                    "and find_by_name, but this name stays unmapped" % name,
                )

    def test_read_and_task_names_are_not_inferred_as_writes(self):
        """`fail_closed` infers a write from the name, and `todo_write` contains `write`.

        Left unmapped, that inference turns a todo update into `replace_file_content`, so
        `require_active_issue` demands an in-progress issue for ticking a checkbox.
        """
        for name in ("read", "glob", "grep", "todo_write"):
            with self.subTest(tool=name):
                event = normalize.fail_closed(self.adapter.parse(bridge_payload(name)))
                self.assertNotIn(
                    event.tool_name,
                    normalize.WRITE_TOOLS,
                    "'%s' was classified as a file mutation" % name,
                )

    def test_write_content_reaches_the_gates(self):
        event = normalize.fail_closed(
            self.adapter.parse(bridge_payload("write", {"file_path": "src/a.py", "content": "x = 1\n"}))
        )
        self.assertIn(event.tool_name, normalize.WRITE_TOOLS)
        self.assertEqual(event.tool_args.get("content"), "x = 1\n")

    def test_edit_replacement_reaches_the_content_gates(self):
        """anti_stub_injection and typography read CodeContent/ReplacementContent/content.

        The Claude adapter maps `new_string` onto both fields; this adapter leaves it as
        `new_string`, which no content gate inspects.
        """
        event = normalize.fail_closed(
            self.adapter.parse(
                bridge_payload("edit", {"file_path": "src/a.py", "old_string": "a", "new_string": "b"})
            )
        )
        self.assertIn(event.tool_name, normalize.WRITE_TOOLS)
        carried = event.tool_args.get("ReplacementContent") or event.tool_args.get("content")
        self.assertEqual(carried, "b", "the replacement text reaches no content gate")


class TestDshAskCapability(unittest.TestCase):
    """The Claude-dialect bridge supports ask on PreToolUse, so a DSH session must be asked."""

    def test_adapter_can_express_ask(self):
        adapter = DeepSeekHarnessAdapter()
        adapter.parse(bridge_payload("pwsh", {"command": "rm -rf build"}))
        code, output = adapter.format_response(
            GateResult(decision=GateDecision.ASK, reason="confirm delete")
        )
        self.assertEqual(code, 0)
        decision = json.loads(output)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "ask")
        self.assertEqual(decision["permissionDecisionReason"], "confirm delete")

    def test_engine_routes_ask_for_dsh(self):
        self.assertTrue(
            can_ask("dsh"),
            "an ASK result for a DSH session is rewritten to DENY inside engine.evaluate",
        )

    def test_ask_capability_matches_the_adapters_that_can_express_it(self):
        for runtime in ("antigravity", "claude", "dsh"):
            with self.subTest(runtime=runtime):
                self.assertTrue(can_ask(runtime))
        for runtime in ("codex", "cursor", "generic", "opencode"):
            with self.subTest(runtime=runtime):
                self.assertFalse(can_ask(runtime))


class TestDshManifestMatcher(unittest.TestCase):
    """The generated matcher must name harness tools, not Claude Code ones."""

    def _alternatives(self) -> set:
        return {part.strip() for part in DSH_PRE_TOOL_MATCHER.split("|") if part.strip()}

    def test_matcher_names_every_model_facing_tool(self):
        alternatives = self._alternatives()
        for name in MODEL_FACING_TOOL_NAMES:
            with self.subTest(tool=name):
                self.assertIn(name, alternatives, "the bridge never admits '%s'" % name)

    def test_matcher_has_no_claude_only_capitalised_names(self):
        for name in ("Write", "Edit", "Bash", "Read", "Glob", "Grep"):
            with self.subTest(tool=name):
                self.assertNotIn(
                    name,
                    self._alternatives(),
                    "Claude Code spelling '%s' matches no DeepSeek Harness tool" % name,
                )

    def test_manifest_declares_the_lifecycle_events(self):
        hooks = get_dsh_hook_manifest(is_global=False)["hooks"]
        for event in ("PreToolUse", "PostToolUse", "Stop", "UserPromptSubmit"):
            with self.subTest(event=event):
                self.assertIn(event, hooks)
                self.assertTrue(hooks[event])
                command = hooks[event][0]["hooks"][0]["command"]
                self.assertIn("--runtime dsh", command)
                self.assertIn("--event %s" % event, command)

    def test_matcher_admits_the_tool_names_the_adapter_maps(self):
        """Every model-facing name in the adapter's own map must be admitted."""
        from alongkit.hooks.adapters.dsh import DSH_TOOL_NAME_MAP
        alternatives = self._alternatives()
        for name in MODEL_FACING_TOOL_NAMES:
            with self.subTest(tool=name):
                self.assertIn(name, DSH_TOOL_NAME_MAP)
                self.assertIn(name, alternatives)


if __name__ == "__main__":
    unittest.main()
