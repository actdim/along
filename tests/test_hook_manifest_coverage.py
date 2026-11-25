#!/usr/bin/env python3
"""
tests/test_hook_manifest_coverage.py - Hermetic manifest superset, payload, and doctor coverage tests.

Regression suite for [bug--antigravity-manifest-matcher-unenforceable-invariants]:
- REQ-1: Each runtime manifest matcher MUST be a superset of the union of `tools:`
  across every catalogue gate whose `enforcement` includes `runtime`.
- REQ-2: A hermetic test derives that union from `default_gates.yaml` and asserts
  the superset relation for every installed runtime, failing if a new gate names a
  tool absent from an installed matcher.
- REQ-3: Payload-level subprocess tests feed `view_file` of a credential path and
  `delete_file` of an issue file through `along_hook.py --runtime antigravity`
  (plus sibling runtimes Cursor, Codex, Claude, DSH) and assert the gates fire.
- REQ-4: Cursor's runtime narrowing is recorded explicitly and reported by `along doctor`.
"""

from __future__ import annotations

import json
import os
import re
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
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

import hermetic
from alongkit import proc, runtime, textio
from alongkit.hooks import (
    audit_installed_hook_manifests,
    audit_manifest_coverage,
    get_antigravity_hook_manifest,
    get_claude_hook_manifest,
    get_codex_hook_manifest,
    get_cursor_hook_manifest,
    get_dsh_hook_manifest,
    get_runtime_hook_narrowing,
    install_antigravity_hooks,
    install_claude_hooks,
    install_codex_hooks,
    install_cursor_hooks,
    install_dsh_hooks,
    runtime_gate_tool_union,
)
from alongkit.hooks.adapters.normalize import SHELL_TOOLS, WRITE_TOOLS
from alongkit.hooks.declarative import DEFAULT_GATES_FILE, load_gate_definitions

_HOOK_SCRIPT = os.path.join(SCRIPTS_DIR, "along_hook.py")
_EXEC_SCRIPT = os.path.join(SCRIPTS_DIR, "along_exec.py")


def _hmc_catalogue_runtime_union(gates_path: str) -> set:
    tools = set()
    for defn in load_gate_definitions(gates_path):
        if defn.enabled and "runtime" in defn.enforcement:
            tools.update(defn.tools)
    return tools


def _hmc_matcher_tokens(pattern: str) -> set:
    return {tok.strip() for tok in pattern.split("|") if tok.strip()}


def _hmc_antigravity_dispatches(manifest: dict, tool_name: str) -> bool:
    pre = manifest["along-runtime-gates"]["PreToolUse"][0]
    matcher = pre.get("matcher")
    if matcher is None:
        return True
    return tool_name in _hmc_matcher_tokens(matcher) or re.fullmatch(matcher, tool_name) is not None


class TestRuntimeGateUnionAndManifestCoverage(unittest.TestCase):
    """REQ-1 & REQ-2: Manifest matchers cover the full default_gates.yaml runtime union."""

    def test_catalogue_union_includes_invariant_read_and_delete_tools(self):
        union = set(runtime_gate_tool_union())
        expected = _hmc_catalogue_runtime_union(DEFAULT_GATES_FILE)
        self.assertEqual(union, expected)
        for required in (
            "view_file", "read_file", "view_image", "list_dir", "list_directory",
            "grep_search", "grep", "find_by_name", "find_files", "file_search",
            "delete_file", "remove_file", "unlink", "delete", "file_delete", "remove",
            "write_to_file", "write_file", "replace_file_content", "edit_file",
            "patch_file", "create_file", "run_command", "execute_command", "bash", "shell",
            "invoke_subagent", "spawn_subagent", "Task", "send_message", "manage_task",
        ):
            self.assertIn(required, union)

    def test_antigravity_manifest_is_superset_of_catalogue_union(self):
        union = _hmc_catalogue_runtime_union(DEFAULT_GATES_FILE)
        manifest = get_antigravity_hook_manifest(is_global=True)
        pre_matcher = manifest["along-runtime-gates"]["PreToolUse"][0]["matcher"]
        pre_tokens = _hmc_matcher_tokens(pre_matcher)
        self.assertTrue(
            union <= pre_tokens,
            f"Antigravity PreToolUse matcher missing tools: {sorted(union - pre_tokens)}",
        )
        post_matcher = manifest["along-runtime-gates"]["PostToolUse"][0]["matcher"]
        post_tokens = _hmc_matcher_tokens(post_matcher)
        expected_post = set(WRITE_TOOLS) | set(SHELL_TOOLS)
        self.assertTrue(
            expected_post <= post_tokens,
            f"Antigravity PostToolUse matcher missing write/shell tools: {sorted(expected_post - post_tokens)}",
        )

    def test_every_installed_runtime_manifest_is_superset_of_catalogue_union(self):
        for rt in ("antigravity", "claude", "codex", "cursor", "dsh", "opencode"):
            with self.subTest(runtime=rt):
                audit = audit_manifest_coverage(rt)
                self.assertTrue(audit["has_hook"], f"{rt} has no PreToolUse hook")
                self.assertEqual(audit["missing_tools"], [], f"{rt} missing gate tools: {audit['missing_tools']}")
                self.assertEqual(audit["unmatched_aliases"], [], f"{rt} unmatched aliases: {audit['unmatched_aliases']}")
                self.assertTrue(audit["is_superset"], f"{rt} manifest audit failed: {audit}")

    def test_adding_new_gate_tool_fails_stale_installed_matchers(self):
        """REQ-2: A new runtime gate tool absent from an installed matcher must fail audit."""
        with tempfile.TemporaryDirectory() as tmp:
            custom_yaml = os.path.join(tmp, "default_gates.yaml")
            base_text = textio.read_text(DEFAULT_GATES_FILE, strict=False)
            extra_gate = (
                "\n  - id: synthetic_vault_guard\n"
                "    profiles:\n"
                "      strict: block\n"
                "      standard: block\n"
                "      light: block\n"
                "    enforcement: [runtime]\n"
                "    title: \"Synthetic Vault Guard\"\n"
                "    description: \"Test gate adding a novel tool\"\n"
                "    event: PreToolUse\n"
                "    tools: [synthetic_vault_read]\n"
                "    rule:\n"
                "      type: predicate\n"
                "      handler: alongkit.hooks.predicates.check_workspace_containment\n"
                "      error: \"Denied.\"\n"
            )
            textio.write_text(custom_yaml, base_text + extra_gate)

            stale_manifests = {
                "antigravity": get_antigravity_hook_manifest(),
                "claude": get_claude_hook_manifest(),
                "codex": get_codex_hook_manifest(),
                "cursor": get_cursor_hook_manifest(),
                "dsh": get_dsh_hook_manifest(),
            }
            for rt, manifest in stale_manifests.items():
                with self.subTest(runtime=rt):
                    audit = audit_manifest_coverage(rt, manifest=manifest, gates_file=custom_yaml)
                    self.assertFalse(audit["is_superset"], f"{rt} falsely passed with missing new gate tool")
                    self.assertIn("synthetic_vault_read", audit["missing_tools"])

            # Installing manifests onto disk and auditing against the expanded catalogue catches all 5
            repo_dir = os.path.join(tmp, "repo")
            os.makedirs(os.path.join(repo_dir, ".along", "ISSUES"), exist_ok=True)
            home_dir = os.path.join(tmp, "home")
            os.makedirs(home_dir, exist_ok=True)
            with mock.patch.dict(os.environ, {"HOME": home_dir, "USERPROFILE": home_dir}):
                install_antigravity_hooks(repo_root=repo_dir)
                install_claude_hooks(repo_root=repo_dir)
                install_codex_hooks(repo_root=repo_dir)
                install_cursor_hooks(repo_root=repo_dir)
                install_dsh_hooks(repo_root=repo_dir)

                audits = audit_installed_hook_manifests(repo_root=repo_dir, gates_file=custom_yaml)
                self.assertEqual(len(audits), 5)
                for item in audits:
                    self.assertFalse(item["is_superset"])
                    self.assertIn("synthetic_vault_read", item["missing_tools"])


class TestAntigravityPayloadEnforcement(unittest.TestCase):
    """REQ-3: Payload-level verification through along_hook.py --runtime antigravity."""

    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="along-ag-payload-"))
        self.home = os.path.join(self.base, "home")
        self.ws = os.path.join(self.base, "ws")
        self.tmp = os.path.join(self.base, "tmp")
        os.makedirs(os.path.join(self.home, ".ssh"), exist_ok=True)
        os.makedirs(os.path.join(self.home, ".aws"), exist_ok=True)
        os.makedirs(os.path.join(self.ws, ".along", "ISSUES"), exist_ok=True)
        os.makedirs(os.path.join(self.ws, "src"), exist_ok=True)
        os.makedirs(self.tmp, exist_ok=True)
        textio.write_text(os.path.join(self.home, ".ssh", "id_ed25519"), "PRIVATE KEY\n")
        textio.write_text(os.path.join(self.home, ".aws", "credentials"), "[default]\n")
        textio.write_text(
            os.path.join(self.ws, ".along", "ISSUES", "bug--sample.md"),
            "---\nslug: sample\ntype: bug\nstatus: open\n---\n\n# Sample\n",
        )
        textio.write_text(os.path.join(self.ws, "src", "app.py"), "x = 1\n")

        self.env = hermetic.isolated_home_env()
        self.env["HOME"] = self.home
        self.env["USERPROFILE"] = self.home
        self.env["TMP"] = self.tmp
        self.env["TEMP"] = self.tmp
        self.env["TMPDIR"] = self.tmp
        self.env.pop("ALONG_AUTONOMOUS", None)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def _run_ag(self, tool_name: str, args: dict) -> dict:
        manifest = get_antigravity_hook_manifest(is_global=True)
        self.assertTrue(
            _hmc_antigravity_dispatches(manifest, tool_name),
            f"Antigravity manifest matcher would never dispatch {tool_name}",
        )
        payload = {
            "toolCall": {"name": tool_name, "args": args},
            "workspacePaths": [self.ws],
            "conversationId": "conv-ag-payload",
            "stepIdx": 1,
        }
        res = subprocess.run(
            [sys.executable, _HOOK_SCRIPT, "--runtime", "antigravity", "--event", "PreToolUse"],
            input=json.dumps(payload).encode("utf-8"),
            capture_output=True,
            env=self.env,
            cwd=self.ws,
            timeout=60,
        )
        self.assertEqual(res.returncode, 0, res.stderr.decode("utf-8", errors="replace"))
        return json.loads(res.stdout.decode("utf-8"))

    def test_view_file_credential_tilde_path_is_denied(self):
        out = self._run_ag("view_file", {"AbsolutePath": "~/.ssh/id_ed25519"})
        self.assertEqual(out["decision"], "deny")
        self.assertIn("workspace-containment", out["reason"])
        self.assertIn("credential store", out["reason"])

    def test_view_file_credential_expanded_path_is_denied(self):
        key_path = os.path.join(self.home, ".ssh", "id_ed25519")
        out = self._run_ag("view_file", {"file_path": key_path})
        self.assertEqual(out["decision"], "deny")
        self.assertIn("workspace-containment", out["reason"])
        self.assertIn("credential store", out["reason"])

    def test_read_file_aws_credentials_is_denied(self):
        out = self._run_ag("read_file", {"TargetFile": "~/.aws/credentials"})
        self.assertEqual(out["decision"], "deny")
        self.assertIn("workspace-containment", out["reason"])

    def test_view_file_inside_workspace_is_allowed(self):
        out = self._run_ag("view_file", {"AbsolutePath": os.path.join(self.ws, "src", "app.py")})
        self.assertEqual(out["decision"], "allow")

    def test_delete_file_issue_is_denied(self):
        for key in ("TargetFile", "AbsolutePath", "file_path"):
            with self.subTest(arg_key=key):
                out = self._run_ag("delete_file", {key: ".along/ISSUES/bug--sample.md"})
                self.assertEqual(out["decision"], "deny")
                self.assertIn("entity-deletion-protection", out["reason"])

    def test_delete_file_non_entity_is_allowed(self):
        out = self._run_ag("delete_file", {"TargetFile": "src/temp_unused.py"})
        self.assertEqual(out["decision"], "allow")

    def test_oversized_invoke_subagent_is_denied(self):
        out = self._run_ag("invoke_subagent", {"Prompt": "x" * 35000})
        self.assertEqual(out["decision"], "deny")
        self.assertIn("bounded-prompt-gate", out["reason"])


class TestSiblingRuntimePayloadsAndAdapters(unittest.TestCase):
    """Verify Cursor, Codex, Claude, and DSH adapters and hook execution on new matcher tools."""

    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="along-rt-payload-"))
        self.home = os.path.join(self.base, "home")
        self.ws = os.path.join(self.base, "ws")
        self.tmp = os.path.join(self.base, "tmp")
        os.makedirs(os.path.join(self.home, ".ssh"), exist_ok=True)
        os.makedirs(os.path.join(self.ws, ".along", "ISSUES"), exist_ok=True)
        os.makedirs(os.path.join(self.ws, "src"), exist_ok=True)
        os.makedirs(self.tmp, exist_ok=True)
        textio.write_text(os.path.join(self.home, ".ssh", "id_ed25519"), "PRIVATE KEY\n")
        textio.write_text(
            os.path.join(self.ws, ".along", "ISSUES", "bug--sample.md"),
            "---\nslug: sample\ntype: bug\nstatus: open\n---\n\n# Sample\n",
        )
        textio.write_text(os.path.join(self.ws, ".along", "ISSUES.md"), "# Active Issues\n")
        textio.write_text(os.path.join(self.ws, "src", "app.py"), "x = 1\n")

        self.env = hermetic.isolated_home_env()
        self.env["HOME"] = self.home
        self.env["USERPROFILE"] = self.home
        self.env["TMP"] = self.tmp
        self.env["TEMP"] = self.tmp
        self.env["TMPDIR"] = self.tmp
        self.env.pop("ALONG_AUTONOMOUS", None)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def _invoke(self, rt: str, payload: dict) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, _HOOK_SCRIPT, "--runtime", rt, "--event", "PreToolUse"],
            input=json.dumps(payload).encode("utf-8"),
            capture_output=True,
            env=self.env,
            cwd=self.ws,
            timeout=60,
        )

    def test_cursor_native_tool_names_enforce_gates_without_unmapped_noise(self):
        # Shell force-push denied
        res_shell = self._invoke("cursor", {
            "hook_event_name": "preToolUse",
            "tool_name": "Shell",
            "tool_input": {"command": "git push --force"},
            "workspace_roots": [self.ws],
        })
        self.assertEqual(res_shell.returncode, 2)
        self.assertIn("destructive-command", res_shell.stderr.decode("utf-8"))

        # Read credential store denied
        res_read = self._invoke("cursor", {
            "hook_event_name": "preToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "~/.ssh/id_ed25519"},
            "workspace_roots": [self.ws],
        })
        self.assertEqual(res_read.returncode, 2)
        self.assertIn("workspace-containment", res_read.stderr.decode("utf-8"))

        # Delete issue file denied
        res_del = self._invoke("cursor", {
            "hook_event_name": "preToolUse",
            "tool_name": "Delete",
            "tool_input": {"path": ".along/ISSUES/bug--sample.md"},
            "workspace_roots": [self.ws],
        })
        self.assertEqual(res_del.returncode, 2)
        self.assertIn("entity-deletion-protection", res_del.stderr.decode("utf-8"))

        # StrReplace on projection denied
        res_edit = self._invoke("cursor", {
            "hook_event_name": "preToolUse",
            "tool_name": "StrReplace",
            "tool_input": {"file_path": ".along/ISSUES.md", "new_string": "# fake"},
            "workspace_roots": [self.ws],
        })
        self.assertEqual(res_edit.returncode, 2)
        self.assertIn("Projection", res_edit.stderr.decode("utf-8"))

        # Workspace LS / Grep / Glob allowed and never audited as unmapped_tool
        for tool, args in (
            ("LS", {"path": self.ws}),
            ("Grep", {"path": os.path.join(self.ws, "src"), "pattern": "x"}),
            ("Glob", {"path": self.ws, "pattern": "**/*.py"}),
        ):
            res_ok = self._invoke("cursor", {
                "hook_event_name": "preToolUse",
                "tool_name": tool,
                "tool_input": args,
                "workspace_roots": [self.ws],
            })
            self.assertEqual(res_ok.returncode, 0, res_ok.stderr.decode("utf-8"))

        audit_file = os.path.join(self.ws, ".along", "diagnostics", "hooks_audit.jsonl")
        if os.path.isfile(audit_file):
            entries = [json.loads(line) for line in textio.read_text(audit_file).splitlines() if line.strip()]
            self.assertFalse(any(e.get("gate") == "unmapped_tool" for e in entries), entries)

    def test_codex_read_and_delete_payloads_denied(self):
        res_read = self._invoke("codex", {
            "hook_event_name": "PreToolUse",
            "tool_name": "read_file",
            "tool_input": {"file_path": "~/.ssh/id_ed25519"},
            "cwd": self.ws,
        })
        self.assertEqual(res_read.returncode, 2)
        self.assertIn("workspace-containment", res_read.stderr.decode("utf-8"))

        res_del = self._invoke("codex", {
            "hook_event_name": "PreToolUse",
            "tool_name": "delete_file",
            "tool_input": {"file_path": ".along/ISSUES/bug--sample.md"},
            "cwd": self.ws,
        })
        self.assertEqual(res_del.returncode, 2)
        self.assertIn("entity-deletion-protection", res_del.stderr.decode("utf-8"))

    def test_claude_ls_and_agent_payloads_enforced(self):
        res_ls = self._invoke("claude", {
            "hook_event_name": "PreToolUse",
            "tool_name": "LS",
            "tool_input": {"path": "~/.ssh"},
            "cwd": self.ws,
        })
        self.assertEqual(res_ls.returncode, 2)
        self.assertIn("workspace-containment", res_ls.stderr.decode("utf-8"))

        res_agent = self._invoke("claude", {
            "hook_event_name": "PreToolUse",
            "tool_name": "Agent",
            "tool_input": {"prompt": "a" * 35000},
            "cwd": self.ws,
        })
        self.assertEqual(res_agent.returncode, 2)
        self.assertIn("bounded-prompt-gate", res_agent.stderr.decode("utf-8"))

    def test_dsh_delete_and_list_payloads_enforced(self):
        res_del = self._invoke("dsh", {
            "hook_event_name": "PreToolUse",
            "tool_name": "delete_file",
            "tool_input": {"file_path": ".along/ISSUES/bug--sample.md"},
            "cwd": self.ws,
        })
        self.assertEqual(res_del.returncode, 2)
        self.assertIn("entity-deletion-protection", res_del.stderr.decode("utf-8"))


class TestDoctorManifestAndCursorNarrowing(unittest.TestCase):
    """REQ-4: Stale narrow matchers and Cursor's narrowing are reported by along doctor."""

    def setUp(self):
        self.repo = hermetic.make_repo_fixture(prefix="along-doc-narrow-")
        self.home = tempfile.mkdtemp(prefix="along-doc-home-")
        self.env = hermetic.isolated_home_env()
        self.env["HOME"] = self.home
        self.env["USERPROFILE"] = self.home

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)
        shutil.rmtree(self.home, ignore_errors=True)

    def _run_doctor(self, agent: str = "antigravity") -> str:
        env = dict(self.env)
        env["ALONG_AGENT"] = agent
        res = proc.run_capture([sys.executable, _EXEC_SCRIPT, "doctor"], cwd=self.repo, env=env)
        return res.stdout

    def test_doctor_warns_on_stale_three_tool_antigravity_manifest(self):
        gemini_cfg = os.path.join(self.home, ".gemini", "config")
        os.makedirs(gemini_cfg, exist_ok=True)
        hooks_path = os.path.join(gemini_cfg, "hooks.json")
        textio.write_text(hooks_path, json.dumps({
            "along-runtime-gates": {
                "PreToolUse": [{
                    "matcher": "write_to_file|replace_file_content|run_command",
                    "hooks": [{"type": "command", "command": "python ~/.along/bin/along_hook.py --runtime antigravity --event PreToolUse"}],
                }]
            }
        }, indent=2))
        out = self._run_doctor("antigravity")
        self.assertIn("excludes", out)
        self.assertIn("runtime gate tool(s)", out)
        self.assertIn("along hook install --runtime antigravity --global", out)

    def test_doctor_clean_after_installing_updated_antigravity_manifest(self):
        install_antigravity_hooks(is_global=True, target_home=os.path.join(self.home, ".gemini", "config"))
        out = self._run_doctor("antigravity")
        self.assertNotIn("excludes", out)
        self.assertNotIn("Runtime hook narrowing", out)

    def test_doctor_reports_cursor_narrowing(self):
        narrow = get_runtime_hook_narrowing("cursor")
        self.assertIsNotNone(narrow)
        self.assertIn("view_image", narrow["unexpressible_tools"])
        self.assertIn("cursor", runtime.RUNTIME_MATRIX)
        self.assertIn("unexpressible_tools", runtime.RUNTIME_MATRIX["cursor"])

        out = self._run_doctor("cursor")
        self.assertIn("Runtime hook narrowing (cursor)", out)
        self.assertIn("view_image", out)
        self.assertIn("send_message", out)
        self.assertIn("spawn_subagent", out)

    def test_doctor_warns_on_legacy_cursor_manifest_without_matcher(self):
        cursor_dir = os.path.join(self.repo, ".cursor")
        os.makedirs(cursor_dir, exist_ok=True)
        textio.write_text(os.path.join(cursor_dir, "hooks.json"), json.dumps({
            "version": 1,
            "hooks": {
                "preToolUse": [{"command": "python scripts/along_hook.py --runtime cursor --event PreToolUse"}],
                "postToolUse": [{"command": "python scripts/along_hook.py --runtime cursor --event PostToolUse"}],
                "stop": [{"command": "python scripts/along_hook.py --runtime cursor --event Stop"}],
            },
        }))
        out = self._run_doctor("antigravity")
        self.assertIn("has no preToolUse matcher", out)
        self.assertIn("Runtime hook narrowing (cursor)", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
