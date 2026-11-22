#!/usr/bin/env python3
"""
tests/test_session_hierarchy.py - Unit tests for umbrella session hierarchy and submodule automation.

Covers requirements from feat--session-hierarchy-and-submodule-automation:
- REQ-1: Umbrella session inheritance across subprojects via children:.
- REQ-2: Smart dirty tree handling on along start for issue-owned changes.
- REQ-3: Submodule protocol auto-commit with chore(along): protocol vX.Y.Z and gate exemption.
- REQ-4: Merge driver change transparency and rationale logging in along update.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import entities, gitgates, lifecycle, proc, repo, session, textio
from alongkit.commands import lifecycle as lifecycle_cmd
from alongkit.hooks import predicates
from alongkit.hooks.models import HookEvent, HookEventType


def _load_local_along_update():
    path = os.path.join(SCRIPTS_DIR, "along_update.py")
    spec = importlib.util.spec_from_file_location("local_along_update_module", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestSessionHierarchyAndSubmoduleAutomation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="along-hierarchy-test-")
        proc.run_capture(["git", "init", "-q"], cwd=self.tmp)
        proc.run_capture(["git", "config", "user.name", "Along Tester"], cwd=self.tmp)
        proc.run_capture(["git", "config", "user.email", "tester@actdim.local"], cwd=self.tmp)
        self.state_dir = os.path.join(self.tmp, ".along")
        os.makedirs(os.path.join(self.state_dir, "ISSUES"), exist_ok=True)
        os.makedirs(os.path.join(self.state_dir, "ISSUES", "done"), exist_ok=True)
        os.makedirs(os.path.join(self.state_dir, ".session"), exist_ok=True)
        with open(os.path.join(self.state_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"protocol_version": "4.9.1"}, f)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_umbrella_session_inheritance_permits_subproject_edits(self):
        """REQ-1: A session bound to an umbrella issue permits editing files in declared child subprojects."""
        # Create a subproject with its own .along/
        sub_dir = os.path.join(self.tmp, "packages", "app-core")
        sub_along = os.path.join(sub_dir, ".along")
        os.makedirs(os.path.join(sub_along, "ISSUES"), exist_ok=True)
        with open(os.path.join(sub_along, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"protocol_version": "4.9.1"}, f)

        # Create child issue in subproject
        child_file = os.path.join(sub_along, "ISSUES", "task--child-setup.md")
        child_content = (
            "---\n"
            "protocol: along\n"
            "protocol_version: '4.9.1'\n"
            "slug: child-setup\n"
            "type: task\n"
            "status: open\n"
            "---\n\n"
            "# Child Setup Task\n"
        )
        textio.write_text(child_file, child_content, newline="\n")

        # Create root umbrella issue declaring child in subproject
        umbrella_slug = "root-umbrella"
        umbrella_file = os.path.join(self.state_dir, "ISSUES", f"feat--{umbrella_slug}.md")
        umbrella_content = (
            "---\n"
            "protocol: along\n"
            "protocol_version: '4.9.1'\n"
            f"slug: {umbrella_slug}\n"
            "type: feat\n"
            "status: in-progress\n"
            "children:\n"
            "  - 'packages/app-core:task--child-setup'\n"
            "---\n\n"
            "# Root Umbrella Feature\n"
        )
        textio.write_text(umbrella_file, umbrella_content, newline="\n")

        # Bind session to the umbrella issue
        key = "antigravity--test-umbrella-session"
        session.bind_session(self.tmp, umbrella_slug, key=key)

        # Create edit event for target inside subproject
        target_file = os.path.join(sub_dir, "src", "index.ts")
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="edit_file",
            tool_args={"TargetFile": target_file, "file_path": target_file, "Target": "old", "Replacement": "new"},
            workspace_root=self.tmp,
            runtime="antigravity",
            conversation_id="test-umbrella-session",
        )

        # Boundary check must pass without rejection
        violation = predicates.check_subproject_boundary(event, self.tmp)
        self.assertIsNone(violation, f"Expected no violation, got: {violation}")

        # Also test with short folder qualifier (e.g. 'app-core:task--child-setup')
        short_umbrella_content = (
            "---\n"
            "protocol: along\n"
            "protocol_version: '4.9.1'\n"
            f"slug: {umbrella_slug}\n"
            "type: feat\n"
            "status: in-progress\n"
            "children:\n"
            "  - 'app-core:task--child-setup'\n"
            "---\n\n"
            "# Root Umbrella Feature\n"
        )
        textio.write_text(umbrella_file, short_umbrella_content, newline="\n")
        violation_short = predicates.check_subproject_boundary(event, self.tmp)
        self.assertIsNone(violation_short, f"Expected no violation with short qualifier, got: {violation_short}")

        # Conversely, if subproject child is not declared, it must report a subproject-boundary violation
        unrelated_umbrella = (
            "---\n"
            "protocol: along\n"
            "protocol_version: '4.9.1'\n"
            f"slug: {umbrella_slug}\n"
            "type: feat\n"
            "status: in-progress\n"
            "children:\n"
            "  - 'other-submod:task--other'\n"
            "---\n\n"
            "# Root Umbrella Feature\n"
        )
        textio.write_text(umbrella_file, unrelated_umbrella, newline="\n")
        violation_unrelated = predicates.check_subproject_boundary(event, self.tmp)
        self.assertIsNotNone(violation_unrelated)
        self.assertIn("Subproject Boundary Violation", violation_unrelated)

    def test_smart_dirty_tree_handling_permits_issue_owned_modifications(self):
        """REQ-2: along start allows dirty tree without --allow-dirty when dirty files belong to the issue."""
        slug = "dirty-test-issue"
        issue_file = os.path.join(self.state_dir, "ISSUES", f"task--{slug}.md")
        content = (
            "---\n"
            "protocol: along\n"
            "protocol_version: '4.9.1'\n"
            f"slug: {slug}\n"
            "type: task\n"
            "status: open\n"
            "---\n\n"
            "# Dirty Test Issue\n"
        )
        textio.write_text(issue_file, content, newline="\n")

        # Initial commit in repo so git status works
        textio.write_text(os.path.join(self.tmp, "README.md"), "# Init", newline="\n")
        proc.run_capture(["git", "add", "README.md", f".along/ISSUES/task--{slug}.md"], cwd=self.tmp)
        proc.run_capture(["git", "commit", "-m", "chore(along): protocol v4.9.1"], cwd=self.tmp)

        # Create uncommitted dirty file that belongs to the issue's ticket/plan
        plan_dir = os.path.join(self.state_dir, "ISSUES", f"task--{slug}")
        os.makedirs(plan_dir, exist_ok=True)
        textio.write_text(os.path.join(plan_dir, "plan.md"), "# Plan for dirty test", newline="\n")

        # along start without --allow-dirty should succeed because the dirty file is owned by the issue
        res = proc.run_capture([sys.executable, os.path.join(SCRIPTS_DIR, "along_exec.py"), "start", slug], cwd=self.tmp)
        self.assertEqual(res.returncode, 0, f"Expected start to succeed on issue-owned dirty tree, but got: {res.stderr}\n{res.stdout}")
        self.assertIn("Ready to work on issue", res.stdout)

    def test_submodule_protocol_auto_commit(self):
        """REQ-3: along update --commit auto-commits protocol-managed files in dirty submodules."""
        # Create a submodule folder with its own .git
        sub_dir = os.path.join(self.tmp, "modules", "core-lib")
        os.makedirs(sub_dir, exist_ok=True)
        proc.run_capture(["git", "init", "-q"], cwd=sub_dir)
        proc.run_capture(["git", "config", "user.name", "Submodule Committer"], cwd=sub_dir)
        proc.run_capture(["git", "config", "user.email", "sub@actdim.local"], cwd=sub_dir)

        # Commit initial baseline in submodule
        textio.write_text(os.path.join(sub_dir, "README.md"), "# Submodule", newline="\n")
        proc.run_capture(["git", "add", "README.md"], cwd=sub_dir)
        proc.run_capture(["git", "commit", "-m", "chore(along): protocol v4.9.0"], cwd=sub_dir)

        # Simulate protocol update in submodule
        textio.write_text(os.path.join(sub_dir, "AGENTS.md"), "# ALONG-PROTOCOL v5.0.0", newline="\n")
        textio.write_text(os.path.join(sub_dir, ".protocol-version"), "5.0.0\n", newline="\n")

        # Run auto_commit_submodule_protocol_updates
        committed = lifecycle.auto_commit_submodule_protocol_updates(
            self.tmp,
            [self.tmp, sub_dir],
            version_str="5.0.0"
        )
        self.assertEqual(len(committed), 1)
        self.assertEqual(committed[0], "modules/core-lib")

        # Verify git commit in submodule
        log_res = proc.run_capture(["git", "log", "-n", "1", "--oneline"], cwd=sub_dir)
        self.assertIn("chore(along): protocol v5.0.0", log_res.stdout)

        # Verify that chore(along): protocol v5.0.0 is exempt from git commit issue binding
        violations = gitgates.check_message("chore(along): protocol v5.0.0", repo_root=sub_dir)
        self.assertEqual(violations, [], f"Expected chore(along): to be exempt from binding, got: {violations}")

    def test_gitattributes_merge_driver_transparency_output(self):
        """REQ-4: along update logs transparency notices and rationales when merge drivers change."""
        # Create .gitattributes with legacy custom merge drivers
        attr_file = os.path.join(self.tmp, ".gitattributes")
        textio.write_text(attr_file, "*.md merge=along-frontmatter\n.along/ISSUES.md merge=along-projection\n", newline="\n")

        local_along_update = _load_local_along_update()
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            local_along_update.apply_migration_to_context(
                ctx_dir=self.tmp,
                protocol_text="# ALONG-PROTOCOL v5.0.0",
                migrate_script=None,
                is_root=True,
                dry_run=False,
            )
            out = mock_stdout.getvalue()

        self.assertIn("[Notice] Updated .gitattributes merge drivers from custom merge driver", out)
        self.assertIn("to -merge (fail-closed protection)", out)
        self.assertIn("Rationale:", out)


if __name__ == "__main__":
    unittest.main()
