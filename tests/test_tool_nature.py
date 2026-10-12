#!/usr/bin/env python3
"""
tests/test_tool_nature.py - Unit tests for tool nature classification engine.

Tests:
1. Classification of read-only, verification, workspace-write, external, and destructive commands.
2. Compound commands taking the most dangerous class.
3. Layered overrides (repo overrides built-in).
4. along tool explain and along tool classify CLI actions.
5. Gate behavior holding unclassified tools.

Hermetic: all filesystem operations execute in temporary directories.
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

from alongkit import session
from alongkit.hooks import (
    GateDecision,
    GateResult,
    HookEngine,
    HookEvent,
    HookEventType,
    HooksConfig,
)
from alongkit.hooks import predicates, toolnature
from alongkit.hooks.toolnature import ToolClass, classify_command, classify_event


class TestToolNatureClassification(unittest.TestCase):
    """Test classification across all tool classes."""

    def test_read_only_commands_and_tools(self):
        reads = (
            "git status",
            "git log -n 5",
            "git diff HEAD~1",
            "git branch -a",
            "git tag -l",
            "gh pr list",
            "gh pr view 123",
            "kubectl get pods",
            "kubectl describe node",
            "docker ps",
            "ls -la",
            "cat README.md",
            "grep -rn foo src",
            "jq . package.json",
            "python --version",
            "python -c \"print('ok')\"",
            "along status",
            "along kb-search query",
        )
        for cmd in reads:
            with self.subTest(cmd=cmd):
                res = classify_command(cmd)
                self.assertEqual(res.tool_class, ToolClass.READ_ONLY, f"Expected {cmd} to be read-only")

        # Agent read tools
        for tool in ("view_file", "read_file", "grep_search", "find_by_name", "list_dir"):
            res = toolnature.classify_agent_tool(tool, {})
            self.assertEqual(res.tool_class, ToolClass.READ_ONLY)

    def test_verification_commands(self):
        verifications = (
            "npm test",
            "npm run test:quiet",
            "npm run build",
            "cargo test",
            "cargo build",
            "dotnet test",
            "dotnet build",
            "pytest -q",
            "python -m unittest",
            "along test",
            "along build",
            "docker build .",
            "ruff check .",
            "eslint src",
        )
        for cmd in verifications:
            with self.subTest(cmd=cmd):
                res = classify_command(cmd)
                self.assertEqual(res.tool_class, ToolClass.VERIFICATION, f"Expected {cmd} to be verification")

    def test_workspace_write_commands_and_tools(self):
        writes = (
            "git commit -m 'update'",
            "git checkout -b new-branch",
            "git add .",
            "npm install",
            "along sanitize --write",
            "kubectl apply -f deploy.yaml",
            "echo hello > out.txt",
            "cat file | grep foo > log.txt",
            "rm -rf build",
        )
        for cmd in writes:
            with self.subTest(cmd=cmd):
                res = classify_command(cmd)
                self.assertEqual(res.tool_class, ToolClass.WORKSPACE_WRITE, f"Expected {cmd} to be workspace-write")

        # Agent write tools
        for tool in ("write_to_file", "replace_file_content", "edit_file", "create_file"):
            res = toolnature.classify_agent_tool(tool, {})
            self.assertEqual(res.tool_class, ToolClass.WORKSPACE_WRITE)

    def test_external_commands(self):
        externals = (
            "gh pr merge 42",
            "gh pr create --title 'feat'",
            "gh release create v1.0",
            "git push origin main",
            "git fetch origin",
            "docker push myorg/app:latest",
            "npm publish",
            "cargo publish",
        )
        for cmd in externals:
            with self.subTest(cmd=cmd):
                res = classify_command(cmd)
                self.assertEqual(res.tool_class, ToolClass.EXTERNAL, f"Expected {cmd} to be external")

    def test_destructive_commands_and_tools(self):
        destructive = (
            "git reset --hard HEAD~1",
            "git clean -fd",
            "kubectl delete pod my-pod",
            "docker run -d myimage",
            "python -c \"import os; os.remove('file.txt')\"",
        )
        for cmd in destructive:
            with self.subTest(cmd=cmd):
                res = classify_command(cmd)
                self.assertEqual(res.tool_class, ToolClass.DESTRUCTIVE, f"Expected {cmd} to be destructive")

        # Agent destructive tools
        for tool in ("delete_file", "remove_file", "unlink", "delete"):
            res = toolnature.classify_agent_tool(tool, {})
            self.assertEqual(res.tool_class, ToolClass.DESTRUCTIVE)

    def test_env_unwrapping_and_dangerous_commands(self):
        """env wrapper should unwrap underlying command and classify correctly."""
        res_dest = classify_command("env rm -rf ~")
        self.assertEqual(res_dest.tool_class, ToolClass.DESTRUCTIVE)

        res_read = classify_command("env git status")
        self.assertEqual(res_read.tool_class, ToolClass.READ_ONLY)

        res_var = classify_command("env FOO=bar rm -rf /")
        self.assertEqual(res_var.tool_class, ToolClass.DESTRUCTIVE)

    def test_git_dangerous_configs_and_flags(self):
        """Dangerous git -c options and flags must classify as DESTRUCTIVE."""
        res_fs = classify_command("git -c core.fsmonitor='rm -rf ~' status")
        self.assertEqual(res_fs.tool_class, ToolClass.DESTRUCTIVE)

        res_pager = classify_command("git -c core.pager=evil diff")
        self.assertEqual(res_pager.tool_class, ToolClass.DESTRUCTIVE)

        res_upload = classify_command("git --upload-pack=evil fetch")
        self.assertEqual(res_upload.tool_class, ToolClass.DESTRUCTIVE)

        res_safe = classify_command("git -c user.name=test status")
        self.assertEqual(res_safe.tool_class, ToolClass.READ_ONLY)

    def test_gh_command_boundaries(self):
        """gh pr review and mutation flags must classify as EXTERNAL, not read-only."""
        res_review = classify_command("gh pr review --approve")
        self.assertEqual(res_review.tool_class, ToolClass.EXTERNAL)

        res_view = classify_command("gh pr view 123")
        self.assertEqual(res_view.tool_class, ToolClass.READ_ONLY)

        res_api_field = classify_command("gh api --field key=val repos/foo")
        self.assertEqual(res_api_field.tool_class, ToolClass.EXTERNAL)

        res_api_read = classify_command("gh api repos/foo")
        self.assertEqual(res_api_read.tool_class, ToolClass.READ_ONLY)

    def test_destructive_path_indicators(self):
        """Deletion commands targeting home, root, or wildcards must classify as DESTRUCTIVE."""
        res_home = classify_command("rm -rf ~")
        self.assertEqual(res_home.tool_class, ToolClass.DESTRUCTIVE)

        res_pwsh_home = classify_command("Remove-Item -Recurse -Force ~")
        self.assertEqual(res_pwsh_home.tool_class, ToolClass.DESTRUCTIVE)

        res_local = classify_command("rm temp.txt")
        self.assertEqual(res_local.tool_class, ToolClass.WORKSPACE_WRITE)

    def test_repo_rules_cannot_downgrade_dangerous_commands(self):
        """Repository tool rules cannot downgrade built-in destructive or external commands to read-only."""
        tmp = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(tmp, ".along"), exist_ok=True)
            rules_path = os.path.join(tmp, ".along", "tool_rules.yaml")
            with open(rules_path, "w", encoding="utf-8") as f:
                f.write(
                    "rules:\n"
                    "  - pattern: 'rm -rf ~'\n"
                    "    class: read-only\n"
                    "    description: 'Downgraded rm'\n"
                )
            res = classify_command("rm -rf ~", repo_root=tmp)
            self.assertEqual(res.tool_class, ToolClass.DESTRUCTIVE)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestCompoundCommands(unittest.TestCase):
    """Test compound shell commands taking the most dangerous class."""

    def test_compound_danger_hierarchy(self):
        # read-only + verification -> verification
        res = classify_command("git status && pytest -q")
        self.assertEqual(res.tool_class, ToolClass.VERIFICATION)

        # verification + workspace-write -> workspace-write
        res = classify_command("npm run build && git commit -m 'build'")
        self.assertEqual(res.tool_class, ToolClass.WORKSPACE_WRITE)

        # workspace-write + external -> external
        res = classify_command("git commit -m 'release' && git push origin main")
        self.assertEqual(res.tool_class, ToolClass.EXTERNAL)

        # read-only + destructive -> destructive
        res = classify_command("git status && git reset --hard")
        self.assertEqual(res.tool_class, ToolClass.DESTRUCTIVE)

    def test_compound_with_unknown_tool_is_unknown(self):
        # If any segment is unclassified, compound command holds as unknown
        res = classify_command("git status && my_custom_unclassified_tool --arg")
        self.assertEqual(res.tool_class, ToolClass.UNKNOWN)
        self.assertIn("my_custom_unclassified_tool", res.unclassified_pattern)

    def test_redirection_escalation(self):
        # Even a read-only command becomes workspace-write when output redirects to a file
        res = classify_command("git status > status.txt")
        self.assertEqual(res.tool_class, ToolClass.WORKSPACE_WRITE)


class TestLayeredOverrides(unittest.TestCase):
    """Test that repository rules override built-in rules (nearest wins)."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="along-toolnature-")
        os.makedirs(os.path.join(self.temp_dir, ".along", "rules"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_repo_override_builtin(self):
        # Built-in: gh pr merge is external
        builtin_res = classify_command("gh pr merge")
        self.assertEqual(builtin_res.tool_class, ToolClass.EXTERNAL)

        # Override in repo gates.yaml
        gates_yaml = os.path.join(self.temp_dir, ".along", "rules", "gates.yaml")
        content = (
            "version: 1\n"
            "tools:\n"
            "  gh:\n"
            "    rules:\n"
            "      - match: { subcommand: 'pr merge' }\n"
            "        class: workspace-write\n"
        )
        with open(gates_yaml, "w", encoding="utf-8") as f:
            f.write(content)

        # Now gh pr merge resolves to workspace-write with layer=repo
        repo_res = classify_command("gh pr merge", repo_root=self.temp_dir)
        self.assertEqual(repo_res.tool_class, ToolClass.WORKSPACE_WRITE)
        self.assertEqual(repo_res.layer, "repo")

        # Unmodified rules still fall back to built-in layer
        fallback_res = classify_command("gh pr list", repo_root=self.temp_dir)
        self.assertEqual(fallback_res.tool_class, ToolClass.READ_ONLY)
        self.assertEqual(fallback_res.layer, "builtin")


class TestToolCliActions(unittest.TestCase):
    """Test along tool explain and along tool classify."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="along-toolcli-")
        os.makedirs(os.path.join(self.temp_dir, ".along", "rules"), exist_ok=True)
        # Create minimal gates.yaml
        with open(os.path.join(self.temp_dir, ".along", "rules", "gates.yaml"), "w", encoding="utf-8") as f:
            f.write("version: 1\n")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_tool_explain(self):
        exp = toolnature.explain_command("git status", repo_root=self.temp_dir)
        self.assertIn("Command: git status", exp)
        self.assertIn("Class:   read-only", exp)

        exp_compound = toolnature.explain_command("git status && rm -rf src", repo_root=self.temp_dir)
        self.assertIn("Segments:", exp_compound)
        self.assertIn("workspace-write", exp_compound)

    def test_tool_classify_repo(self):
        # Classify custom tool default
        msg = toolnature.classify_tool("customcli", "read-only", repo_root=self.temp_dir)
        self.assertIn("Classified 'customcli' as 'read-only'", msg)

        res = classify_command("customcli", repo_root=self.temp_dir)
        self.assertEqual(res.tool_class, ToolClass.READ_ONLY)
        self.assertEqual(res.layer, "repo")

        # Classify subcommands
        toolnature.classify_tool("customcli deploy", "external", repo_root=self.temp_dir)
        res_sub = classify_command("customcli deploy", repo_root=self.temp_dir)
        self.assertEqual(res_sub.tool_class, ToolClass.EXTERNAL)

        # Base still read-only
        res_base = classify_command("customcli", repo_root=self.temp_dir)
        self.assertEqual(res_base.tool_class, ToolClass.READ_ONLY)


class TestGateHoldingUnclassified(unittest.TestCase):
    """Test that require_plan_approval gate holds unclassified tools with reason to ask user."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="along-gate-unclass-")
        os.makedirs(os.path.join(self.temp_dir, ".along", "ISSUES"), exist_ok=True)
        os.makedirs(os.path.join(self.temp_dir, ".along", ".session"), exist_ok=True)
        session.set_session_phase(self.temp_dir, "inquiry", plan_approved=False)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_unclassified_shell_command_holds_with_classify_prompt(self):
        cmd = "unclassified_binary --do-something"
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": cmd},
            workspace_root=self.temp_dir,
            runtime="generic",
        )
        options = {"enforce_unbound": True}
        result = predicates.check_mutation_authorization(event, self.temp_dir, options=options)
        self.assertIsInstance(result, str)
        self.assertIn("Unclassified Tool Nature", result)
        self.assertIn("along tool classify \"unclassified_binary\" <class>", result)

    def test_unclassified_agent_tool_holds(self):
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="unknown_mcp_custom_tool",
            tool_args={"target": "database"},
            workspace_root=self.temp_dir,
            runtime="antigravity",
        )
        options = {"enforce_unbound": True}
        result = predicates.check_mutation_authorization(event, self.temp_dir, options=options)
        self.assertIsInstance(result, GateResult)
        self.assertEqual(result.decision, GateDecision.ASK)
        self.assertIn("Unclassified Tool Nature", result.reason or "")

    def test_classified_tool_passes_after_user_classification(self):
        tool = "my_safe_inspector"
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name=tool,
            tool_args={},
            workspace_root=self.temp_dir,
            runtime="generic",
        )
        options = {"enforce_unbound": True}

        # Held before classification
        before = predicates.check_mutation_authorization(event, self.temp_dir, options=options)
        self.assertIsNotNone(before)
        self.assertIn("Unclassified Tool Nature", before)

        # User classifies as read-only
        toolnature.classify_tool(tool, "read-only", repo_root=self.temp_dir)

        # Allowed after classification in inquiry phase
        after = predicates.check_mutation_authorization(event, self.temp_dir, options=options)
        self.assertIsNone(after)


if __name__ == "__main__":
    unittest.main()
