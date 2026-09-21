"""
Hermetic test suite for update, migration, and runtime hooks hardening.
Verifies:
1. Global hook manifests generation (is_global=True) for Antigravity, Claude, Codex, Cursor.
2. fail-open behavior of along_hook.py on non-Along workspaces.
3. purge_local_along_hooks cleans spurious hooks and workaround scripts from consumer repos.
4. purge_local_along_hooks preserves unrelated user hooks and configs.
5. migrate_protocol Step 12 cleans legacy hooks even if protocol version was already recorded.
6. textio.write_text exponential backoff retry.
7. entities.sync_constraints empty path handling when no decisions exist.
8. validate_and_build_entity_graph ancestor context cross-reference resolution.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import hermetic
from alongkit import entities, repo, textio
from alongkit.hooks import config as hook_config
from alongkit.hooks import purge_local_along_hooks


class TestUpdateAndHooksHardening(unittest.TestCase):

    def test_global_hook_manifests(self):
        """Global manifests must generate shell-independent python fail-open commands."""
        # Antigravity
        ag_manifest = hook_config.get_antigravity_hook_manifest(is_global=True)
        self.assertIn("along-runtime-gates", ag_manifest)
        pre_tool_cmd = ag_manifest["along-runtime-gates"]["PreToolUse"][0]["hooks"][0]["command"]
        self.assertIn("along_hook.py", pre_tool_cmd)
        self.assertIn("~/.along/bin/along_hook.py", pre_tool_cmd)
        self.assertIn("--runtime antigravity", pre_tool_cmd)

        # Claude
        claude_manifest = hook_config.get_claude_hook_manifest(is_global=True)
        self.assertIn("PreToolUse", claude_manifest)
        self.assertIn("--runtime claude", claude_manifest["PreToolUse"][0]["command"])
        self.assertIn("~/.along/bin/along_hook.py", claude_manifest["PreToolUse"][0]["command"])

        # Codex
        codex_manifest = hook_config.get_codex_hook_manifest(is_global=True)
        self.assertIn("hooks", codex_manifest)
        self.assertIn("PreToolUse", codex_manifest["hooks"])
        self.assertIn("--runtime codex", codex_manifest["hooks"]["PreToolUse"][0]["command"])

        # Cursor
        cursor_manifest = hook_config.get_cursor_hook_manifest(is_global=True)
        self.assertIn("hooks", cursor_manifest)
        self.assertIn("preToolUse", cursor_manifest["hooks"])
        self.assertIn("--runtime cursor", cursor_manifest["hooks"]["preToolUse"][0]["command"])

    def test_purge_local_along_hooks_removes_spurious_artifacts(self):
        """purge_local_along_hooks must remove Along hooks, workaround scripts, and empty dirs."""
        with hermetic.repo_fixture(prefix="test-purge-") as tmp:
            # Create spurious artifacts
            ag_hooks = os.path.join(tmp, ".agents", "hooks.json")
            cl_settings = os.path.join(tmp, ".claude", "settings.json")
            cx_hooks = os.path.join(tmp, ".codex", "hooks.json")
            cr_hooks = os.path.join(tmp, ".cursor", "hooks.json")
            workaround1 = os.path.join(tmp, "scripts", "along_hook.py")
            workaround2 = os.path.join(tmp, ".along", "scripts", "along_hook.py")

            for p in [ag_hooks, cl_settings, cx_hooks, cr_hooks, workaround1, workaround2]:
                os.makedirs(os.path.dirname(p), exist_ok=True)

            textio.write_text(ag_hooks, json.dumps({"along-runtime-gates": {"pre_tool": "python foo"}}))
            textio.write_text(cl_settings, json.dumps({"hooks": {"PreToolUse": [{"command": "python ../scripts/along_hook.py"}]}}))
            textio.write_text(cx_hooks, json.dumps({"hooks": {"PreToolUse": [{"command": "python ../scripts/along_hook.py"}]}}))
            textio.write_text(cr_hooks, json.dumps({"version": 1, "hooks": {"preToolUse": [{"command": "python ../scripts/along_hook.py"}]}}))
            textio.write_text(workaround1, "# workaround 1\n")
            textio.write_text(workaround2, "# workaround 2\n")

            # Dry-run first
            dry_actions = purge_local_along_hooks(tmp, dry_run=True)
            self.assertTrue(len(dry_actions) > 0)
            self.assertTrue(os.path.exists(ag_hooks))
            self.assertTrue(os.path.exists(workaround1))

            # Real purge
            actions = purge_local_along_hooks(tmp, dry_run=False)
            self.assertTrue(len(actions) > 0)

            self.assertFalse(os.path.exists(ag_hooks), "Must remove .agents/hooks.json")
            self.assertFalse(os.path.exists(os.path.dirname(ag_hooks)), "Must remove empty .agents dir")
            self.assertFalse(os.path.exists(cl_settings), "Must remove .claude/settings.json")
            self.assertFalse(os.path.exists(os.path.dirname(cl_settings)), "Must remove empty .claude dir")
            self.assertFalse(os.path.exists(cx_hooks), "Must remove .codex/hooks.json")
            self.assertFalse(os.path.exists(os.path.dirname(cx_hooks)), "Must remove empty .codex dir")
            self.assertFalse(os.path.exists(cr_hooks), "Must remove .cursor/hooks.json")
            self.assertFalse(os.path.exists(os.path.dirname(cr_hooks)), "Must remove empty .cursor dir")
            self.assertFalse(os.path.exists(workaround1), "Must remove scripts/along_hook.py")
            self.assertFalse(os.path.exists(os.path.dirname(workaround1)), "Must remove empty scripts dir")
            self.assertFalse(os.path.exists(workaround2), "Must remove .along/scripts/along_hook.py")

    def test_purge_local_along_hooks_preserves_unrelated_user_configs(self):
        """purge_local_along_hooks must preserve non-Along hooks and user settings."""
        with hermetic.repo_fixture(prefix="test-preserve-") as tmp:
            cl_settings = os.path.join(tmp, ".claude", "settings.json")
            cx_hooks = os.path.join(tmp, ".codex", "hooks.json")
            cr_hooks = os.path.join(tmp, ".cursor", "hooks.json")

            for p in [cl_settings, cx_hooks, cr_hooks]:
                os.makedirs(os.path.dirname(p), exist_ok=True)

            textio.write_text(cl_settings, json.dumps({
                "theme": "dark",
                "hooks": {
                    "PreToolUse": [
                        {"command": "python ../scripts/along_hook.py"},
                        {"command": "user_linter.sh"}
                    ]
                }
            }))
            textio.write_text(cx_hooks, json.dumps({
                "custom_key": 123,
                "hooks": {
                    "PreToolUse": [
                        {"command": "python ../scripts/along_hook.py"},
                        {"command": "custom_gate.sh"}
                    ]
                }
            }))
            textio.write_text(cr_hooks, json.dumps({
                "version": 1,
                "custom_setting": True,
                "hooks": {
                    "preToolUse": [
                        {"command": "python ../scripts/along_hook.py"},
                        {"command": "my_hook.sh"}
                    ]
                }
            }))

            purge_local_along_hooks(tmp, dry_run=False)

            self.assertTrue(os.path.exists(cl_settings))
            with open(cl_settings, "r", encoding="utf-8") as f:
                cl_data = json.load(f)
            self.assertEqual(cl_data["theme"], "dark")
            self.assertEqual(len(cl_data["hooks"]["PreToolUse"]), 1)
            self.assertEqual(cl_data["hooks"]["PreToolUse"][0]["command"], "user_linter.sh")

            self.assertTrue(os.path.exists(cx_hooks))
            with open(cx_hooks, "r", encoding="utf-8") as f:
                cx_data = json.load(f)
            self.assertEqual(cx_data["custom_key"], 123)
            self.assertEqual(len(cx_data["hooks"]["PreToolUse"]), 1)
            self.assertEqual(cx_data["hooks"]["PreToolUse"][0]["command"], "custom_gate.sh")

            self.assertTrue(os.path.exists(cr_hooks))
            with open(cr_hooks, "r", encoding="utf-8") as f:
                cr_data = json.load(f)
            self.assertEqual(cr_data["custom_setting"], True)
            self.assertEqual(len(cr_data["hooks"]["preToolUse"]), 1)
            self.assertEqual(cr_data["hooks"]["preToolUse"][0]["command"], "my_hook.sh")

    def test_along_hook_fail_open_on_non_along_workspace(self):
        """along_hook.py must exit 0 cleanly on non-Along workspaces."""
        hook_script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "along_hook.py")
        self.assertTrue(os.path.exists(hook_script))

        with tempfile.TemporaryDirectory() as empty_dir:
            cmd = [sys.executable, hook_script, "--runtime", "antigravity", "--event", "PreToolUse"]
            res = subprocess.run(cmd, cwd=empty_dir, input="", capture_output=True, text=True, timeout=5)
            self.assertEqual(res.returncode, 0, f"Must fail open with 0: {res.stderr}")

    def test_sync_constraints_empty_decisions(self):
        """sync_constraints must return empty string and not crash when no active decisions exist."""
        with hermetic.repo_fixture(prefix="test-constraints-") as tmp:
            along_dir = os.path.join(tmp, ".along")
            # Remove any seeded decisions
            dec_file = os.path.join(along_dir, "DECISIONS.md")
            dec_dir = os.path.join(along_dir, "DECISIONS")
            if os.path.isfile(dec_file):
                os.remove(dec_file)
            if os.path.isdir(dec_dir):
                shutil.rmtree(dec_dir)
            out = entities.sync_constraints(tmp)
            self.assertEqual(out, "")

    def test_textio_write_text_retries_on_transient_error(self):
        """textio.write_text retries on transient file sharing collisions."""
        with hermetic.repo_fixture(prefix="test-textio-") as tmp:
            test_file = os.path.join(tmp, "test_retry.txt")
            attempts = 0
            orig_replace = os.replace

            def flaky_replace(src, dst):
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise OSError(13, "Permission denied (simulated transient lock)")
                return orig_replace(src, dst)

            with mock.patch("os.replace", side_effect=flaky_replace):
                textio.write_text(test_file, "successful write after retry")

            self.assertEqual(attempts, 3)
            self.assertEqual(textio.read_text(test_file), "successful write after retry")

    def test_migration_purges_hooks_even_if_already_at_current_version(self):
        """migrate_protocol.py must execute Step 12 when spurious local hooks exist."""
        from scripts import migrate_protocol
        with hermetic.repo_fixture(prefix="test-mig-hooks-") as tmp:
            along_dir = os.path.join(tmp, ".along")
            os.makedirs(along_dir, exist_ok=True)
            # Record current protocol version state
            with open(os.path.join(along_dir, ".version"), "w", encoding="utf-8") as f:
                f.write(f"{migrate_protocol.CURRENT_PROTOCOL_VERSION}\n")

            # Plant spurious hooks
            ag_hooks = os.path.join(tmp, ".agents", "hooks.json")
            os.makedirs(os.path.dirname(ag_hooks), exist_ok=True)
            with open(ag_hooks, "w", encoding="utf-8") as f:
                json.dump({"along-runtime-gates": {"pre_tool": "python ../scripts/along_hook.py"}}, f)

            code = migrate_protocol.run_migrations(tmp, dry_run=False)
            self.assertEqual(code, 0)
            self.assertFalse(os.path.exists(ag_hooks), "Migration must purge .agents/hooks.json")

    def test_validate_and_build_entity_graph_ancestor_cross_reference(self):
        """validate_and_build_entity_graph resolves parent, blocked_by, and related to ancestor contexts."""
        from scripts import migrate_protocol
        with hermetic.repo_fixture(prefix="test-monorepo-") as root_dir:
            # Simulate git repo boundary at root_dir
            git_marker = os.path.join(root_dir, ".git")
            os.makedirs(git_marker, exist_ok=True)

            root_along = os.path.join(root_dir, ".along")
            root_issues = os.path.join(root_along, "ISSUES")
            root_decisions = os.path.join(root_along, "DECISIONS")
            os.makedirs(root_issues, exist_ok=True)
            os.makedirs(root_decisions, exist_ok=True)

            # Plant root issue and root decision
            textio.write_text(
                os.path.join(root_issues, "feat--root-task.md"),
                "---\nprotocol: along\nslug: root-task\ntype: feat\nstatus: in-progress\n---\n# Root Task\n"
            )
            textio.write_text(
                os.path.join(root_decisions, "ADR-2026-09-21--root-decision.md"),
                "---\nslug: root-decision\ntitle: Root Decision\nstatus: accepted\ndate: 2026-09-21\n---\n# Decision\n"
            )

            # Plant subproject with cross-context references
            sub_dir = os.path.join(root_dir, "packages", "subproject")
            sub_along = os.path.join(sub_dir, ".along")
            sub_issues = os.path.join(sub_along, "ISSUES")
            os.makedirs(sub_issues, exist_ok=True)

            textio.write_text(
                os.path.join(sub_issues, "feat--sub-task.md"),
                "---\n"
                "protocol: along\n"
                "slug: sub-task\n"
                "type: feat\n"
                "status: in-progress\n"
                "parent: root-task\n"
                "blocked_by: [feat--root-task]\n"
                "related: [decision--root-decision]\n"
                "---\n"
                "# Sub Task\n"
            )

            nodes, edges, errors, warnings = migrate_protocol.validate_and_build_entity_graph(sub_along)
            self.assertEqual(errors, [], f"Expected zero errors, got: {errors}")
            self.assertEqual(warnings, [], f"Expected zero dangling link warnings, got: {warnings}")
            self.assertIn("sub-task", nodes)

            # Now add a truly dangling link and verify warning is emitted
            textio.write_text(
                os.path.join(sub_issues, "feat--sub-task-broken.md"),
                "---\n"
                "protocol: along\n"
                "slug: sub-task-broken\n"
                "type: feat\n"
                "status: in-progress\n"
                "blocked_by: [non-existent-task]\n"
                "---\n"
                "# Broken Task\n"
            )

            nodes2, edges2, errors2, warnings2 = migrate_protocol.validate_and_build_entity_graph(sub_along)
            self.assertTrue(any("non-existent-task" in w for w in warnings2), f"Expected warning for non-existent-task: {warnings2}")


if __name__ == "__main__":
    unittest.main()
