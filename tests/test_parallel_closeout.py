#!/usr/bin/env python3
"""
tests/test_parallel_closeout.py - Parallel sessions: attribution, readiness, closeout.

Regression suite for [feat--parallel-session-closeout]: the session event ledger attributes
every edit and test run to the issue a session is bound to (REQ-1, REQ-2), test runs are reused
for an unchanged tree (REQ-8), readiness is computed per issue (REQ-3, REQ-4), a closeout is
approved (REQ-6) and executed (REQ-5), issues can be reopened (REQ-7) and doctor reports stale
state (REQ-9).

All tests use throwaway directories and a cleared session environment.
"""

from __future__ import annotations

import json
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

from alongkit import session, textio
from alongkit.hooks import HookEvent, HookEventType
from alongkit.hooks.predicates import record_tool_activity

CLEAN_ENV = {k: v for k, v in os.environ.items() if k not in session.SESSION_ENV_VARS}


def _closeout_issue(root: str, slug: str, status: str = "in-progress", itype: str = "feat",
                    body: str = "") -> str:
    path = os.path.join(root, ".along", "ISSUES", f"{itype}--{slug}.md")
    textio.write_text(path, f"---\nprotocol: along\nslug: {slug}\ntype: {itype}\nstatus: {status}\n"
                            f"priority: medium\ncreated: 2026-10-01\nupdated: 2026-10-01\n---\n\n# {slug}\n{body}",
                      newline="\n")
    return path


def _edit_event(root: str, rel: str, sid: str) -> HookEvent:
    return HookEvent(event_type=HookEventType.POST_TOOL_USE, tool_name="write_to_file",
                     tool_args={"TargetFile": os.path.join(root, rel), "CodeContent": "x = 1\n"},
                     workspace_root=root, runtime="claude", conversation_id=sid)


class LedgerFixture(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, CLEAN_ENV, clear=True)
        self.env.start()
        self.root = tempfile.mkdtemp(prefix="along-closeout-test-")
        os.makedirs(os.path.join(self.root, ".git"), exist_ok=True)
        os.makedirs(os.path.join(self.root, ".along", "ISSUES"))
        os.makedirs(os.path.join(self.root, ".along", ".session"))
        self.key_a = session.session_key("claude", "sess-a")
        self.key_b = session.session_key("claude", "sess-b")

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def start(self, slug: str, key: str, body: str = "") -> None:
        _closeout_issue(self.root, slug, body=body)
        session.init_session(self.root, slug)
        session.bind_session(self.root, slug, key=key)

    def edit(self, rel: str, sid: str = "sess-a") -> HookEvent:
        event = _edit_event(self.root, rel, sid)
        record_tool_activity(event, self.root)
        return event


class TestLedger(LedgerFixture):
    """REQ-1, REQ-2 (ADR session-event-ledger-feeds-telemetry)."""

    def test_path_kinds(self):
        self.assertEqual(session.path_kind("src/a.py"), "source")
        self.assertEqual(session.path_kind("docs/topic--x.md"), "docs")
        self.assertEqual(session.path_kind("README.md"), "docs")
        self.assertEqual(session.path_kind(".along/ISSUES/feat--a.md"), "state")
        self.assertEqual(session.path_kind("packages/ui/docs/INDEX.md"), "docs")

    def test_edits_are_attributed_to_the_bound_issue_only(self):
        self.start("alpha", self.key_a)
        self.start("beta", self.key_b)
        event = self.edit("src/a.py")
        self.edit("docs/topic--x.md")
        self.edit(".along/ISSUES/feat--alpha.md")
        self.edit("src/b.py", sid="sess-b")
        self.edit("src/u.py", sid="sess-unbound")
        alpha = session.load_events(self.root, "alpha")
        edits = [(e["path"], e["path_kind"]) for e in alpha if e["kind"] == "edit"]
        self.assertEqual(edits, [("src/a.py", "source"), ("docs/topic--x.md", "docs"),
                                 (".along/ISSUES/feat--alpha.md", "state")])
        self.assertTrue(all(e["schema"] == session.EVENT_SCHEMA and e["session"] == self.key_a for e in alpha))
        self.assertEqual(list(session.attributed_files(self.root, "beta")), ["src/b.py"])
        self.assertEqual(event.ledger_event["path"], "src/a.py")

    def test_test_runs_plans_and_approvals_are_recorded(self):
        self.start("alpha", self.key_a)
        with mock.patch.dict(os.environ, {"ALONG_SESSION_ID": "sess-a", "ALONG_SESSION_RUNTIME": "claude"}):
            session.trace_test_run(self.root, False, "along test")
            session.trace_test_run(self.root, True, "along test")
        session.record_accepted_plan(self.root, self.key_a, "1. plan")
        kinds = [(e["kind"], e["ok"]) for e in session.load_events(self.root, "alpha")]
        self.assertEqual(kinds, [("test", False), ("test", True), ("plan", None), ("approve", None)])

    def test_compaction_drops_oldest_edits_first(self):
        self.start("alpha", self.key_a)
        with mock.patch.object(session, "EVENTS_MAX", 4), mock.patch.object(session, "_EVENTS_COMPACT_BYTES", 0):
            session.append_event(self.root, "alpha", self.key_a, "test", ok=True)
            for i in range(5):
                session.append_event(self.root, "alpha", self.key_a, "edit", f"src/{i}.py")
        events = session.load_events(self.root, "alpha")
        self.assertEqual(len(events), 4)
        self.assertEqual(events[0]["kind"], "test")
        self.assertEqual([e["path"] for e in events[1:]], ["src/2.py", "src/3.py", "src/4.py"])

    def test_failed_write_is_reported(self):
        self.start("alpha", self.key_a)
        with mock.patch("builtins.open", side_effect=OSError("disk full")):
            self.assertIsNone(session.append_event(self.root, "alpha", self.key_a, "edit", "src/a.py"))
        errors = session.ledger_errors(self.root)
        self.assertEqual(errors["alpha"]["count"], 1)
        self.assertIn("disk full", errors["alpha"]["last_error"])

    def test_record_keeps_attributed_files(self):
        self.start("alpha", self.key_a)
        self.edit("src/a.py")
        self.edit("src/a.py")
        rendered = session.render_blackboard_markdown(self.root, "alpha")
        self.assertIn("### Attributed Files", rendered)
        self.assertIn("| `src/a.py` | source | 2 |", rendered)

    def test_unknown_lines_and_old_records_are_tolerated(self):
        self.start("alpha", self.key_a)
        textio.write_text(session.events_path(self.root, "alpha"),
                          'not json\n{"kind":"edit","path":"src/a.py"}\n', newline="\n")
        events = session.load_events(self.root, "alpha")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["schema"], 1)

    def test_telemetry_projection_uses_conventions(self):
        from alongkit.telemetry import conventions
        attrs = conventions.ledger_event_attributes({"schema": 1, "session": "k", "slug": "alpha", "kind": "edit",
                                                     "path": "src/a.py", "path_kind": "source", "ok": None})
        self.assertEqual(attrs[conventions.ALONG_ISSUE_SLUG], "alpha")
        self.assertEqual(attrs[conventions.ALONG_EVENT_PATH_KIND], "source")
        self.assertNotIn(conventions.ALONG_EVENT_OK, attrs)


def _co_git(root: str, *args: str) -> str:
    import subprocess
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8",
                          check=True).stdout


def _co_put(root: str, rel: str, text: str) -> None:
    textio.write_text(os.path.join(root, *rel.split("/")), text, newline="\n")


COUNTING_TEST_HOOK = (
    "#!/usr/bin/env python3\n# Status: verified\nimport os\n"
    "path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'runs.txt')\n"
    "with open(path, 'a') as f:\n    f.write('run\\n')\n"
    "raise SystemExit(1 if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "
    "'..', '..', 'FAIL')) else 0)\n"
)


class GitFixture(unittest.TestCase):
    """A real git repository with an Along context and a counting test hook."""

    def setUp(self):
        self.env = mock.patch.dict(os.environ, CLEAN_ENV, clear=True)
        self.env.start()
        self.root = tempfile.mkdtemp(prefix="along-closeout-git-")
        _co_git(self.root, "init", "-q")
        _co_git(self.root, "config", "user.email", "t@example.com")
        _co_git(self.root, "config", "user.name", "T")
        _co_put(self.root, ".gitignore", "ignored.txt\n.along/.session/\n.along/diagnostics/\n")
        _co_put(self.root, ".along/ISSUES.md", "# Active Issues\n")
        _co_put(self.root, ".along/scripts/test.py", COUNTING_TEST_HOOK)
        _co_put(self.root, "src/a.py", "a = 1\n")
        _co_put(self.root, "docs/INDEX.md", "# Index\n")
        _co_git(self.root, "add", "-A")
        _co_git(self.root, "commit", "-q", "-m", "init")

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def runs(self) -> int:
        path = os.path.join(self.root, ".along", "runs.txt")
        return len(textio.read_text(path).splitlines()) if os.path.isfile(path) else 0


class TestTestRunReuse(GitFixture):
    """REQ-8: one test run per completion."""

    def test_tree_hash_ignores_state_and_projections_only(self):
        from alongkit import testruns
        base = testruns.tree_hash(self.root)
        self.assertTrue(base)
        _co_put(self.root, ".along/ISSUES.md", "# Active Issues\n- changed\n")
        _co_put(self.root, "docs/INDEX.md", "# Index\n- regenerated\n")
        _co_put(self.root, "llms.txt", "x\n")
        _co_put(self.root, "ignored.txt", "x\n")
        self.assertEqual(testruns.tree_hash(self.root), base)
        _co_put(self.root, "src/new.py", "b = 2\n")
        self.assertNotEqual(testruns.tree_hash(self.root), base, "untracked source counts")
        os.remove(os.path.join(self.root, "src", "new.py"))
        _co_put(self.root, ".along/scripts/test.py", COUNTING_TEST_HOOK + "# changed\n")
        self.assertNotEqual(testruns.tree_hash(self.root), base, "the test hook counts")

    def test_gate_reuses_a_green_run_on_the_same_tree(self):
        from alongkit import gates
        self.assertTrue(gates.run_repository_tests(self.root, "Wrap Quality Gate"))
        _co_put(self.root, ".along/ISSUES.md", "# Active Issues\n- wrapped\n")
        self.assertTrue(gates.run_repository_tests(self.root, "Pre-Commit Quality Gate"))
        self.assertEqual(self.runs(), 1)
        _co_put(self.root, "src/a.py", "a = 2\n")
        self.assertTrue(gates.run_repository_tests(self.root, "Pre-Commit Quality Gate"))
        self.assertEqual(self.runs(), 2)

    def test_a_red_run_is_never_reused(self):
        from alongkit import gates
        _co_put(self.root, "FAIL", "1\n")
        self.assertFalse(gates.run_repository_tests(self.root, "Wrap Quality Gate"))
        self.assertFalse(gates.run_repository_tests(self.root, "Wrap Quality Gate"))
        self.assertEqual(self.runs(), 2)


AC_DONE = "\n## Acceptance Criteria\n- [x] works\n- [x] tested\n"
AC_OPEN = "\n## Acceptance Criteria\n- [x] works\n- [ ] tested\n\n## Notes\n- [ ] not a criterion\n"


class CloseoutFixture(GitFixture):
    """Git fixture with two sessions working on two issues."""

    def setUp(self):
        super().setUp()
        self.key_a = session.session_key("claude", "sess-a")
        self.key_b = session.session_key("claude", "sess-b")

    def start(self, slug: str, sid: str, body: str = AC_DONE, plan: bool = True) -> None:
        _closeout_issue(self.root, slug, body=body)
        session.init_session(self.root, slug)
        key = session.session_key("claude", sid)
        session.bind_session(self.root, slug, key=key)
        if plan:
            session.record_plan(self.root, slug, "1. plan", "test", key=key)

    def edit(self, rel: str, sid: str, text: str = "x = 1\n") -> None:
        _co_put(self.root, rel, text)
        record_tool_activity(_edit_event(self.root, rel, sid), self.root)

    def ran_tests(self, sid: str, ok: bool = True) -> None:
        with mock.patch.dict(os.environ, {"ALONG_SESSION_ID": sid, "ALONG_SESSION_RUNTIME": "claude"}):
            session.trace_test_run(self.root, ok, "along test")

    def status(self):
        from alongkit import closeout
        return closeout.closeout_status(self.root)

    def item(self, status, key):
        return next(i for i in status["items"] if i["key"] == key)


class TestAcceptanceCriteria(unittest.TestCase):
    def test_only_the_section_counts(self):
        from alongkit import entities
        self.assertEqual(entities.acceptance_criteria(AC_OPEN), (1, 2))
        self.assertEqual(entities.acceptance_criteria(AC_DONE), (2, 2))
        self.assertEqual(entities.acceptance_criteria("# x\n- [ ] free\n"), (0, 0))
        fenced = "## Acceptance Criteria\n```markdown\n- [ ] example\n```\n- [X] real\n"
        self.assertEqual(entities.acceptance_criteria(fenced), (1, 1))


class TestReadiness(CloseoutFixture):
    """REQ-3, REQ-4."""

    def test_two_sessions_exclusive_shared_and_unattributed(self):
        self.start("alpha", "sess-a")
        self.start("beta", "sess-b")
        self.edit("src/alpha.py", "sess-a")
        self.edit("src/shared.py", "sess-a")
        self.edit("src/beta.py", "sess-b")
        self.edit("src/shared.py", "sess-b", "y = 2\n")
        _co_put(self.root, "src/unrelated.py", "z = 3\n")
        self.ran_tests("sess-a")
        self.ran_tests("sess-b")
        status = self.status()
        alpha, beta = self.item(status, "feat--alpha"), self.item(status, "feat--beta")
        self.assertEqual(alpha["verdict"], "ready", alpha["reasons"])
        self.assertEqual(beta["verdict"], "ready", beta["reasons"])
        self.assertEqual(alpha["files"]["src/shared.py"]["shared_with"], ["feat--beta"])
        self.assertEqual(alpha["files"]["src/alpha.py"]["shared_with"], [])
        self.assertEqual(alpha["changed_files"], ["src/alpha.py", "src/shared.py"])
        self.assertIn("src/unrelated.py", status["repository"]["unattributed"])
        self.assertNotIn("src/shared.py", status["repository"]["unattributed"])
        self.assertEqual(alpha["sessions"][0]["key"], self.key_a)

    def test_short_and_long_path_mismatch_resolved(self):
        self.start("alpha", "sess-a")
        self.edit("src/alpha.py", "sess-a")
        self.ran_tests("sess-a")
        from alongkit import closeout
        canonical_top = os.path.realpath(self.root)
        simulated_short_root = os.path.join(os.path.dirname(self.root), "SHORT~1")

        orig_realpath = os.path.realpath

        def fake_realpath(p):
            norm = os.path.normpath(str(p))
            if norm == os.path.normpath(simulated_short_root) or norm.startswith(os.path.normpath(simulated_short_root) + os.sep):
                tail = os.path.relpath(norm, simulated_short_root)
                target = canonical_top if tail == "." else os.path.join(canonical_top, tail)
                return orig_realpath(target)
            return orig_realpath(p)

        with mock.patch("os.path.realpath", side_effect=fake_realpath):
            status = closeout.closeout_status(simulated_short_root)
            alpha = self.item(status, "feat--alpha")
            self.assertEqual(alpha["verdict"], "ready")
            self.assertIn("src/alpha.py", alpha["files"])
            self.assertEqual(alpha["files"]["src/alpha.py"]["shared_with"], [])

    def test_windows_short_path_compatibility(self):
        if sys.platform != "win32":
            return
        import ctypes
        buf = ctypes.create_unicode_buffer(500)
        res = ctypes.windll.kernel32.GetShortPathNameW(self.root, buf, 500)
        short_root = buf.value if res else self.root
        self.start("alpha", "sess-a")
        self.edit("src/alpha.py", "sess-a")
        self.ran_tests("sess-a")
        from alongkit import closeout
        status = closeout.closeout_status(short_root)
        alpha = self.item(status, "feat--alpha")
        self.assertEqual(alpha["verdict"], "ready")
        self.assertIn("src/alpha.py", alpha["files"])

    def test_blockers(self):
        self.start("alpha", "sess-a", body=AC_OPEN)
        self.start("beta", "sess-b", plan=False)
        self.edit("src/alpha.py", "sess-a")
        self.ran_tests("sess-b", ok=False)
        status = self.status()
        alpha, beta = self.item(status, "feat--alpha"), self.item(status, "feat--beta")
        self.assertIn("no test run after the last edit", alpha["reasons"])
        self.assertIn("acceptance criteria 1/2 ticked", alpha["reasons"])
        self.assertIn("no plan recorded", beta["reasons"])
        self.assertIn("last test run failed", beta["reasons"])

    def test_test_before_the_last_edit_does_not_count(self):
        self.start("alpha", "sess-a")
        self.ran_tests("sess-a")
        self.edit("src/alpha.py", "sess-a")
        self.assertIn("no test run after the last edit", self.item(self.status(), "feat--alpha")["reasons"])

    def test_ledger_error_blocks(self):
        self.start("alpha", "sess-a")
        with mock.patch("builtins.open", side_effect=OSError("denied")):
            session.append_event(self.root, "alpha", self.key_a, "edit", "src/a.py")
        self.assertTrue(any("ledger write failed" in r for r in self.item(self.status(), "feat--alpha")["reasons"]))

    def test_repository_state(self):
        _co_put(self.root, "src/a.py", "<<<<<<< ours\na = 1\n=======\na = 2\n>>>>>>> theirs\n")
        _co_put(self.root, "src/staged.py", "s = 1\n")
        _co_git(self.root, "add", "src/staged.py")
        _co_put(self.root, os.path.join(".git", "MERGE_HEAD"), "0" * 40 + "\n")
        rep = self.status()["repository"]
        self.assertEqual(rep["conflicts"], ["src/a.py"])
        self.assertEqual(rep["staged"], ["src/staged.py"])
        self.assertEqual(rep["operation"], "merge")

    def test_session_list_cli(self):
        from alongkit import proc
        self.start("alpha", "sess-a")
        exe = os.path.join(SCRIPTS_DIR, "along_exec.py")
        text = proc.run_capture([sys.executable, exe, "session", "list"], cwd=self.root)
        self.assertTrue(text.ok, text.stderr)
        self.assertIn("feat--alpha [ready]", text.stdout)
        data = proc.run_capture([sys.executable, exe, "session", "list", "--json"], cwd=self.root)
        self.assertEqual(json.loads(data.stdout)["items"][0]["key"], "feat--alpha")


class TestCloseoutPlan(unittest.TestCase):
    """REQ-5.4: commit grouping by attribution."""

    def test_groups(self):
        from alongkit import closeout

        def item(key, files, verdict="ready"):
            return {"key": key, "changed_files": files, "verdict": verdict}
        status = {"repository": {"unattributed": ["src/other.py"]}, "items": [
            item("feat--a", ["src/a.py", "src/shared.py", "src/ab_c.py"]),
            item("feat--b", ["src/b.py", "src/shared.py", "src/ab_c.py"]),
            item("feat--c", ["src/ab_c.py", "src/c.py"], verdict="blocked"),
            item("feat--d", []),
        ]}
        plan = closeout.plan_closeout(status, ["feat--a", "feat--b", "feat--d"])
        groups = {tuple(g["keys"]): g["files"] for g in plan["groups"]}
        self.assertEqual(groups[("feat--a",)], ["src/a.py"])
        self.assertEqual(groups[("feat--b",)], ["src/b.py"])
        self.assertEqual(groups[("feat--d",)], [])
        self.assertEqual(groups[("feat--a", "feat--b")], ["src/shared.py"])
        self.assertEqual([g["keys"] for g in plan["groups"]][-1], ["feat--a", "feat--b"], "shared commits last")
        self.assertEqual(plan["held"], [{"path": "src/ab_c.py", "with": ["feat--c"]}])
        self.assertEqual(plan["unattributed"], ["src/other.py"])

    def test_commit_messages(self):
        from alongkit import closeout
        self.assertEqual(closeout._commit_message(["bug--a"], {"bug--a": "Fix A"}), "fix: Fix A (refs #a)")
        self.assertIn("(refs #a) (refs #b)", closeout._commit_message(["feat--a", "feat--b"], {}))


def _run_exec(root: str, args, sid: str = None):
    from alongkit import proc
    env = dict(os.environ)
    if sid:
        env.update({"ALONG_SESSION_ID": sid, "ALONG_SESSION_RUNTIME": "claude"})
    return proc.run_capture([sys.executable, os.path.join(SCRIPTS_DIR, "along_exec.py"), *args],
                            cwd=root, env=env)


class TestCloseoutApproval(LedgerFixture):
    """REQ-6."""

    def gate(self, cmd: str, sid: str = "fresh"):
        from alongkit.hooks.predicates import check_mutation_authorization
        event = HookEvent(event_type=HookEventType.PRE_TOOL_USE, tool_name="run_command",
                          tool_args={"CommandLine": cmd}, workspace_root=self.root, runtime="claude",
                          conversation_id=sid)
        return check_mutation_authorization(event, self.root, options={"enforce_unbound": True})

    def test_fresh_session_commits_approved_issues_only(self):
        fresh = session.session_key("claude", "fresh")
        self.assertIn("closeout approval", self.gate('along commit "x" -i alpha --paths a.py') or "")
        session.record_closeout_approval(self.root, fresh, ["alpha", "beta"])
        self.assertIsNone(self.gate('along commit "x" -i alpha --paths a.py'))
        self.assertIsNone(self.gate('along commit "x" -i feat--beta --paths b.py'))
        self.assertIsNotNone(self.gate('along commit "x" -i gamma --paths c.py'))
        self.assertIsNotNone(self.gate('along commit "x" -i alpha --paths a.py', sid="other"))
        self.assertIsNotNone(self.gate("touch src/a.py"), "a closeout approval is not a plan approval")

    def test_consumed_and_expiring(self):
        from datetime import datetime, timedelta, timezone
        fresh = session.session_key("claude", "fresh")
        session.record_closeout_approval(self.root, fresh, ["alpha", "beta"])
        later = datetime.now(timezone.utc) + timedelta(hours=session.BINDING_MAX_AGE_HOURS + 1)
        self.assertEqual(session.closeout_approved(self.root, fresh, now=later), [])
        session.consume_closeout_approval(self.root, fresh, ["alpha"])
        self.assertEqual(session.closeout_approved(self.root, fresh), ["beta"])
        session.consume_closeout_approval(self.root, fresh, ["beta"])
        self.assertIsNone(session.load_binding(self.root, fresh), "an empty binding is removed")

    def test_token_consumption_keeps_a_closeout_binding(self):
        session.save_binding(self.root, self.key_a, {"slug": None, "completed": [
            {"slug": "alpha", "approved_at": None, "wrapped_at": session._utc_now_iso()}]})
        session.record_closeout_approval(self.root, self.key_a, ["beta"])
        session.consume_completion_token(self.root, self.key_a, "alpha")
        self.assertEqual(session.closeout_approved(self.root, self.key_a), ["beta"])

    def test_cli(self):
        res = _run_exec(self.root, ["plan", "approve", "--closeout", "feat--alpha", "beta"], sid="cli")
        self.assertTrue(res.ok, res.stderr)
        self.assertEqual(session.closeout_approved(self.root, session.session_key("claude", "cli")), ["alpha", "beta"])
        empty = _run_exec(self.root, ["plan", "approve", "--closeout", "--ready"], sid="cli")
        self.assertEqual(empty.returncode, 2)


class TestReopenAndDoctor(unittest.TestCase):
    """REQ-7, REQ-9."""

    def setUp(self):
        from tests import hermetic
        self.env = mock.patch.dict(os.environ, CLEAN_ENV, clear=True)
        self.env.start()
        self.root = hermetic.make_repo_fixture()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_reopen_round_trip(self):
        from alongkit import entities, frontmatter
        slug = "fixture-sample-task"
        self.assertTrue(_run_exec(self.root, ["issue", "done", slug, "--status", "superseded",
                                              "--superseded-by", "task--x"]).ok)
        res = _run_exec(self.root, ["issue", "reopen", slug])
        self.assertTrue(res.ok, res.stderr)
        issue = entities.find_issue_by_slug(self.root, slug)
        self.assertEqual(issue["status"], "open")
        self.assertNotIn("done", os.path.normpath(issue["file_path"]).split(os.sep))
        fm, _body = frontmatter.parse(textio.read_text(issue["file_path"]))
        self.assertNotIn("completed", fm)
        self.assertNotIn("superseded_by", fm)
        self.assertIn(f"{slug}", textio.read_text(os.path.join(self.root, ".along", "ISSUES.md")))
        again = _run_exec(self.root, ["issue", "reopen", slug])
        self.assertEqual(again.returncode, 1)

    def test_doctor_reports_stale_bindings_and_unbound_work(self):
        slug = "fixture-sample-task"
        self.assertTrue(_run_exec(self.root, ["issue", "update", slug, "--status", "in-progress"]).ok)
        key = session.session_key("claude", "old")
        session.save_binding(self.root, key, {"slug": "gone"})
        res = _run_exec(self.root, ["doctor"])
        self.assertIn("stale session binding(s)", res.stdout)
        self.assertIn(f"issue(s) in progress with no session bound: {slug}", res.stdout)


class TestCloseoutScenario(unittest.TestCase):
    """Two sessions, two issues, one shared file, one unrelated change, one issue not ready:
    one closeout closes both ready issues, commits by attribution, pushes once."""

    def setUp(self):
        from tests import hermetic
        self.env = mock.patch.dict(os.environ, CLEAN_ENV, clear=True)
        self.env.start()
        self.root = hermetic.make_repo_fixture(prefix="along-closeout-scenario-")
        self.remote = tempfile.mkdtemp(prefix="along-closeout-remote-")
        _co_git(self.remote, "init", "-q", "--bare")
        _co_git(self.root, "init", "-q")
        _co_git(self.root, "config", "user.email", "t@example.com")
        _co_git(self.root, "config", "user.name", "T")
        _co_put(self.root, ".gitignore", ".along/.session/\n.along/artifacts/\n")
        _co_put(self.root, ".along/scripts/test.py", COUNTING_TEST_HOOK)
        _co_put(self.root, ".along/.gitignore", "runs.txt\n")
        _co_put(self.root, "src/shared.py", "s = 0\n")
        _co_git(self.root, "add", "-A")
        _co_git(self.root, "commit", "-q", "-m", "init")
        _co_git(self.root, "remote", "add", "origin", self.remote)
        _co_git(self.root, "push", "-q", "-u", "origin", "HEAD")
        self.base = _co_git(self.root, "rev-parse", "HEAD").strip()
        self.work("alpha", "sess-a", ["src/alpha.py", "src/shared.py"])
        self.work("beta", "sess-b", ["src/beta.py", "src/shared.py"])
        self.work("gamma", "sess-c", ["src/gamma.py"], body=AC_OPEN)
        _co_put(self.root, "src/unrelated.py", "u = 1\n")
        self.closer = session.session_key("claude", "closer")

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(self.remote, ignore_errors=True)

    def work(self, slug: str, sid: str, files, body: str = AC_DONE) -> None:
        key = session.session_key("claude", sid)
        _closeout_issue(self.root, slug, body=body)
        session.init_session(self.root, slug)
        session.bind_session(self.root, slug, key=key)
        session.record_plan(self.root, slug, f"1. implement {slug}", "test", key=key)
        for rel in files:
            path = os.path.join(self.root, *rel.split("/"))
            old = textio.read_text(path) if os.path.isfile(path) else ""
            _co_put(self.root, rel, old + f"# {slug}\n")
            record_tool_activity(_edit_event(self.root, rel, sid), self.root)
        with mock.patch.dict(os.environ, {"ALONG_SESSION_ID": sid, "ALONG_SESSION_RUNTIME": "claude"}):
            session.trace_test_run(self.root, True, "along test")

    def close(self, **kwargs) -> int:
        from alongkit import closeout
        return closeout.run_closeout(self.root, session_key=self.closer, **kwargs)

    def commits(self):
        """(subject, {paths}) of the commits after the fixture's base, oldest first."""
        out = []
        for sha in _co_git(self.root, "rev-list", "--reverse", f"{self.base}..HEAD").split():
            subject = _co_git(self.root, "log", "-1", "--format=%s", sha).strip()
            names = _co_git(self.root, "show", "--name-only", "--format=", sha).split()
            out.append((subject, set(names)))
        return out

    def runs(self) -> int:
        path = os.path.join(self.root, ".along", "runs.txt")
        return len(textio.read_text(path).splitlines()) if os.path.isfile(path) else 0

    def test_full_closeout(self):
        from alongkit import entities
        session.record_closeout_approval(self.root, self.closer, ["alpha", "beta"])
        self.assertEqual(self.close(ready=True, push=True), 0)
        commits = self.commits()
        subjects = [s for s, _ in commits]
        self.assertEqual(len(commits), 4, subjects)
        alpha, beta, shared, projections = commits
        self.assertIn("src/alpha.py", alpha[1])
        self.assertIn(".along/ISSUES/done/feat--alpha.md", alpha[1])
        self.assertTrue(any(p.startswith(".along/SESSIONS/") for p in alpha[1]))
        self.assertIn("(refs #alpha)", alpha[0])
        self.assertIn("src/beta.py", beta[1])
        self.assertEqual(shared[1], {"src/shared.py"})
        self.assertIn("(refs #alpha) (refs #beta)", shared[0])
        self.assertIn(".along/ISSUES.md", projections[1])
        status = _co_git(self.root, "status", "--porcelain", "-uall")
        self.assertIn("src/unrelated.py", status)
        self.assertIn("src/gamma.py", status)
        self.assertEqual(entities.find_issue_by_slug(self.root, "gamma")["status"], "in-progress")
        self.assertEqual(entities.find_issue_by_slug(self.root, "alpha")["status"], "done")
        self.assertEqual(_co_git(self.remote, "rev-parse", "HEAD").strip(),
                         _co_git(self.root, "rev-parse", "HEAD").strip(), "pushed once at the end")
        self.assertEqual(self.runs(), 1, "one test run for the whole closeout")
        self.assertIn("docs/topic--architecture.md", projections[1], "KB provenance the wraps rewrote")
        self.assertEqual(session.closeout_approved(self.root, self.closer), [], "approval consumed")
        log = textio.read_text(os.path.join(self.root, ".along", "SESSIONS", entities.today_iso()[:4],
                                            f"{entities.today_iso()}--alpha.md"))
        self.assertIn("### Attributed Files", log)
        self.assertIn("`src/shared.py`", log)

    def test_resume_after_a_failed_commit(self):
        from alongkit import closeout
        session.record_closeout_approval(self.root, self.closer, ["alpha", "beta"])
        real = closeout._commit
        calls = {"n": 0}

        def flaky(*args, **kwargs):
            calls["n"] += 1
            return 1 if calls["n"] == 2 else real(*args, **kwargs)
        with mock.patch.object(closeout, "_commit", side_effect=flaky):
            self.assertEqual(self.close(ready=True), 1)
        self.assertTrue(os.path.isfile(closeout.run_file(self.root)))
        self.assertEqual(self.close(), 0, "a re-run continues")
        self.assertEqual(len(self.commits()), 4)
        history = textio.read_text(os.path.join(self.root, ".along", "HISTORY.md"))
        self.assertEqual(history.count(" - alpha - "), 1, "no issue wrapped twice")
        self.assertFalse(os.path.isfile(closeout.run_file(self.root)))

    def test_red_tests_touch_nothing(self):
        from alongkit import entities
        session.record_closeout_approval(self.root, self.closer, ["alpha", "beta"])
        _co_put(self.root, "FAIL", "1\n")
        self.assertEqual(self.close(ready=True), 1)
        self.assertEqual(self.commits(), [])
        self.assertEqual(entities.find_issue_by_slug(self.root, "alpha")["status"], "in-progress")

    def test_without_approval_nothing_happens(self):
        self.assertEqual(self.close(ready=True), 2)
        self.assertEqual(self.commits(), [])
        session.record_closeout_approval(self.root, self.closer, ["alpha"])
        self.assertEqual(self.close(keys=["alpha", "beta"]), 2, "every closed issue must be approved")

    def test_named_not_ready_issue_is_left_untouched(self):
        session.record_closeout_approval(self.root, self.closer, ["alpha", "gamma"])
        self.assertEqual(self.close(keys=["alpha", "gamma"]), 0)
        subjects = [s for s, _ in self.commits()]
        self.assertTrue(all("gamma" not in s for s in subjects), subjects)
        status = _co_git(self.root, "status", "--porcelain", "-uall")
        self.assertIn("src/shared.py", status, "shared with beta, which is not closed now: held back")

    def test_a_source_change_during_the_wraps_is_tested_again(self):
        from alongkit import lifecycle
        session.record_closeout_approval(self.root, self.closer, ["alpha", "beta"])
        real = lifecycle.execute_wrap

        def wrap_while_someone_edits(*args, **kwargs):
            _co_put(self.root, "src/gamma.py", "edited during the closeout\n")
            return real(*args, **kwargs)
        with mock.patch.object(lifecycle, "execute_wrap", side_effect=wrap_while_someone_edits):
            self.assertEqual(self.close(ready=True), 0)
        self.assertEqual(self.runs(), 2, "the green run is not carried over a source change")
        self.assertTrue(all("src/gamma.py" not in files for _s, files in self.commits()))

    def test_dry_run_writes_nothing(self):
        from alongkit import closeout
        before = _co_git(self.root, "status", "--porcelain", "-uall")
        self.assertEqual(self.close(ready=True, dry_run=True), 0)
        self.assertEqual(_co_git(self.root, "status", "--porcelain", "-uall"), before)
        self.assertFalse(os.path.isfile(closeout.run_file(self.root)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
