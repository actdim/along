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
        """Global manifests must generate direct script paths without fragile python -c."""
        expanded_path = os.path.expanduser("~/.along/bin/along_hook.py")
        if sys.platform == "win32":
            expanded_path = expanded_path.replace("\\", "/")
        # Antigravity
        ag_manifest = hook_config.get_antigravity_hook_manifest(is_global=True)
        self.assertIn("along-runtime-gates", ag_manifest)
        pre_tool_cmd = ag_manifest["along-runtime-gates"]["PreToolUse"][0]["hooks"][0]["command"]
        self.assertIn("along_hook.py", pre_tool_cmd)
        self.assertIn(expanded_path, pre_tool_cmd)
        self.assertNotIn("python -c", pre_tool_cmd)
        self.assertIn("--runtime antigravity", pre_tool_cmd)

        # Claude
        claude_manifest = hook_config.get_claude_hook_manifest(is_global=True)
        self.assertIn("PreToolUse", claude_manifest)
        claude_pre = claude_manifest["PreToolUse"][0]["hooks"][0]
        self.assertEqual(claude_pre["type"], "command")
        self.assertIn("--runtime claude", claude_pre["command"])
        self.assertIn(expanded_path, claude_pre["command"])
        self.assertNotIn("python -c", claude_pre["command"])

        # Codex
        codex_manifest = hook_config.get_codex_hook_manifest(is_global=True)
        self.assertIn("hooks", codex_manifest)
        self.assertIn("PreToolUse", codex_manifest["hooks"])
        self.assertIn("--runtime codex", codex_manifest["hooks"]["PreToolUse"][0]["command"])
        self.assertIn(expanded_path, codex_manifest["hooks"]["PreToolUse"][0]["command"])
        self.assertNotIn("python -c", codex_manifest["hooks"]["PreToolUse"][0]["command"])

        # Cursor
        cursor_manifest = hook_config.get_cursor_hook_manifest(is_global=True)
        self.assertIn("hooks", cursor_manifest)
        self.assertIn("preToolUse", cursor_manifest["hooks"])
        self.assertIn("--runtime cursor", cursor_manifest["hooks"]["preToolUse"][0]["command"])
        # Verify no literal quotes wrap the script path on Windows when no spaces exist
        if sys.platform == "win32" and " " not in expanded_path:
            self.assertNotIn(f'"{expanded_path}"', pre_tool_cmd)

    def test_global_hook_command_has_no_backslashes(self):
        """Git Bash strips backslashes, so a global hook command must use forward slashes only."""
        for runtime in ("claude", "codex", "cursor", "antigravity"):
            cmd = hook_config.get_hook_command(runtime, "PreToolUse", is_global=True)
            self.assertNotIn("\\", cmd, f"{runtime} hook command contains a backslash: {cmd}")

    def test_format_hook_script_path_windows_forward_slashes(self):
        """On Windows, mixed-slash expanduser output must come back with forward slashes only."""
        from alongkit.hooks.config import _format_hook_script_path
        with mock.patch("sys.platform", "win32"):
            self.assertEqual(
                _format_hook_script_path("C:\\Users\\Admin/.along/bin/along_hook.py"),
                "C:/Users/Admin/.along/bin/along_hook.py",
            )

    @unittest.skipUnless(sys.platform == "win32", "patches ctypes.windll, which exists only on Windows")
    def test_format_hook_script_path_windows_safety(self):
        """_format_hook_script_path must omit quotes on Windows when no whitespace exists."""
        from alongkit.hooks.config import _format_hook_script_path
        with mock.patch("sys.platform", "win32"):
            # No space path
            self.assertEqual(
                _format_hook_script_path(r"C:\Users\Admin\.along\bin\along_hook.py"),
                "C:/Users/Admin/.along/bin/along_hook.py",
            )
            # Path with spaces and mock short path resolution
            with mock.patch("ctypes.windll.kernel32.GetShortPathNameW", create=True) as mock_short:
                mock_short.return_value = 1
                with mock.patch("ctypes.create_unicode_buffer") as mock_buf:
                    mock_buf.return_value.value = r"C:\Users\ADMINI~1\.along\bin\along_hook.py"
                    result = _format_hook_script_path(r"C:\Users\Admin User\.along\bin\along_hook.py")
                    self.assertEqual(result, "C:/Users/ADMINI~1/.along/bin/along_hook.py")

    def test_ensure_deps_missing_exit_code(self):
        """ensure_deps exits with missing_exit_code when deps are absent and uv cannot help."""
        from alongkit import bootstrap
        missing_venv = os.path.join(tempfile.gettempdir(), "along-no-such-venv")
        with mock.patch.object(bootstrap, "have_deps", return_value=False), \
                mock.patch.dict(os.environ, {bootstrap.VENV_ENV: missing_venv}), \
                mock.patch("shutil.which", return_value=None):
            os.environ.pop(bootstrap.GUARD_ENV, None)
            with self.assertRaises(SystemExit) as ctx:
                bootstrap.ensure_deps(missing_exit_code=0)
            self.assertEqual(ctx.exception.code, 0)
            with self.assertRaises(SystemExit) as ctx:
                bootstrap.ensure_deps()
            self.assertEqual(ctx.exception.code, 2)

    def _run_ensure_deps_capturing_reexec(self, venv_dir, which="uv", build_result=None):
        """Run ensure_deps with deps missing; return the command it re-executes."""
        from alongkit import bootstrap
        captured = {}

        def fake_reexec(command, missing_exit_code, **_kwargs):
            captured["command"] = command
            raise SystemExit(0)

        patches = [
            mock.patch.object(bootstrap, "have_deps", return_value=False),
            mock.patch.object(bootstrap, "_reexec", side_effect=fake_reexec),
            mock.patch("shutil.which", return_value=which),
            mock.patch.dict(os.environ, {bootstrap.VENV_ENV: venv_dir}),
        ]
        if build_result is not None:
            patches.append(mock.patch.object(bootstrap, "_build_venv", return_value=build_result))
        for p in patches:
            p.start()
        try:
            os.environ.pop(bootstrap.GUARD_ENV, None)
            with self.assertRaises(SystemExit):
                bootstrap.ensure_deps()
        finally:
            for p in reversed(patches):
                p.stop()
        return captured.get("command")

    def _plant_venv(self, venv_dir, specs):
        from alongkit import bootstrap
        python = bootstrap.venv_python(venv_dir)
        os.makedirs(os.path.dirname(python), exist_ok=True)
        textio.write_text(python, "")
        textio.write_text(os.path.join(venv_dir, ".along-deps"), "\n".join(specs) + "\n")
        return python

    def test_ensure_deps_reuses_cached_venv(self):
        """A current cached venv is re-executed into directly, without building or uv run."""
        from alongkit import bootstrap
        with tempfile.TemporaryDirectory() as tmp:
            venv_dir = os.path.join(tmp, "venv")
            python = self._plant_venv(venv_dir, bootstrap.RUNTIME_DEPENDENCIES)
            with mock.patch.object(bootstrap, "_build_venv") as build:
                command = self._run_ensure_deps_capturing_reexec(venv_dir)
                build.assert_not_called()
            self.assertEqual(command[0], python)

    def test_ensure_deps_rebuilds_venv_with_stale_stamp(self):
        """A venv stamped with other dependency specs is not reused."""
        from alongkit import bootstrap
        with tempfile.TemporaryDirectory() as tmp:
            venv_dir = os.path.join(tmp, "venv")
            self._plant_venv(venv_dir, ["ruamel.yaml>=0.1"])
            self.assertFalse(bootstrap._venv_is_current(venv_dir, bootstrap.RUNTIME_DEPENDENCIES))
            command = self._run_ensure_deps_capturing_reexec(venv_dir, build_result=False)
            self.assertEqual(command[1], "run", "failed rebuild must fall back to uv run")

    def test_ensure_deps_builds_venv_then_reexecs_into_it(self):
        """With uv available and no venv, ensure_deps builds the venv and re-executes into it."""
        from alongkit import bootstrap
        with tempfile.TemporaryDirectory() as tmp:
            venv_dir = os.path.join(tmp, "venv")
            command = self._run_ensure_deps_capturing_reexec(venv_dir, build_result=True)
            self.assertEqual(command[0], bootstrap.venv_python(venv_dir))

    def test_build_venv_failure_leaves_no_partial_env(self):
        """A failed build removes its temp dir and reports no current venv."""
        from alongkit import bootstrap
        with tempfile.TemporaryDirectory() as tmp:
            venv_dir = os.path.join(tmp, "venv")
            with mock.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "uv")):
                self.assertFalse(bootstrap._build_venv("uv", venv_dir, bootstrap.RUNTIME_DEPENDENCIES))
            self.assertEqual(os.listdir(tmp), [])

    def test_ensure_deps_clears_the_guard_once_deps_are_present(self):
        """The marker guards one re-exec; it must not reach the engines this process starts."""
        from alongkit import bootstrap
        with mock.patch.object(bootstrap, "have_deps", return_value=True), \
                mock.patch.dict(os.environ, {bootstrap.GUARD_ENV: "1"}):
            bootstrap.ensure_deps()
            self.assertNotIn(bootstrap.GUARD_ENV, os.environ)

    def test_a_bootstrapped_process_starts_children_without_the_guard(self):
        """End to end: a re-executed engine spawns another engine, which must see no marker.

        Before the fix an installer run from a bootstrapped process called
        `install_manifest.py` under a bare interpreter, which saw the inherited marker,
        refused to bootstrap and exited 2. See [bug--bootstrap-guard-leaks-to-children].
        """
        from alongkit import bootstrap
        scripts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")
        with tempfile.TemporaryDirectory() as tmp:
            child = os.path.join(tmp, "child.py")
            textio.write_text(child, (
                "import os\n"
                f"print(os.environ.get({bootstrap.GUARD_ENV!r}, 'absent'))\n"))
            engine = os.path.join(tmp, "engine.py")
            textio.write_text(engine, (
                "import subprocess, sys\n"
                f"sys.path.insert(0, {scripts_dir!r})\n"
                "from alongkit import bootstrap\n"
                "bootstrap.ensure_deps()\n"
                f"run = subprocess.run([sys.executable, {child!r}], capture_output=True, text=True)\n"
                "sys.stdout.write(run.stdout)\n"))
            env = dict(os.environ)
            env[bootstrap.GUARD_ENV] = "1"
            result = subprocess.run([sys.executable, engine], capture_output=True, text=True,
                                    env=env, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "absent")

    def _run_ensure_project_env(self, root, have=False, which="uv", guard=None):
        """Run ensure_project_env; return (re-exec command or None, guard passed to _reexec)."""
        from alongkit import bootstrap
        captured = {}

        def fake_reexec(command, missing_exit_code, guard=bootstrap.GUARD_ENV):
            captured["command"], captured["guard"] = command, guard
            raise SystemExit(0)

        env = {bootstrap.PROJECT_GUARD_ENV: guard} if guard else {}
        with mock.patch.object(bootstrap, "have_deps", return_value=have), \
                mock.patch.object(bootstrap, "_reexec", side_effect=fake_reexec), \
                mock.patch("shutil.which", return_value=which), \
                mock.patch.dict(os.environ, env):
            if not guard:
                os.environ.pop(bootstrap.PROJECT_GUARD_ENV, None)
            try:
                bootstrap.ensure_project_env(root, ("pydantic",))
            except SystemExit:
                pass
            guard_left = os.environ.get(bootstrap.PROJECT_GUARD_ENV)
        return captured.get("command"), captured.get("guard"), guard_left

    def test_ensure_project_env_reexecs_through_uv_project(self):
        """Missing dev modules: re-exec via `uv run --project <root>` under its own guard."""
        from alongkit import bootstrap
        with tempfile.TemporaryDirectory() as root:
            textio.write_text(os.path.join(root, "pyproject.toml"), "[project]\nname = \"x\"\n")
            command, guard, _ = self._run_ensure_project_env(root)
        self.assertIsNotNone(command)
        self.assertEqual(command[:2], ["uv", "run"])
        self.assertEqual(command[command.index("--project") + 1], root)
        self.assertEqual(guard, bootstrap.PROJECT_GUARD_ENV)

    def test_ensure_project_env_returns_when_it_cannot_or_need_not_help(self):
        """Present modules, a set guard, no uv or no pyproject: no re-exec, never an exit."""
        with tempfile.TemporaryDirectory() as root:
            self.assertIsNone(self._run_ensure_project_env(root)[0], "no pyproject.toml")
            textio.write_text(os.path.join(root, "pyproject.toml"), "[project]\nname = \"x\"\n")
            self.assertIsNone(self._run_ensure_project_env(root, which=None)[0], "no uv")
            self.assertIsNone(self._run_ensure_project_env(root, guard="1")[0], "already re-executed")
            command, _, guard_left = self._run_ensure_project_env(root, have=True, guard="1")
            self.assertIsNone(command, "modules present")
            self.assertIsNone(guard_left, "the project guard is cleared once modules are present")

    def test_along_hook_fails_open_without_deps(self):
        """along_hook.py must pass missing_exit_code=0 so a missing ruamel.yaml never blocks a tool."""
        hook_script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "along_hook.py")
        source = textio.read_text(hook_script)
        self.assertIn("ensure_deps(missing_exit_code=0,", source)


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
            self.assertTrue(os.path.exists(os.path.dirname(ag_hooks)), "Must preserve .agents dir to protect active processes")
            self.assertFalse(os.path.exists(cl_settings), "Must remove .claude/settings.json")
            self.assertTrue(os.path.exists(os.path.dirname(cl_settings)), "Must preserve .claude dir to protect active processes")
            self.assertFalse(os.path.exists(cx_hooks), "Must remove .codex/hooks.json")
            self.assertTrue(os.path.exists(os.path.dirname(cx_hooks)), "Must preserve .codex dir to protect active processes")
            self.assertFalse(os.path.exists(cr_hooks), "Must remove .cursor/hooks.json")
            self.assertTrue(os.path.exists(os.path.dirname(cr_hooks)), "Must preserve .cursor dir to protect active processes")
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

    def test_purge_local_along_hooks_recursive_subprojects(self):
        """purge_local_along_hooks with recursive=True must clean hooks across all subprojects."""
        with hermetic.repo_fixture(prefix="test-purge-rec-") as tmp:
            # Create root hook
            root_ag = os.path.join(tmp, ".agents", "hooks.json")
            os.makedirs(os.path.dirname(root_ag), exist_ok=True)
            textio.write_text(root_ag, json.dumps({"along-runtime-gates": {"pre_tool": "python foo"}}))

            # Create subproject 1 with .agents/hooks.json
            sub1 = os.path.join(tmp, "services", "auth")
            sub1_ag = os.path.join(sub1, ".agents", "hooks.json")
            sub1_proto = os.path.join(sub1, "AGENTS.md")
            os.makedirs(os.path.dirname(sub1_ag), exist_ok=True)
            textio.write_text(sub1_proto, "<!-- BEGIN ALONG-PROTOCOL ref=../../AGENTS.md -->\n<!-- END ALONG-PROTOCOL -->\n")
            textio.write_text(sub1_ag, json.dumps({"along-runtime-gates": {"pre_tool": "python bar"}}))

            # Create subproject 2 with .claude/settings.json
            sub2 = os.path.join(tmp, "packages", "core")
            sub2_cl = os.path.join(sub2, ".claude", "settings.json")
            sub2_proto = os.path.join(sub2, "AGENTS.md")
            os.makedirs(os.path.dirname(sub2_cl), exist_ok=True)
            textio.write_text(sub2_proto, "<!-- BEGIN ALONG-PROTOCOL ref=../../AGENTS.md -->\n<!-- END ALONG-PROTOCOL -->\n")
            textio.write_text(sub2_cl, json.dumps({"hooks": {"PreToolUse": [{"command": "python scripts/along_hook.py"}]}}))

            # Purge with recursive=True
            actions = purge_local_along_hooks(tmp, recursive=True, dry_run=False)
            self.assertTrue(len(actions) >= 3, f"Expected at least 3 purge actions, got {actions}")

            self.assertFalse(os.path.exists(root_ag), "Root .agents/hooks.json must be removed")
            self.assertFalse(os.path.exists(sub1_ag), "Subproject 1 .agents/hooks.json must be removed")
            self.assertFalse(os.path.exists(sub2_cl), "Subproject 2 .claude/settings.json must be removed")

    def test_along_update_context_exception_isolation(self):
        """along_update.py must isolate context failures and continue processing other contexts."""
        from scripts import along_update
        with hermetic.repo_fixture(prefix="test-update-iso-") as tmp:
            root_agents = os.path.join(tmp, "AGENTS.md")
            textio.write_text(root_agents, "<!-- BEGIN ALONG-PROTOCOL root -->\nALONG-PROTOCOL v3.8.0\n<!-- END ALONG-PROTOCOL -->\n")

            # Subproject 1: valid context
            sub1 = os.path.join(tmp, "sub1")
            os.makedirs(sub1, exist_ok=True)
            textio.write_text(os.path.join(sub1, "AGENTS.md"), "<!-- BEGIN ALONG-PROTOCOL ref=../AGENTS.md -->\n<!-- END ALONG-PROTOCOL -->\n")

            # Subproject 2: valid context
            sub2 = os.path.join(tmp, "sub2")
            os.makedirs(sub2, exist_ok=True)
            textio.write_text(os.path.join(sub2, "AGENTS.md"), "<!-- BEGIN ALONG-PROTOCOL ref=../AGENTS.md -->\n<!-- END ALONG-PROTOCOL -->\n")

            # Patch apply_migration_to_context to raise on sub1
            orig_apply = along_update.apply_migration_to_context
            def flaky_apply(ctx_dir, *args, **kwargs):
                if os.path.basename(ctx_dir) == "sub1":
                    raise OSError(22, "Simulated invalid argument on sub1")
                return orig_apply(ctx_dir, *args, **kwargs)

            with mock.patch("scripts.along_update.apply_migration_to_context", side_effect=flaky_apply):
                # Run update (should return False because sub1 failed, but sub2 must be processed)
                success = along_update.run_update(tmp, local_only=True, dry_run=False, no_hooks=True)
                self.assertFalse(success, "Update should report failure when one context fails")


if __name__ == "__main__":
    unittest.main()
