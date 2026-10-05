#!/usr/bin/env python3
"""
tests/test_hook_activation.py - When the runtime hooks apply, where their state goes, and what
the plan and test gates hold. Regression suite for [bug--hook-activation-and-gate-deadlock]:

- a bare AGENTS.md activated every gate in repositories that never adopted Along;
- a root whose state lives elsewhere (`<dir>/.local/.along/`) could not be declared;
- diagnostics created `.along/` in whatever directory the session sat in, which then counted
  as a subproject and blocked every edit under it;
- `awk` and build/lint commands were rejected as mutations in the inquiry phase;
- a write a gate rejected still counted as "source modified" for test-before-stop;
- sessions not bound to an issue were held by the plan and test gates.
"""

from __future__ import annotations

import json
import os
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
from alongkit import circuit, hookpreflight, repo, session
from alongkit.hooks import HookEngine, HookEvent, HookEventType, HooksConfig
from alongkit.hooks.predicates import (
    check_mutation_authorization,
    check_subproject_boundary,
    check_test_before_stop,
    load_activity_trace,
    record_tool_activity,
)
from alongkit.hooks.shellparse import is_read_only_command, is_verification_command

HOOK = os.path.join(SCRIPTS_DIR, "along_hook.py")


def _put(path: str, text: str = "") -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


def _along(root: str) -> str:
    """Make `root` an Along context (a state directory with real content)."""
    _put(os.path.join(root, ".along", "ISSUES.md"), "# Active Issues\n")
    os.makedirs(os.path.join(root, ".along", "ISSUES"), exist_ok=True)
    return root


def _edit_tool_event(target: str, root: str, event_type=HookEventType.PRE_TOOL_USE, key="sess-1") -> HookEvent:
    return HookEvent(event_type=event_type, tool_name="write_to_file",
                     tool_args={"TargetFile": target, "CodeContent": "x = 1\n"},
                     workspace_root=root, runtime="claude", conversation_id=key)


def _bash_tool_event(cmd: str, root: str, key="sess-1") -> HookEvent:
    return HookEvent(event_type=HookEventType.PRE_TOOL_USE, tool_name="run_command",
                     tool_args={"CommandLine": cmd}, workspace_root=root, runtime="claude",
                     conversation_id=key)


class _TempRoot(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along-activation-")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)


class TestContextResolution(_TempRoot):
    def test_bare_agents_md_is_not_a_context(self):
        _put(os.path.join(self.root, "AGENTS.md"), "# Team instructions\n")
        self.assertIsNone(repo.find_hook_root(self.root))
        self.assertIsNone(repo.find_state_dir(self.root))

    def test_diagnostics_only_along_is_not_a_context(self):
        _put(os.path.join(self.root, ".along", "diagnostics", "hook_heartbeat.json"), "{}\n")
        _put(os.path.join(self.root, ".along", "diagnostics", ".gitignore"), "*\n")
        self.assertFalse(repo.is_along_state_dir(os.path.join(self.root, ".along")))
        self.assertIsNone(repo.find_hook_root(self.root))

    def test_foreign_agents_dir_is_not_a_context(self):
        os.makedirs(os.path.join(self.root, ".agents", "skills", "x"))
        self.assertIsNone(repo.find_hook_root(self.root))
        _put(os.path.join(self.root, ".agents", "ISSUES.md"), "# Active Issues\n")
        self.assertIsNotNone(repo.find_hook_root(self.root))

    def test_real_along_activates_from_a_subdirectory(self):
        _along(self.root)
        sub = os.path.join(self.root, "pkg", "src")
        os.makedirs(sub)
        self.assertTrue(repo._same_path(repo.find_hook_root(sub), self.root))

    def test_agents_md_pointer_declares_a_nested_root(self):
        _put(os.path.join(self.root, "AGENTS.md"), "# Team\n\n<!-- along-root: .local -->\n")
        _along(os.path.join(self.root, ".local"))
        sub = os.path.join(self.root, "Service", "Core")
        os.makedirs(sub)
        self.assertTrue(repo._same_path(repo.find_hook_root(sub), self.root))
        self.assertTrue(repo._same_path(repo.state_dir(self.root),
                                        os.path.join(self.root, ".local", ".along")))
        owner, sdir = repo.find_context(sub)
        self.assertTrue(repo._same_path(owner, self.root))

    def test_pointer_to_missing_state_does_not_activate(self):
        _put(os.path.join(self.root, "AGENTS.md"), "<!-- along-root: .local -->\n")
        self.assertIsNone(repo.find_hook_root(self.root))

    def test_config_context_roots_declare_a_root(self):
        home = tempfile.mkdtemp(prefix="along-home-")
        try:
            _along(os.path.join(self.root, "state"))
            _put(os.path.join(home, ".along", "config.json"), json.dumps(
                {"context_roots": [{"workspace": self.root, "root": "state"}]}))
            with mock.patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}):
                self.assertTrue(repo._same_path(repo.find_hook_root(self.root), self.root))
                self.assertTrue(repo._same_path(repo.state_dir(self.root),
                                                os.path.join(self.root, "state", ".along")))
        finally:
            shutil.rmtree(home, ignore_errors=True)


class TestDiagnosticsPlacement(_TempRoot):
    def test_no_state_dir_goes_to_global_diagnostics(self):
        home = tempfile.mkdtemp(prefix="along-home-")
        try:
            with mock.patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}):
                path = repo.ensure_diagnostics_dir(self.root)
            self.assertFalse(os.path.exists(os.path.join(self.root, ".along")))
            self.assertTrue(repo.is_within(path, os.path.join(home, ".along", "diagnostics")))
        finally:
            shutil.rmtree(home, ignore_errors=True)

    def test_declared_root_keeps_diagnostics_in_its_state(self):
        _put(os.path.join(self.root, "AGENTS.md"), "<!-- along-root: .local -->\n")
        _along(os.path.join(self.root, ".local"))
        path = repo.ensure_diagnostics_dir(self.root)
        self.assertTrue(repo._same_path(path, os.path.join(self.root, ".local", ".along", "diagnostics")))
        self.assertFalse(os.path.exists(os.path.join(self.root, ".along")))


class TestHookProcess(_TempRoot):
    """The hook as the runtime runs it: a subprocess fed a JSON payload on stdin."""

    def _run(self, payload: dict, event="PreToolUse", runtime="claude", project_dir=None):
        env = hermetic.isolated_home_env()
        env.pop("CLAUDE_PROJECT_DIR", None)
        if project_dir:
            env["CLAUDE_PROJECT_DIR"] = project_dir
        return subprocess.run([sys.executable, HOOK, "--runtime", runtime, "--event", event],
                              input=json.dumps(payload).encode("utf-8"), capture_output=True,
                              env=env, cwd=self.root, timeout=120)

    def test_bare_agents_md_allows_and_creates_nothing(self):
        _put(os.path.join(self.root, "AGENTS.md"), "# Team instructions\n")
        sub = os.path.join(self.root, "Service")
        os.makedirs(sub)
        target = os.path.join(sub, "a.cs")
        done = self._run({"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": sub,
                          "tool_input": {"file_path": target, "content": "class A {}\n"}})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stderr.strip(), b"")
        for current, dirs, _files in os.walk(self.root):
            self.assertNotIn(".along", dirs, f"hook created .along/ under {current}")

    def test_stray_diagnostics_dir_does_not_block_edits(self):
        _along(self.root)
        sub = os.path.join(self.root, "Service")
        _put(os.path.join(sub, ".along", "diagnostics", "hook_heartbeat.json"), "{}\n")
        event = _edit_tool_event(os.path.join(sub, "a.py"), self.root)
        self.assertIsNone(check_subproject_boundary(event, self.root))

    def test_antigravity_allow_outside_a_context_is_json(self):
        done = self._run({"toolCall": {"name": "write_to_file", "args": {"TargetFile": "x"}},
                          "workspacePaths": [self.root]}, runtime="antigravity")
        self.assertEqual(done.returncode, 0)
        self.assertEqual(json.loads(done.stdout.decode("utf-8")), {"decision": "allow"})

    def test_workspace_read_answers_without_the_pipeline(self):
        _along(self.root)
        payload = {"tool_name": "Read", "cwd": self.root,
                   "tool_input": {"file_path": os.path.join(self.root, "src", "a.py")}}
        self.assertEqual(hookpreflight.preflight(json.dumps(payload), "claude", "PreToolUse"), (0, ""))
        docs = {"tool_name": "Grep", "cwd": self.root, "tool_input": {"path": os.path.join(self.root, "docs")}}
        self.assertIsNone(hookpreflight.preflight(json.dumps(docs), "claude", "PreToolUse"))
        outside = {"tool_name": "Read", "cwd": self.root,
                   "tool_input": {"file_path": os.path.join(os.path.dirname(self.root), "other.txt")}}
        self.assertIsNone(hookpreflight.preflight(json.dumps(outside), "claude", "PreToolUse"))

    def test_gates_still_run_inside_a_context(self):
        _along(self.root)
        done = self._run({"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": self.root,
                          "tool_input": {"command": "git reset --hard"}})
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertIn(b"CLI Safety", done.stderr)


class TestShellClassification(unittest.TestCase):
    def test_reported_audit_command_is_read_only(self):
        cmd = ("cd /d/work/Service && sed -n 25,62p X.cs; echo ---; grep -rn \"pattern\" --include=*.cs . "
               "| grep -v \"/obj/\" | awk -F: '{print $1\":\"$2}'; echo ---; git log --oneline -3 -- X.cs")
        self.assertTrue(is_read_only_command(cmd))

    def test_awk_reads(self):
        for cmd in ("awk '{print $1}' f", "awk -F, -v n=2 '$3 > 5 {print $n}' f", "gawk 'END {print NR}' f"):
            with self.subTest(cmd=cmd):
                self.assertTrue(is_read_only_command(cmd))

    def test_awk_writes(self):
        for cmd in ("awk '{print > \"out.txt\"}' f", "awk '{print | \"sh\"}' f", "awk 'BEGIN {system(\"rm x\")}'",
                    "gawk -i inplace '{print}' f", "awk -f prog.awk f", "awk '{print}' f > out"):
            with self.subTest(cmd=cmd):
                self.assertFalse(is_read_only_command(cmd))

    def test_verification_commands(self):
        for cmd in ("dotnet build -v q", "dotnet test", "cargo check", "cargo clippy", "go vet ./...",
                    "npm run lint", "pnpm build", "tsc --noEmit", "mypy scripts", "ruff check .",
                    "cd src && dotnet build", "along build", "python .along/scripts/test.py"):
            with self.subTest(cmd=cmd):
                self.assertTrue(is_verification_command(cmd))

    def test_rewriting_or_redirected_runs_are_not_verification(self):
        for cmd in ("dotnet format", "eslint --fix .", "ruff check --fix .", "cargo clippy --fix",
                    "dotnet build > build.log", "npm install", "dotnet build && rm -rf src", "jest -u"):
            with self.subTest(cmd=cmd):
                self.assertFalse(is_verification_command(cmd))


class TestPlanGate(_TempRoot):
    def setUp(self):
        super().setUp()
        _along(self.root)
        self.src = os.path.join(self.root, "src", "a.py")

    def test_unbound_session_is_not_held_by_default(self):
        self.assertIsNone(check_mutation_authorization(_edit_tool_event(self.src, self.root), self.root))

    def test_unbound_session_is_held_when_the_repository_opts_in(self):
        reason = check_mutation_authorization(_edit_tool_event(self.src, self.root), self.root,
                                              options={"enforce_unbound": True})
        self.assertIn("require-plan-approval", reason or "")

    def test_bound_session_without_approval_is_held(self):
        session.bind_session(self.root, "work", key=session.session_key("claude", "sess-1"))
        self.assertIn("require-plan-approval",
                      check_mutation_authorization(_edit_tool_event(self.src, self.root), self.root) or "")

    def test_verification_passes_for_a_bound_unapproved_session(self):
        session.bind_session(self.root, "work", key=session.session_key("claude", "sess-1"))
        self.assertIsNone(check_mutation_authorization(_bash_tool_event("dotnet build -v q", self.root), self.root))
        self.assertIsNotNone(check_mutation_authorization(_bash_tool_event("rm -rf src", self.root), self.root))

    def test_along_commit_passes_for_an_unbound_session(self):
        """The completion checklist commits after `along wrap` unbound the session.

        See [bug--commit-blocked-after-wrap].
        """
        enforce = {"enforce_unbound": True}
        for cmd in ('along commit "fix x" -i x --all --push',
                    'python scripts/along_exec.py commit "fix x" -i x --all',
                    'along issue sync; along commit "fix x" -i x --all --push'):
            with self.subTest(cmd=cmd):
                self.assertIsNone(check_mutation_authorization(_bash_tool_event(cmd, self.root),
                                                               self.root, options=enforce))

    def test_rewriting_commit_and_raw_git_commit_stay_held(self):
        enforce = {"enforce_unbound": True}
        for cmd in ('along commit "fix x" -i x --all --fix-typography',
                    'git commit -am "fix x"', 'git push',
                    'along commit "fix x" -i x --all && rm -rf src',
                    'along commit "fix x" > out.txt'):
            with self.subTest(cmd=cmd):
                self.assertIn("require-plan-approval",
                              check_mutation_authorization(_bash_tool_event(cmd, self.root),
                                                           self.root, options=enforce) or "")

    def test_commit_right_after_wrap_purge(self):
        """Bind, approve, purge (what `along wrap` does), then commit: the commit passes."""
        key = session.session_key("claude", "sess-1")
        session.init_session(self.root, "work")
        session.bind_session(self.root, "work", key=key)
        session.record_plan_approval(self.root, key)
        session.purge_session(self.root, "work")
        enforce = {"enforce_unbound": True}
        self.assertIsNone(check_mutation_authorization(
            _bash_tool_event('along commit "fix" -i work --all --push', self.root), self.root, options=enforce))
        self.assertIsNotNone(check_mutation_authorization(
            _edit_tool_event(self.src, self.root), self.root, options=enforce),
            "source edits still need a new binding and approval")

    def test_declared_root_whitelists_its_state_paths(self):
        nested = tempfile.mkdtemp(prefix="along-declared-")
        try:
            _put(os.path.join(nested, "AGENTS.md"), "<!-- along-root: .local -->\n")
            _along(os.path.join(nested, ".local"))
            issue = os.path.join(nested, ".local", ".along", "ISSUES", "bug--x.md")
            reason = check_mutation_authorization(_edit_tool_event(issue, nested), nested,
                                                  options={"enforce_unbound": True})
            self.assertIsNone(reason)
            self.assertIsNone(check_subproject_boundary(_edit_tool_event(issue, nested), nested))
        finally:
            shutil.rmtree(nested, ignore_errors=True)


class TestActivityTrace(_TempRoot):
    def setUp(self):
        super().setUp()
        _along(self.root)
        self.key = session.session_key("claude", "sess-1")
        self.src = os.path.join(self.root, "src", "a.py")

    def test_pre_tool_write_is_not_an_edit(self):
        record_tool_activity(_edit_tool_event(self.src, self.root), self.root)
        self.assertIsNone(load_activity_trace(self.root, self.key).get("last_edit_time"))
        record_tool_activity(_edit_tool_event(self.src, self.root, HookEventType.POST_TOOL_USE), self.root)
        self.assertIsNotNone(load_activity_trace(self.root, self.key).get("last_edit_time"))

    def test_rejected_write_never_reaches_the_trace(self):
        _put(os.path.join(self.root, ".along", "rules", "gates.yaml"),
               "version: 1\ngates:\n  - id: require_plan_approval\n    enforce_unbound: true\n")
        engine = HookEngine(config=HooksConfig(mode="enforce"), repo_root=self.root)
        result = engine.evaluate(_edit_tool_event(self.src, self.root), repo_root=self.root)
        self.assertTrue(result.is_denied)
        self.assertIsNone(load_activity_trace(self.root, self.key).get("last_edit_time"))

    def test_unbound_session_and_tripped_breaker_do_not_demand_tests(self):
        stop = HookEvent(event_type=HookEventType.STOP, workspace_root=self.root, runtime="claude",
                         conversation_id="sess-1")
        record_tool_activity(_edit_tool_event(self.src, self.root, HookEventType.POST_TOOL_USE), self.root)
        self.assertIsNone(check_test_before_stop(stop, self.root))
        enforce = {"enforce_unbound": True}
        self.assertIn("test-before-stop", check_test_before_stop(stop, self.root, options=enforce) or "")
        with mock.patch.object(circuit, "get_breaker_state",
                               return_value=(circuit.CircuitState.TRIPPED, None)):
            self.assertIsNone(check_test_before_stop(stop, self.root, options=enforce))


if __name__ == "__main__":
    unittest.main()
