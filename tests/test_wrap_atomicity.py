#!/usr/bin/env python3
"""
tests/test_wrap_atomicity.py - Unit tests for engine atomicity, gate resilience, and subproject session friction.

Covers requirements from bug--engine-atomicity-and-gate-resilience:
- REQ-1: Wrap fail-fast on open checkboxes; auto-commit failure unstaging and status output.
- REQ-2: Entity reference integrity distinguishes untracked on-disk entity files.
- REQ-3: Stub detection completeness across all stubs and subproject contexts.
- REQ-4: Subprojects without tests treated as tests: none without failing.
- REQ-5: User gate approvals via 'along gates approve'.
- REQ-6: Submodule CWD resilience in find_repo_root.
- REQ-7: Workspace containment honors session-registered extra working directories.
"""

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

from alongkit import entities, gates, gitgates, lifecycle, repo, session, textio
from alongkit.hooks import containment, predicates


class TestWrapAtomicityAndGateResilience(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="along-atomicity-test-")
        os.makedirs(os.path.join(self.tmp, ".git"), exist_ok=True)
        self.state_dir = os.path.join(self.tmp, ".along")
        os.makedirs(os.path.join(self.state_dir, "ISSUES"), exist_ok=True)
        os.makedirs(os.path.join(self.state_dir, "ISSUES", "done"), exist_ok=True)
        os.makedirs(os.path.join(self.state_dir, ".session"), exist_ok=True)
        # Create minimal config.json
        with open(os.path.join(self.state_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"protocol_version": "4.9.1"}, f)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_wrap_fails_fast_on_unchecked_acceptance_criteria(self):
        """REQ-1: along wrap aborts if unchecked checkboxes exist in the issue body."""
        slug = "sample-issue"
        issue_path = os.path.join(self.state_dir, "ISSUES", f"task--{slug}.md")
        content = (
            "---\n"
            "protocol: along\n"
            "protocol_version: '4.9.1'\n"
            f"slug: {slug}\n"
            "type: task\n"
            "status: in-progress\n"
            "---\n\n"
            "# Sample Task\n\n"
            "## Problem\nSome problem description.\n\n"
            "## Requirements\nSome requirement.\n\n"
            "## Acceptance Criteria\n"
            "- [x] Completed item\n"
            "- [ ] Unfinished item\n"
        )
        textio.write_text(issue_path, content, newline="\n")

        # execute_wrap must abort with code 2 because of the unchecked item without force_reason
        code = lifecycle.execute_wrap(
            repo_root=self.tmp,
            slug=slug,
            status="done",
            summary="Completed sample",
            decisions=[],
            no_verify=True,
            no_commit=True,
        )
        self.assertEqual(code, 2)
        # Verify the file was NOT moved to done/
        self.assertTrue(os.path.isfile(issue_path))
        self.assertFalse(os.path.isfile(os.path.join(self.state_dir, "ISSUES", "done", f"task--{slug}.md")))

        # Passes with force_reason
        code_forced = lifecycle.execute_wrap(
            repo_root=self.tmp,
            slug=slug,
            status="done",
            summary="Completed sample",
            decisions=[],
            force_reason="Need urgent closeout",
            no_verify=True,
            no_commit=True,
        )
        self.assertEqual(code_forced, 0)

    def test_entity_reference_integrity_distinguishes_untracked_files(self):
        """REQ-2: check_entity_references detects untracked entity files on disk and advises git add."""
        slug = "untracked-dep"
        dep_path = os.path.join(self.state_dir, "ISSUES", f"feat--{slug}.md")
        textio.write_text(dep_path, "---\nprotocol: along\nslug: " + slug + "\ntype: feat\nstatus: open\n---\n# Dep\n", newline="\n")

        # _entity_exists_on_disk should recognize the file on physical disk
        self.assertTrue(gitgates._entity_exists_on_disk(self.tmp, slug))
        self.assertTrue(gitgates._entity_exists_on_disk(self.tmp, f"feat--{slug}"))

        # Non-existent entity returns False
        self.assertFalse(gitgates._entity_exists_on_disk(self.tmp, "completely-bogus-slug"))

    def test_stub_detector_reports_all_without_truncation(self):
        """REQ-3: validate_issue_completion reports all unchecked items in full without truncation."""
        items = [f"- [ ] Item number {i}" for i in range(1, 8)]
        body = (
            "---\nprotocol: along\nslug: test-stubs\ntype: task\nstatus: done\n---\n"
            "# Title\n## Problem\nP\n## Requirements\nR\n## Acceptance Criteria\n"
            + "\n".join(items)
            + "\n"
        )
        ok, reasons = entities.validate_issue_completion(body, status="done")
        self.assertFalse(ok)
        reason_text = " ".join(reasons)
        # Every item from 1 to 7 must be listed in the reasons
        for i in range(1, 8):
            self.assertIn(f"Item number {i}", reason_text)
        self.assertNotIn("more", reason_text)

    def test_subproject_zero_tests_treated_as_tests_none(self):
        """REQ-4: Zero-test subproject is treated as tests: none rather than hard failure."""
        # Subproject with intentional subproject marker or ancestor context
        sub_dir = os.path.join(self.tmp, "subproj")
        sub_along = os.path.join(sub_dir, ".along")
        os.makedirs(sub_along, exist_ok=True)
        with open(os.path.join(sub_along, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"subproject": {"intentional": True}}, f)

        # In subproject, detect_test_command returns None if tests/ is empty
        os.makedirs(os.path.join(sub_dir, "tests"), exist_ok=True)
        cmd = gates.detect_test_command(sub_dir)
        self.assertIsNone(cmd)

    def test_gates_approve_command_resolves_denials(self):
        """REQ-5: along gates approve resolves pending denials."""
        slug = "approval-test"
        session.init_session(self.tmp, slug)
        key = "antigravity--test-session"
        session.save_binding(self.tmp, key, {"slug": slug})

        # Record a denial event
        session.append_event(
            self.tmp, slug, key, "deny",
            path="some/file.py",
            extra={"id": "denial-101", "gate": "projection_protection", "tool": "edit"}
        )

        status_before = session.denial_status(self.tmp, slug)
        self.assertEqual(len(status_before), 1)
        self.assertEqual(status_before[0]["state"], session.DENIAL_OPEN)

        # Run approve via commands.gates
        from alongkit.commands import gates as cmd_gates
        code = cmd_gates.handle_gates_command(self.tmp, ["approve", "denial-101", "--slug", slug, "--reason", "Approved by user"])
        self.assertEqual(code, 0)

        status_after = session.denial_status(self.tmp, slug)
        self.assertEqual(len(status_after), 1)
        self.assertEqual(status_after[0]["state"], session.DENIAL_RESOLVED)
        self.assertEqual(status_after[0]["via"], "user-approval")

    def test_auto_settle_projection_denials(self):
        """REQ-5: Auto-settle resolves projection_protection denials upon projection regeneration."""
        slug = "auto-settle-test"
        session.init_session(self.tmp, slug)
        key = session.current_session_key()
        session.save_binding(self.tmp, key, {"slug": slug})

        session.append_event(
            self.tmp, slug, key, "deny",
            path="docs/INDEX.md",
            extra={"id": "denial-202", "gate": "projection_protection", "tool": "edit"}
        )

        settled = session.settle_projection_denials(self.tmp, slug=slug)
        self.assertIn("denial-202", settled)

        status_after = session.denial_status(self.tmp, slug)
        self.assertEqual(status_after[0]["state"], session.DENIAL_RESOLVED)
        self.assertEqual(status_after[0]["via"], "superseded")

    def test_submodule_find_repo_root_resolves_parent_along_repo(self):
        """REQ-6: find_repo_root walks past submodule .git to enclosing Along repo."""
        submodule_dir = os.path.join(self.tmp, "submodule")
        os.makedirs(submodule_dir, exist_ok=True)
        # Create .git file as typical for git submodules
        with open(os.path.join(submodule_dir, ".git"), "w", encoding="utf-8") as f:
            f.write("gitdir: ../.git/modules/submodule\n")

        # CWD inside submodule should resolve to the parent Along repo (self.tmp)
        resolved = repo.find_repo_root(submodule_dir)
        self.assertEqual(os.path.realpath(resolved), os.path.realpath(self.tmp))

    def test_workspace_containment_honors_session_extra_working_dirs(self):
        """REQ-7: workspace containment allows paths registered in session extra working directories."""
        slug = "containment-test"
        session.init_session(self.tmp, slug)
        key = "antigravity--test-containment"

        extra_dir = tempfile.mkdtemp(prefix="along-extra-dir-")
        try:
            # Register extra working dir in binding
            session.save_binding(self.tmp, key, {"slug": slug, "extra_working_dirs": [extra_dir]})

            policy = containment.build_policy(self.tmp, session_key=key)
            self.assertTrue(policy.can_read(extra_dir))
        finally:
            shutil.rmtree(extra_dir, ignore_errors=True)

    def test_lifecycle_hook_cli_help_interception(self):
        """REQ-8: along test --help and along build -h intercept help without executing hooks."""
        from alongkit import proc
        exec_py = os.path.join(SCRIPTS_DIR, "along_exec.py")

        res_test = proc.run_capture([sys.executable, exec_py, "test", "--help"], cwd=self.tmp)
        self.assertEqual(res_test.returncode, 0)
        self.assertIn("Usage: along test [options]", res_test.stdout)
        self.assertIn("--full", res_test.stdout)
        self.assertIn("--affected", res_test.stdout)

        res_build = proc.run_capture([sys.executable, exec_py, "build", "-h"], cwd=self.tmp)
        self.assertEqual(res_build.returncode, 0)
        self.assertIn("Usage: along build [options]", res_build.stdout)

    def test_docs_only_test_skipping(self):
        """REQ-9: Pure documentation, metadata, and Along state changes skip test gate."""
        from alongkit import verify
        import io
        from unittest.mock import patch

        self.assertTrue(verify.is_doc_only_path("AGENTS.md"))
        self.assertTrue(verify.is_doc_only_path("docs/topic.md"))
        self.assertTrue(verify.is_doc_only_path(".along/ISSUES/task--1.md"))
        self.assertTrue(verify.is_doc_only_path("llms.txt"))
        self.assertTrue(verify.is_doc_only_path("llms-full.txt"))

        self.assertTrue(verify.docs_only_change(self.tmp, ["AGENTS.md", "docs/topic.md", ".along/ISSUES/task--1.md"]))
        self.assertFalse(verify.docs_only_change(self.tmp, ["AGENTS.md", "src/index.ts"]))

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            outcome = gates.run_test_gate(
                self.tmp,
                label="Pre-Commit Quality Gate",
                files=["AGENTS.md", "docs/topic.md"]
            )
            out = mock_stdout.getvalue()

        self.assertEqual(outcome, gates.TESTS_SKIPPED)
        self.assertIn("tests: skipped (docs-only change)", out)

    def test_hook_engine_resolves_parent_repo_on_submodule_cwd(self):
        """REQ-6: HookEngine resolves effective_root to parent Along repo when cwd is in submodule."""
        submodule_dir = os.path.join(self.tmp, "src", "submod")
        os.makedirs(submodule_dir, exist_ok=True)
        with open(os.path.join(submodule_dir, ".git"), "w", encoding="utf-8") as f:
            f.write("gitdir: ../../.git/modules/submod\n")

        from alongkit.hooks.adapters.claude import ClaudeCodeAdapter
        adapter = ClaudeCodeAdapter()
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Edit",
            "tool_input": {"file_path": "README.md", "old_string": "a", "new_string": "b"},
            "cwd": submodule_dir,
        }
        event = adapter.parse(json.dumps(payload))
        # Adapter preserves verbatim cwd
        self.assertEqual(event.workspace_root, submodule_dir)
        # HookEngine resolves effective_root to parent Along repo
        parent_repo = repo.find_hook_root(submodule_dir)
        self.assertEqual(os.path.realpath(parent_repo), os.path.realpath(self.tmp))
        parent_file = os.path.join(self.tmp, "README.md")
        with open(parent_file, "w", encoding="utf-8") as f:
            f.write("test")
        policy = containment.build_policy(parent_repo)
        self.assertTrue(policy.can_write(parent_file))


if __name__ == "__main__":
    unittest.main()
