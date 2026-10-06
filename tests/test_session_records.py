#!/usr/bin/env python3
"""
tests/test_session_records.py - The session record is captured and never lost.

Regression suite for [bug--session-records-not-captured]: the approved plan reaches the
blackboard (REQ-1), direct mode keeps an execution trace (REQ-2), a blackboard is archived
into a session log before any purge (REQ-3..REQ-5), wrap-before-stop checks every issue
completed today (REQ-6), Blackboard Records are append-only (REQ-7) and doctor reports
orphan blackboards (REQ-8).

All tests use throwaway directories and a cleared session environment.
"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

import along_exec
from alongkit import session, textio
from alongkit.hooks import HookEvent, HookEventType
from alongkit.hooks.predicates import record_tool_activity

CLEAN_ENV = {k: v for k, v in os.environ.items() if k not in session.SESSION_ENV_VARS}
SCAFFOLD = "# Living Plan: x\n\nTitle: x\n\n## Steps\n- [ ] Step 1: Step 1\n- [ ] Step 2: Step 2\n"


def _record_issue(root: str, slug: str, status: str = "in-progress", itype: str = "feat") -> str:
    path = os.path.join(root, ".along", "ISSUES", f"{itype}--{slug}.md")
    textio.write_text(path, f"---\nprotocol: along\nslug: {slug}\ntype: {itype}\nstatus: {status}\n"
                            f"priority: medium\ncreated: 2026-10-01\nupdated: 2026-10-01\n---\n\n# {slug}\n",
                      newline="\n")
    return path


class RecordFixture(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, CLEAN_ENV, clear=True)
        self.env.start()
        self.root = tempfile.mkdtemp(prefix="along-records-test-")
        os.makedirs(os.path.join(self.root, ".git"), exist_ok=True)
        os.makedirs(os.path.join(self.root, ".along", "ISSUES"))
        os.makedirs(os.path.join(self.root, ".along", ".session"))
        self.key = session.session_key("claude", "sess-a")

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def start(self, slug: str) -> None:
        _record_issue(self.root, slug)
        session.init_session(self.root, slug)
        session.bind_session(self.root, slug, key=self.key)

    def plan_text(self, slug: str) -> str:
        return session.read_plan(self.root, slug)

    def trace_text(self, slug: str) -> str:
        path = os.path.join(session.get_session_dir(self.root, slug), session.TRACE_FILENAME)
        return textio.read_text(path, strict=False) if os.path.isfile(path) else ""

    def run_cli(self, handler, args):
        """Run an along_exec handler as this session; (exit code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"ALONG_SESSION_ID": "sess-a", "ALONG_SESSION_RUNTIME": "claude"}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                handler(self.root, args)
                code = 0
            except SystemExit as exc:
                code = int(exc.code or 0)
        return code, out.getvalue(), err.getvalue()

    def exit_plan_mode(self, plan):
        tool_input = {} if plan is None else {"plan": plan}
        event = HookEvent(event_type=HookEventType.POST_TOOL_USE, tool_name="ask_question",
                          tool_args=dict(tool_input), workspace_root=self.root, runtime="claude",
                          conversation_id="sess-a",
                          raw_payload={"tool_name": "ExitPlanMode", "tool_input": tool_input})
        record_tool_activity(event, self.root)


class TestScaffoldDetection(unittest.TestCase):
    def test_scaffold_and_empty(self):
        self.assertTrue(session.is_scaffold_plan(SCAFFOLD))
        self.assertTrue(session.is_scaffold_plan(""))

    def test_real_content_is_not_scaffold(self):
        self.assertFalse(session.is_scaffold_plan(SCAFFOLD + "\n1. Edit session.py\n"))
        self.assertFalse(session.is_scaffold_plan("# Living Plan: x\n\n## Steps\n- [ ] Step 1: Plan capture\n"))


class TestRecordPlan(RecordFixture):
    """REQ-1: the approved plan is recorded and its revisions are kept."""

    def test_first_plan_replaces_scaffold_then_revisions_append(self):
        self.start("alpha")
        self.assertFalse(session.plan_recorded(self.root, "alpha"))
        self.assertEqual(session.record_plan(self.root, "alpha", "1. first", "test"), 1)
        self.assertEqual(session.record_plan(self.root, "alpha", "1. first", "test"), 0, "same plan twice")
        self.assertEqual(session.record_plan(self.root, "alpha", "1. second", "test"), 2)
        text = self.plan_text("alpha")
        self.assertNotIn("Step 1: Step 1", text)
        self.assertIn("## Revision 1 (", text)
        self.assertIn("1. first", text)
        self.assertIn("## Revision 2 (", text)
        self.assertIn("plan recorded: revision 2 (test)", self.trace_text("alpha"))

    def test_plan_written_by_the_agent_counts_as_revision_one(self):
        self.start("alpha")
        textio.write_text(session.plan_path(self.root, "alpha"), "# Living Plan\n\n1. by hand\n", newline="\n")
        self.assertTrue(session.plan_recorded(self.root, "alpha"))
        self.assertEqual(session.record_plan(self.root, "alpha", "1. revised", "test"), 2)
        self.assertIn("1. by hand", self.plan_text("alpha"))


class TestPlanApproveCli(RecordFixture):
    def test_refuses_while_plan_is_scaffold(self):
        self.start("alpha")
        code, _out, err = self.run_cli(along_exec.handle_plan_command, ["approve", "alpha"])
        self.assertEqual(code, 2)
        self.assertIn("No plan recorded", err)
        self.assertFalse(session.is_plan_approved(self.root, key=self.key))

    def test_plan_file_is_recorded_and_approved(self):
        self.start("alpha")
        plan_file = os.path.join(self.root, "plan-input.md")
        textio.write_text(plan_file, "1. do the thing\n", newline="\n")
        code, out, _err = self.run_cli(along_exec.handle_plan_command,
                                       ["approve", "alpha", "--plan-file", plan_file])
        self.assertEqual(code, 0, out)
        self.assertIn("1. do the thing", self.plan_text("alpha"))
        self.assertTrue(session.is_plan_approved(self.root, key=self.key))
        self.assertIn("plan approved (along plan approve)", self.trace_text("alpha"))
        self.assertTrue((session.load_binding(self.root, self.key) or {}).get("approved_at"))

    def test_plan_written_into_plan_md_is_enough(self):
        self.start("alpha")
        textio.write_text(session.plan_path(self.root, "alpha"), "1. by hand\n", newline="\n")
        code, _out, _err = self.run_cli(along_exec.handle_plan_command, ["approve", "alpha"])
        self.assertEqual(code, 0)

    def test_missing_plan_file_fails(self):
        self.start("alpha")
        code, _out, err = self.run_cli(along_exec.handle_plan_command,
                                       ["approve", "alpha", "--plan-file", os.path.join(self.root, "nope.md")])
        self.assertEqual(code, 2)
        self.assertIn("Cannot read", err)

    def test_scratch_approve_refuses_scaffold_too(self):
        self.start("alpha")
        code, _out, err = self.run_cli(along_exec.handle_scratch_command, ["approve", "alpha"])
        self.assertEqual(code, 2)
        self.assertIn("No plan recorded", err)


class TestExitPlanModeCapture(RecordFixture):
    def test_bound_session_records_the_plan(self):
        self.start("alpha")
        self.exit_plan_mode("## Plan\n\n1. accepted in plan mode\n")
        self.assertIn("accepted in plan mode", self.plan_text("alpha"))
        self.assertIn(", ExitPlanMode)", self.plan_text("alpha"))
        self.assertTrue(session.is_plan_approved(self.root, key=self.key))
        self.assertIn("plan approved (ExitPlanMode)", self.trace_text("alpha"))

    def test_plan_before_start_goes_to_the_first_slug(self):
        self.exit_plan_mode("1. accepted before start\n")
        self.start("alpha")
        self.assertIn("accepted before start", self.plan_text("alpha"))
        self.assertTrue(session.is_plan_approved(self.root, key=self.key))
        self.assertNotIn("pending_plan", session.load_binding(self.root, self.key) or {})

    def test_no_plan_text_still_approves(self):
        self.start("alpha")
        self.exit_plan_mode(None)
        self.assertTrue(session.is_plan_approved(self.root, key=self.key))
        self.assertFalse(session.plan_recorded(self.root, "alpha"))


def _post_edit(root: str, rel: str, sid: str = "sess-a") -> HookEvent:
    return HookEvent(event_type=HookEventType.POST_TOOL_USE, tool_name="write_to_file",
                     tool_args={"TargetFile": os.path.join(root, rel), "CodeContent": "x = 1\n"},
                     workspace_root=root, runtime="claude", conversation_id=sid)


class TestDirectModeTrace(RecordFixture):
    """REQ-2: hooks and Along entry points keep the trace of the bound issue."""

    def test_edits_of_any_repository_path_are_traced_and_collapsed(self):
        self.start("alpha")
        for rel in ("src/a.py", "src/a.py", "docs/topic--x.md", ".along/ISSUES/feat--alpha.md",
                    ".along/.session/alpha/plan.md", ".along/diagnostics/x.json"):
            record_tool_activity(_post_edit(self.root, rel), self.root)
        trace = self.trace_text("alpha")
        self.assertIn("edit src/a.py (x2)", trace)
        self.assertIn("edit docs/topic--x.md", trace)
        self.assertIn("edit .along/ISSUES/feat--alpha.md", trace)
        self.assertNotIn(".along/.session/", trace)
        self.assertNotIn("diagnostics", trace)

    def test_unbound_and_other_sessions_do_not_write_into_the_trace(self):
        self.start("alpha")
        record_tool_activity(_post_edit(self.root, "src/b.py", sid="sess-b"), self.root)
        self.assertNotIn("src/b.py", self.trace_text("alpha"))

    def test_test_runs_with_result(self):
        self.start("alpha")
        with mock.patch.dict(os.environ, {"ALONG_SESSION_ID": "sess-a", "ALONG_SESSION_RUNTIME": "claude"}):
            session.trace_test_run(self.root, True, "along test")
            session.trace_test_run(self.root, False, "Wrap Quality Gate")
        trace = self.trace_text("alpha")
        self.assertIn("test pass (along test)", trace)
        self.assertIn("test FAIL (Wrap Quality Gate)", trace)

    def test_gate_denial_is_traced(self):
        from alongkit.hooks.engine import HookEngine
        self.start("alpha")
        event = HookEvent(event_type=HookEventType.PRE_TOOL_USE, tool_name="run_command",
                          tool_args={"CommandLine": "git reset --hard"}, workspace_root=self.root,
                          runtime="claude", conversation_id="sess-a")
        result = HookEngine(repo_root=self.root).evaluate(event)
        self.assertFalse(result.is_allowed)
        self.assertIn("denied [", self.trace_text("alpha"))

    def test_phase_and_step_changes(self):
        self.start("alpha")
        session.update_state(self.root, "alpha", phase="execution")
        session.update_state(self.root, "alpha", current_step=1, step_status="in-progress")
        session.update_state(self.root, "alpha", current_step=1, increment_retry=True)
        trace = self.trace_text("alpha")
        self.assertIn("phase: inquiry -> execution", trace)
        self.assertIn("step 1: pending -> in-progress", trace)
        self.assertIn("step 1: retry 1/", trace)

    def test_trace_is_bounded(self):
        self.start("alpha")
        with mock.patch.object(session, "TRACE_MAX_ENTRIES", 5):
            for i in range(12):
                session.append_trace(self.root, "alpha", f"entry {i}")
        trace = self.trace_text("alpha")
        self.assertIn("(7 earlier entries trimmed)", trace)
        self.assertNotIn("entry 6\n", trace)
        self.assertIn("entry 11", trace)
        self.assertEqual(trace.count("\n- "), 5)


class ArchiveFixture(unittest.TestCase):
    """A hermetic repository with issue `task--fixture-sample-task` and its blackboard."""
    SLUG = "fixture-sample-task"

    def setUp(self):
        from tests import hermetic
        self.env = mock.patch.dict(os.environ, CLEAN_ENV, clear=True)
        self.env.start()
        self.root = hermetic.make_repo_fixture()
        session.init_session(self.root, self.SLUG)
        self.sdir = session.get_session_dir(self.root, self.SLUG)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def log_text(self) -> str:
        from alongkit import entities, lifecycle
        path = lifecycle.session_log_path(self.root, self.SLUG, entities.today_iso())
        return textio.read_text(path) if os.path.isfile(path) else ""

    def run_exec(self, args):
        from alongkit import proc
        return proc.run_capture([sys.executable, os.path.join(SCRIPTS_DIR, "along_exec.py"), *args],
                                cwd=self.root)


class TestArchiveAndPurge(ArchiveFixture):
    """REQ-3..REQ-5: no blackboard leaves without its record."""

    def test_scratch_purge_archives_a_direct_blackboard(self):
        session.record_plan(self.root, self.SLUG, "1. the direct plan", "test")
        res = self.run_exec(["scratch", "purge", self.SLUG])
        self.assertTrue(res.ok, res.stderr)
        self.assertFalse(os.path.isdir(self.sdir))
        log = self.log_text()
        self.assertIn("## Blackboard Record", log)
        self.assertIn("1. the direct plan", log)
        self.assertIn("archived by scratch purge", log)
        self.assertIn("issues_completed: []", log)

    def test_forced_purge_records_the_reason(self):
        session.init_session(self.root, self.SLUG, execution_mode="role-based")
        res = self.run_exec(["scratch", "purge", self.SLUG, "--force", "--reason", "user dropped it"])
        self.assertTrue(res.ok, res.stderr)
        log = self.log_text()
        self.assertIn("Archived without completing: open problems", log)
        self.assertIn("user dropped it", log)

    def test_scaffold_is_not_rendered_as_content(self):
        rendered = session.render_blackboard_markdown(self.root, self.SLUG)
        self.assertIn("No plan recorded.", rendered)
        self.assertNotIn("Step 1: Step 1", rendered)
        self.assertNotIn("| 1 | Step 1 | pending", rendered)
        self.assertNotIn("Target Symbols and Files", rendered)

    def test_same_day_second_record_is_kept(self):
        from alongkit import lifecycle
        session.record_plan(self.root, self.SLUG, "1. first", "test")
        lifecycle.archive_and_purge(self.root, self.SLUG, source="test")
        session.init_session(self.root, self.SLUG)
        session.record_plan(self.root, self.SLUG, "1. second", "test")
        lifecycle.archive_and_purge(self.root, self.SLUG, source="test")
        log = self.log_text()
        self.assertIn("1. first", log)
        self.assertIn("1. second", log)
        self.assertIn("## Blackboard Record (2, ", log)

    def test_issue_done_archives_the_blackboard_and_records_completion(self):
        session.record_plan(self.root, self.SLUG, "1. done plan", "test")
        res = self.run_exec(["issue", "done", self.SLUG])
        self.assertTrue(res.ok, res.stderr)
        self.assertFalse(os.path.isdir(self.sdir))
        log = self.log_text()
        self.assertIn("task--fixture-sample-task", log)
        self.assertIn("1. done plan", log)
        self.assertIn("archived by issue done", log)

    def test_issue_done_without_blackboard_still_logs_completion(self):
        shutil.rmtree(self.sdir)
        res = self.run_exec(["issue", "done", self.SLUG])
        self.assertTrue(res.ok, res.stderr)
        from alongkit import frontmatter
        fm, _body = frontmatter.parse(self.log_text())
        self.assertEqual(fm["issues_completed"], ["task--fixture-sample-task"])


class TestWrapBeforeStop(ArchiveFixture):
    """REQ-6: every issue completed today is in a session log of today."""

    def close(self, slug: str, status: str = "done") -> None:
        from alongkit import entities
        path = _record_issue(self.root, slug, status=status)
        text = textio.read_text(path).replace(f"status: {status}\n", f"status: {status}\ncompleted: {entities.today_iso()}\n")
        done = os.path.join(self.root, ".along", "ISSUES", "done", os.path.basename(path))
        os.makedirs(os.path.dirname(done), exist_ok=True)
        textio.write_text(done, text, newline="\n")
        os.remove(path)

    def check(self):
        from alongkit.hooks.predicates import check_wrap_before_stop
        return check_wrap_before_stop(None, self.root)

    def test_issue_closed_today_without_log_entry_blocks(self):
        self.close("alpha")
        reason = self.check()
        self.assertIn("feat--alpha", reason or "")
        self.assertIn("along wrap alpha", reason or "")

    def test_a_log_of_another_issue_does_not_count(self):
        from alongkit import lifecycle, entities, transaction
        self.close("alpha")
        tx = transaction.FileTransaction(self.root, label="t")
        lifecycle.write_session_record(self.root, tx, self.SLUG, today=entities.today_iso(), completed=True)
        tx.commit()
        self.assertIn("feat--alpha", self.check() or "")

    def test_listed_issue_passes_and_other_statuses_are_ignored(self):
        from alongkit import lifecycle, entities, transaction
        self.close("alpha")
        self.close("beta", status="superseded")
        tx = transaction.FileTransaction(self.root, label="t")
        lifecycle.write_session_record(self.root, tx, "alpha", today=entities.today_iso(), completed=True)
        tx.commit()
        self.assertIsNone(self.check())


class TestDoctorOrphans(ArchiveFixture):
    """REQ-8: orphan blackboards are reported."""

    def test_closed_and_missing_issues_are_orphans_bound_ones_are_not(self):
        from alongkit import lifecycle
        session.init_session(self.root, "ghost")
        _record_issue(self.root, "kept")
        session.init_session(self.root, "kept")
        session.bind_session(self.root, "kept", key=session.session_key("claude", "s1"))
        self.assertEqual(lifecycle.orphan_blackboards(self.root), [("ghost", "issue missing")])
        res = self.run_exec(["issue", "done", self.SLUG, "--status", "cancelled"])
        self.assertTrue(res.ok, res.stderr)
        session.init_session(self.root, self.SLUG)
        self.assertIn((self.SLUG, "issue cancelled"), lifecycle.orphan_blackboards(self.root))
        doctor = self.run_exec(["doctor"])
        self.assertIn("orphan blackboard(s)", doctor.stdout)
        self.assertIn("ghost (issue missing)", doctor.stdout)


SESSION_LOG = ("---\nprotocol: along\ndate: 2026-10-06\nslug: alpha\n---\n\n# Session: Alpha\n\n"
               "## Summary\nFirst summary.\n\n## Blackboard Record\n\nExecution mode: direct.\n\n"
               "### Plan\n\n1. step one\n2. step two\n\n### Execution Trace\n\n- t1 edit a.py\n")
LOG_REL = ".along/SESSIONS/2026/2026-10-06--alpha.md"


class TestSessionRecordAppendOnly(unittest.TestCase):
    """REQ-7: a committed Blackboard Record loses no line; the Summary stays editable."""

    def setUp(self):
        import subprocess
        self.root = tempfile.mkdtemp(prefix="along-record-git-")
        self.git = lambda *a: subprocess.run(["git", *a], cwd=self.root, capture_output=True, text=True,
                                             encoding="utf-8", check=True)
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "T")
        self.write(SESSION_LOG)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "log")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, text):
        path = os.path.join(self.root, *LOG_REL.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        textio.write_text(path, text, newline="\n")

    def staged_check(self, text):
        from alongkit import gitgates
        self.write(text)
        self.git("add", "-A")
        return gitgates.check_session_records(self.root, [LOG_REL], "git", "HEAD")

    def test_summary_edit_passes(self):
        self.assertEqual(self.staged_check(SESSION_LOG.replace("First summary.", "Better summary.")), [])

    def test_append_to_the_record_passes(self):
        self.assertEqual(self.staged_check(SESSION_LOG + "- t2 test pass\n"), [])

    def test_removing_a_record_line_is_rejected(self):
        found = self.staged_check(SESSION_LOG.replace("2. step two\n", ""))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].gate, "session_record_append_only")
        self.assertIn("step two", found[0].message)

    def test_rewriting_a_record_line_is_rejected(self):
        self.assertTrue(self.staged_check(SESSION_LOG.replace("1. step one", "1. step 1")))

    def test_deleting_the_log_is_rejected(self):
        from alongkit import gitgates
        self.git("rm", "-q", LOG_REL)
        self.assertTrue(gitgates.check_session_records(self.root, [LOG_REL], "git", "HEAD"))

    def test_ci_range(self):
        from alongkit import gitgates
        self.write(SESSION_LOG.replace("- t1 edit a.py\n", ""))
        self.git("commit", "-q", "-am", "cut")
        self.assertTrue(gitgates.check_session_records(self.root, [LOG_REL], "ci", "HEAD^", target="HEAD"))

    def test_pre_commit_check_includes_the_gate(self):
        from alongkit import gitgates
        self.write(SESSION_LOG.replace("1. step one\n", ""))
        self.git("add", "-A")
        gates = {v.gate for v in gitgates.check_pre_commit(self.root)}
        self.assertIn("session_record_append_only", gates)


class TestWrapRecord(ArchiveFixture):
    def test_wrap_refuses_a_scaffold_plan_without_reason(self):
        from alongkit import lifecycle
        code = lifecycle.execute_wrap(self.root, self.SLUG, no_verify=True, decisions=[])
        self.assertEqual(code, 2)
        self.assertTrue(os.path.isdir(self.sdir))
        code = lifecycle.execute_wrap(self.root, self.SLUG, no_verify=True, decisions=[],
                                      force_reason="plan given verbally")
        self.assertEqual(code, 0)
        log = self.log_text()
        self.assertIn("No plan recorded.", log)
        self.assertIn("Wrapped without a recorded plan: plan given verbally", log)

    def test_failed_wrap_keeps_the_blackboard(self):
        from alongkit import lifecycle, transaction
        session.record_plan(self.root, self.SLUG, "1. plan", "test")
        with mock.patch.object(transaction.FileTransaction, "commit", side_effect=OSError("disk full")):
            code = lifecycle.execute_wrap(self.root, self.SLUG, no_verify=True, decisions=[])
        self.assertEqual(code, 1)
        self.assertTrue(os.path.isdir(self.sdir), "the purge runs only after the commit")


if __name__ == "__main__":
    unittest.main(verbosity=2)
