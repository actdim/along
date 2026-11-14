#!/usr/bin/env python3
"""
tests/test_gates_traceability.py - Integration and hermetic tests for Gate Traceability.
"""

from __future__ import annotations

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

from alongkit.hooks.traceability import (
    audit_traceability,
    format_traceability_report,
    scan_prose_anchors,
)


class TestRepositoryGateTraceability(unittest.TestCase):
    """Verifies that the live repository satisfies bi-directional gate traceability."""

    def test_live_repository_traceability_is_clean(self):
        report = audit_traceability(REPO_ROOT)
        report_output = format_traceability_report(report)

        self.assertGreaterEqual(
            report.total_gates,
            11,
            f"Expected at least 11 default gates, found {report.total_gates}\n{report_output}",
        )
        self.assertEqual(
            report.dangling_references,
            [],
            f"Dangling gate references found in prose:\n{report_output}",
        )
        self.assertEqual(
            report.schema_errors,
            [],
            f"Gate schema or predicate handler errors found:\n{report_output}",
        )
        self.assertTrue(report.is_clean, f"Traceability report failed:\n{report_output}")


class TestHermeticTraceabilityScanner(unittest.TestCase):
    """Hermetic unit tests for the scanner's ability to catch defects."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="along-trace-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_catches_dangling_gate_reference(self):
        # Create a dummy skill with an invalid gate badge
        skills_dir = os.path.join(self.tmp, "skills", "fake-skill")
        os.makedirs(skills_dir, exist_ok=True)
        doc_path = os.path.join(skills_dir, "SKILL.md")
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write("# Fake Skill\nRule [gate: ghost-gate-not-in-yaml] must be observed.\n")

        report = audit_traceability(self.tmp)
        self.assertFalse(report.is_clean)
        self.assertEqual(len(report.dangling_references), 1)
        self.assertEqual(report.dangling_references[0].gate_id, "ghost-gate-not-in-yaml")


class TestCompiledProjections(unittest.TestCase):
    """Hermetic unit tests for compiled projection recognition. [bug--stop-gate-false-positives] REQ-1"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="along-proj-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_compiled_projections_not_plan_governed(self):
        from alongkit import closeout
        from alongkit.hooks import predicates

        pkg_docs = os.path.join(self.tmp, "packages", "pkg", "docs")
        os.makedirs(pkg_docs, exist_ok=True)
        agents_path = os.path.join(self.tmp, "packages", "pkg", "AGENTS.md")
        with open(agents_path, "w", encoding="utf-8") as f:
            f.write("# Agent context\n")

        index_path = os.path.join(pkg_docs, "INDEX.md")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write("---\nprotocol: along\ntype: index\n---\n# Index\n")

        self.assertTrue(closeout.is_compiled_projection("packages/pkg/docs/INDEX.md", self.tmp))
        self.assertFalse(predicates._is_plan_governed("packages/pkg/docs/INDEX.md", self.tmp))

        # PreToolUse exemption for package-level compiled projection
        from alongkit.hooks.models import HookEvent, HookEventType
        ev_pre = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": index_path, "CodeContent": "new content"},
            workspace_root=self.tmp,
            runtime="claude",
            conversation_id="test-sess",
        )
        self.assertIsNone(predicates.check_mutation_authorization(ev_pre, self.tmp, options={"enforce_unbound": True}))

        # same file without front matter
        with open(index_path, "w", encoding="utf-8") as f:
            f.write("# Plain Index without frontmatter\n")
        self.assertFalse(closeout.is_compiled_projection("packages/pkg/docs/INDEX.md", self.tmp))
        self.assertTrue(predicates._is_plan_governed("packages/pkg/docs/INDEX.md", self.tmp))

        # llms.txt with sibling docs/ present
        llms_path = os.path.join(self.tmp, "packages", "pkg", "llms.txt")
        with open(llms_path, "w", encoding="utf-8") as f:
            f.write("llms content\n")
        self.assertTrue(closeout.is_compiled_projection("packages/pkg/llms.txt", self.tmp))
        self.assertFalse(predicates._is_plan_governed("packages/pkg/llms.txt", self.tmp))

        # tools/llms.txt without sibling docs/
        tools_dir = os.path.join(self.tmp, "tools")
        os.makedirs(tools_dir, exist_ok=True)
        tool_llms = os.path.join(tools_dir, "llms.txt")
        with open(tool_llms, "w", encoding="utf-8") as f:
            f.write("tool llms\n")
        self.assertFalse(closeout.is_compiled_projection("tools/llms.txt", self.tmp))
        self.assertTrue(predicates._is_plan_governed("tools/llms.txt", self.tmp))

        # source code file -> governed
        src_dir = os.path.join(self.tmp, "packages", "pkg", "src")
        os.makedirs(src_dir, exist_ok=True)
        src_file = os.path.join(src_dir, "a.py")
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("x = 1\n")
        self.assertFalse(closeout.is_compiled_projection("packages/pkg/src/a.py", self.tmp))
        self.assertTrue(predicates._is_plan_governed("packages/pkg/src/a.py", self.tmp))


class TestStopCountsSessionWrites(unittest.TestCase):
    """Verifies that the Stop plan gate counts only this session's writes. REQ-4"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="along-stop-writes-")
        import subprocess
        subprocess.run(["git", "init", "-q"], cwd=self.tmp, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.tmp, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.tmp, check=True)
        src_dir = os.path.join(self.tmp, "src")
        os.makedirs(src_dir, exist_ok=True)
        with open(os.path.join(src_dir, "init.py"), "w", encoding="utf-8") as f:
            f.write("x = 0\n")
        subprocess.run(["git", "add", "-A"], cwd=self.tmp, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=self.tmp, check=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_stop_counts_only_this_sessions_writes(self):
        from alongkit.hooks.models import HookEvent, HookEventType
        from alongkit.hooks.predicates import record_tool_activity, check_mutation_authorization, load_activity_trace, save_activity_trace

        sid = "sess-1"
        ev_prompt = HookEvent(
            event_type=HookEventType.USER_PROMPT_SUBMIT,
            workspace_root=self.tmp,
            runtime="claude",
            conversation_id=sid,
        )
        ev_stop = HookEvent(
            event_type=HookEventType.STOP,
            workspace_root=self.tmp,
            runtime="claude",
            conversation_id=sid,
        )

        # 1. Foreign write: simulate a second session writing src/other.py
        record_tool_activity(ev_prompt, self.tmp)
        other_path = os.path.join(self.tmp, "src", "other.py")
        with open(other_path, "w", encoding="utf-8") as f:
            f.write("foreign = 1\n")
        ev_other_write = HookEvent(
            event_type=HookEventType.POST_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": other_path, "CodeContent": "foreign = 1\n"},
            workspace_root=self.tmp,
            runtime="claude",
            conversation_id="sess-2",
        )
        record_tool_activity(ev_other_write, self.tmp)
        res = check_mutation_authorization(ev_stop, self.tmp, options={"enforce_unbound": True})
        self.assertIsNone(res, f"Foreign write should not be denied: {res}")

        # 2. Own file-tool write: create src/mine.py + PostToolUse
        record_tool_activity(ev_prompt, self.tmp)
        mine_path = os.path.join(self.tmp, "src", "mine.py")
        with open(mine_path, "w", encoding="utf-8") as f:
            f.write("mine = 1\n")
        ev_file_write = HookEvent(
            event_type=HookEventType.POST_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": mine_path, "CodeContent": "mine = 1\n"},
            workspace_root=self.tmp,
            runtime="claude",
            conversation_id=sid,
        )
        record_tool_activity(ev_file_write, self.tmp)
        res = check_mutation_authorization(ev_stop, self.tmp, options={"enforce_unbound": True})
        self.assertIsNotNone(res)
        self.assertIn("require-plan-approval", str(res))
        self.assertIn("src/mine.py", str(res).replace("\\", "/"))

        # 3. Own shell write: PRE_TOOL_USE run_command -> write src/sh.py -> POST_TOOL_USE run_command
        record_tool_activity(ev_prompt, self.tmp)
        sh_path = os.path.join(self.tmp, "src", "sh.py")
        ev_sh_pre = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": "echo x > src/sh.py"},
            workspace_root=self.tmp,
            runtime="claude",
            conversation_id=sid,
        )
        ev_sh_post = HookEvent(
            event_type=HookEventType.POST_TOOL_USE,
            tool_name="run_command",
            tool_args={"CommandLine": "echo x > src/sh.py"},
            workspace_root=self.tmp,
            runtime="claude",
            conversation_id=sid,
        )
        record_tool_activity(ev_sh_pre, self.tmp)
        with open(sh_path, "w", encoding="utf-8") as f:
            f.write("sh = 1\n")
        record_tool_activity(ev_sh_post, self.tmp)
        res = check_mutation_authorization(ev_stop, self.tmp, options={"enforce_unbound": True})
        self.assertIsNotNone(res)
        self.assertIn("src/sh.py", str(res).replace("\\", "/"))

        # 4. Legacy trace (no turn_writes): foreign write should be denied as old behavior
        record_tool_activity(ev_prompt, self.tmp)
        key = "claude--sess-1"
        trace = load_activity_trace(self.tmp, key)
        trace.pop("turn_writes", None)
        save_activity_trace(self.tmp, trace, key)
        with open(os.path.join(self.tmp, "src", "legacy_foreign.py"), "w", encoding="utf-8") as f:
            f.write("legacy = 1\n")
        res = check_mutation_authorization(ev_stop, self.tmp, options={"enforce_unbound": True})
        self.assertIsNotNone(res)
        self.assertIn("src/legacy_foreign.py", str(res).replace("\\", "/"))


class TestNoMicroEditExemption(unittest.TestCase):
    """Verifies that the protocol text and mutation authorization agree: no micro-edit exemption. REQ-6 (D1: A)"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="along-no-micro-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_protocol_text_and_gate_have_no_micro_edit_exemption(self):
        from alongkit import textio
        from alongkit.hooks.models import HookEvent, HookEventType
        from alongkit.hooks.predicates import check_mutation_authorization

        proto_path = os.path.join(REPO_ROOT, "skills", "along-init", "protocol.md")
        proto_ref_path = os.path.join(REPO_ROOT, "skills", "along-init", "protocol-reference.md")

        proto_text = textio.read_text(proto_path)
        proto_ref_text = textio.read_text(proto_ref_path)

        self.assertNotIn("1-line typo/comment edits are exempt", proto_text)
        self.assertNotIn("1-line micro-edits", proto_ref_text)

        # In an unbound temp repo with enforce_unbound, a 1-line comment edit to src/a.py is denied
        src_dir = os.path.join(self.tmp, "src")
        os.makedirs(src_dir, exist_ok=True)
        file_path = os.path.join(src_dir, "a.py")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("# old comment\nx = 1\n")

        ev_edit = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="edit_file",
            tool_args={
                "TargetFile": file_path,
                "old_string": "# old comment\n",
                "new_string": "# new comment\n",
            },
            workspace_root=self.tmp,
            runtime="claude",
            conversation_id="sess-unbound",
        )
        res = check_mutation_authorization(ev_edit, self.tmp, options={"enforce_unbound": True})
        self.assertIsNotNone(res)
        self.assertIn("require-plan-approval", str(res))


if __name__ == "__main__":
    unittest.main()
