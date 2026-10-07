#!/usr/bin/env python3
"""
tests/test_workspace_containment.py - `[gate: workspace-containment]`.

Covers [feat--workspace-containment-and-path-scoping]: canonical path resolution, the
built-in whitelist (temp, brain artifacts, global skill dirs read-only, credential stores
never), read/write asymmetry, `allowed_roots` / `write_scope` from `.along/rules/gates.yaml`
and issue frontmatter, shell `Cwd`, mode-aware ASK/DENY, repo override merging, and
`along start --allow-root/--write-scope`. Every fixture lives in a throwaway directory; the
home and temp dirs are redirected into it.
"""

from __future__ import annotations

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

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit.hooks import containment
from alongkit.hooks.declarative import DEFAULT_GATES_FILE, get_all_declarative_gates, load_gate_definitions
from alongkit.hooks.models import GateDecision, HookEvent, HookEventType
from alongkit.hooks.predicates import check_workspace_containment


def _wc_write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _wc_issue(ws, slug, status="in-progress", extra=""):
    _wc_write(os.path.join(ws, ".along", "ISSUES", f"feat--{slug}.md"),
              f"---\nslug: {slug}\ntype: feat\nstatus: {status}\n{extra}---\n\n# {slug}\n")


def _wc_event(tool, args=None, payload=None, conversation_id=None, workspace_root=""):
    return HookEvent(event_type=HookEventType.PRE_TOOL_USE, tool_name=tool, tool_args=args or {},
                     workspace_root=workspace_root, runtime="claude-code",
                     conversation_id=conversation_id, raw_payload=payload or {})


class _ContainmentFixture(unittest.TestCase):
    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="along_wc_"))
        self.ws = os.path.join(self.base, "ws")
        self.home = os.path.join(self.base, "home")
        self.tmp = os.path.join(self.base, "tmp")
        self.sibling = os.path.join(self.base, "sibling")
        for d in (self.ws, self.home, self.tmp, self.sibling):
            os.makedirs(d)
        os.makedirs(os.path.join(self.ws, ".along", "ISSUES"))
        env = {"HOME": self.home, "USERPROFILE": self.home, containment.AUTONOMOUS_ENV: ""}
        self._patches = [
            mock.patch.dict(os.environ, env),
            mock.patch.object(containment.tempfile, "gettempdir", return_value=self.tmp),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        shutil.rmtree(self.base, ignore_errors=True)

    def run_gate(self, tool, args=None, options=None, **kw):
        return check_workspace_containment(_wc_event(tool, args, **kw), repo_root=self.ws,
                                           options=options)


class TestCanonicalPaths(_ContainmentFixture):
    def test_dotdot_traversal_is_resolved(self):
        sneaky = os.path.join(self.ws, "src", "..", "..", "sibling", "x.py")
        res = self.run_gate("write_to_file", {"TargetFile": sneaky})
        self.assertEqual(res.decision, GateDecision.DENY)
        self.assertIn("sibling", res.reason)

    def test_relative_path_resolves_against_workspace(self):
        self.assertIsNone(self.run_gate("write_to_file", {"TargetFile": "src/app.py"}))
        res = self.run_gate("write_to_file", {"TargetFile": "../sibling/app.py"})
        self.assertEqual(res.decision, GateDecision.DENY)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unsupported")
    def test_symlink_escape_is_resolved(self):
        link = os.path.join(self.ws, "escape")
        try:
            os.symlink(self.sibling, link, target_is_directory=True)
        except OSError:
            self.skipTest("symlink creation not permitted")
        res = self.run_gate("write_to_file", {"TargetFile": os.path.join(link, "x.py")})
        self.assertEqual(res.decision, GateDecision.DENY)


class TestDefaultWhitelist(_ContainmentFixture):
    def test_workspace_read_and_write_allowed(self):
        target = os.path.join(self.ws, "packages", "a", "x.ts")
        self.assertIsNone(self.run_gate("write_to_file", {"TargetFile": target}))
        self.assertIsNone(self.run_gate("view_file", {"file_path": target}))

    def test_temp_dir_writable(self):
        self.assertIsNone(self.run_gate("write_to_file", {"TargetFile": os.path.join(self.tmp, "f", "t.py")}))

    def test_brain_dir_scoped_to_conversation(self):
        brain = os.path.join(self.home, ".gemini", "antigravity", "brain")
        own = os.path.join(brain, "conv-1", "implementation_plan.md")
        other = os.path.join(brain, "conv-2", "implementation_plan.md")
        self.assertIsNone(self.run_gate("write_to_file", {"TargetFile": own}, conversation_id="conv-1"))
        res = self.run_gate("write_to_file", {"TargetFile": other}, conversation_id="conv-1")
        self.assertEqual(res.decision, GateDecision.DENY)

    def test_claude_project_memory_writable(self):
        mem = os.path.join(self.home, ".claude", "projects", "p", "memory", "m.md")
        self.assertIsNone(self.run_gate("write_to_file", {"TargetFile": mem}))

    def test_claude_plan_dir_writable(self):
        # Claude Code plan mode writes here [bug--runtime-plan-dir-containment].
        plan = os.path.join(self.home, ".claude", "plans", "lively-plan.md")
        self.assertIsNone(self.run_gate("write_to_file", {"TargetFile": plan}))
        settings = os.path.join(self.home, ".claude", "settings.json")
        res = self.run_gate("write_to_file", {"TargetFile": settings})
        self.assertEqual(res.decision, GateDecision.DENY)

    def test_global_skill_dirs_read_only(self):
        skill = os.path.join(self.home, ".claude", "skills", "x", "SKILL.md")
        self.assertIsNone(self.run_gate("view_file", {"file_path": skill}))
        res = self.run_gate("write_to_file", {"TargetFile": skill})
        self.assertEqual(res.decision, GateDecision.DENY)
        self.assertIn("writes are limited", res.reason)

    def test_credential_store_never_readable(self):
        key = os.path.join(self.home, ".ssh", "id_ed25519")
        res = self.run_gate("view_file", {"file_path": key}, options={"on_violation": "ask"})
        self.assertEqual(res.decision, GateDecision.DENY)
        self.assertIn("credential store", res.reason)

    def test_pathless_tools_ignored(self):
        self.assertIsNone(self.run_gate("read_url_content", {"Url": "https://example.com"}))
        self.assertIsNone(self.run_gate("run_command", {"CommandLine": "git status"}))


class TestReadWriteAsymmetry(_ContainmentFixture):
    def test_sibling_read_asks_interactively(self):
        res = self.run_gate("view_file", {"file_path": os.path.join(self.sibling, "a.py")})
        self.assertEqual(res.decision, GateDecision.ASK)
        self.assertIn("allowed_roots", res.reason)

    def test_sibling_read_denied_when_autonomous(self):
        path = os.path.join(self.sibling, "a.py")
        res = self.run_gate("view_file", {"file_path": path}, payload={"permission_mode": "bypassPermissions"})
        self.assertEqual(res.decision, GateDecision.DENY)
        with mock.patch.dict(os.environ, {containment.AUTONOMOUS_ENV: "1"}):
            self.assertEqual(self.run_gate("view_file", {"file_path": path}).decision, GateDecision.DENY)
        res = self.run_gate("view_file", {"file_path": path}, options={"on_violation": "deny"})
        self.assertEqual(res.decision, GateDecision.DENY)

    def test_search_tools_checked(self):
        res = self.run_gate("grep_search", {"path": self.sibling, "pattern": "TODO"})
        self.assertEqual(res.decision, GateDecision.ASK)
        glob = self.sibling.replace(os.sep, "/") + "/**/*.py"
        res = self.run_gate("find_by_name", {"pattern": glob})
        self.assertEqual(res.decision, GateDecision.ASK)
        self.assertIsNone(self.run_gate("find_by_name", {"pattern": "**/*.py"}))

    def test_shell_cwd_outside_denied_or_asked(self):
        self.assertIsNone(self.run_gate("run_command", {"CommandLine": "ls", "Cwd": self.ws}))
        res = self.run_gate("run_command", {"CommandLine": "ls", "Cwd": self.sibling})
        self.assertEqual(res.decision, GateDecision.ASK)
        self.assertIn("Shell working directory", res.reason)


class TestDeclaredScopes(_ContainmentFixture):
    def test_allowed_roots_option_expands_read_not_write(self):
        opts = {"allowed_roots": ["../sibling"]}
        path = os.path.join(self.sibling, "types.ts")
        self.assertIsNone(self.run_gate("view_file", {"file_path": path}, options=opts))
        self.assertEqual(self.run_gate("write_to_file", {"TargetFile": path}, options=opts).decision,
                         GateDecision.DENY)

    def test_write_scope_limits_workspace_writes(self):
        opts = {"write_scope": ["packages/auth"]}
        inside = os.path.join(self.ws, "packages", "auth", "a.ts")
        outside = os.path.join(self.ws, "packages", "billing", "a.ts")
        state = os.path.join(self.ws, ".along", ".session", "s", "plan.md")
        self.assertIsNone(self.run_gate("write_to_file", {"TargetFile": inside}, options=opts))
        self.assertIsNone(self.run_gate("write_to_file", {"TargetFile": state}, options=opts))
        self.assertEqual(self.run_gate("write_to_file", {"TargetFile": outside}, options=opts).decision,
                         GateDecision.DENY)
        self.assertIsNone(self.run_gate("view_file", {"file_path": outside}, options=opts))

    def test_issue_frontmatter_scopes(self):
        _wc_issue(self.ws, "scoped", extra="allowed_roots: [../sibling]\nwrite_scope: [lib]\n")
        _wc_issue(self.ws, "idle", status="open", extra="allowed_roots: [/elsewhere]\n")
        roots, scope = containment.issue_scope(self.ws)
        # Entries resolve against the issue's own context [bug--subproject-model-overdetection].
        self.assertEqual((roots, scope), ([containment.canonical("../sibling", self.ws)],
                                          [containment.canonical("lib", self.ws)]))
        self.assertIsNone(self.run_gate("view_file", {"file_path": os.path.join(self.sibling, "x")}))
        res = self.run_gate("write_to_file", {"TargetFile": os.path.join(self.ws, "src", "x.py")})
        self.assertEqual(res.decision, GateDecision.DENY)

    def test_worktree_main_checkout_readable(self):
        main = os.path.join(self.base, "main")
        os.makedirs(os.path.join(main, ".git", "worktrees", "wt"))
        _wc_write(os.path.join(self.ws, ".git"), f"gitdir: {main}/.git/worktrees/wt\n")
        self.assertIsNone(self.run_gate("view_file", {"file_path": os.path.join(main, "pkg.json")}))


class TestCatalogueAndOverrides(_ContainmentFixture):
    def test_catalogue_entry(self):
        defn = {d.id: d for d in load_gate_definitions(DEFAULT_GATES_FILE)}["workspace_containment"]
        self.assertEqual(defn.rules[0].handler, check_workspace_containment)
        for tool in ("view_file", "write_to_file", "grep_search", "find_by_name", "run_command"):
            self.assertIn(tool, defn.tools)
        self.assertEqual(defn.options.get("on_violation"), "auto")

    def _gates(self):
        return {g.name: g for g in get_all_declarative_gates(self.ws)}

    def test_repo_override_merges_options_into_builtin(self):
        _wc_write(os.path.join(self.ws, ".along", "rules", "gates.yaml"),
                  "gates:\n  - id: workspace_containment\n    allowed_roots: [../sibling]\n")
        gate = self._gates()["workspace_containment"]
        self.assertTrue(gate.defn.rules, "rules must be inherited from the built-in gate")
        self.assertEqual(gate.defn.options["allowed_roots"], ["../sibling"])
        res = gate.evaluate(_wc_event("view_file", {"file_path": os.path.join(self.sibling, "a")}))
        self.assertEqual(res.decision, GateDecision.ALLOW)
        res = gate.evaluate(_wc_event("view_file", {"file_path": os.path.join(self.base, "other", "a")}))
        self.assertEqual(res.decision, GateDecision.ASK)
        self.assertEqual(res.gate_name, "workspace_containment")

    def test_repo_override_can_disable(self):
        _wc_write(os.path.join(self.ws, ".along", "rules", "gates.yaml"),
                  "gates:\n  - id: workspace_containment\n    enabled: false\n")
        self.assertNotIn("workspace_containment", self._gates())
        self.assertIn("typography", self._gates())


class TestStartScopeFlags(unittest.TestCase):
    def test_start_records_scope_in_issue(self):
        base = tempfile.mkdtemp(prefix="along_wc_start_")
        try:
            ws = os.path.join(base, "ws")
            os.makedirs(os.path.join(ws, ".along", "ISSUES"))
            _wc_issue(ws, "demo", status="open")
            subprocess.run(["git", "init", "-q", ws], check=True)
            cmd = [sys.executable, os.path.join(SCRIPTS_DIR, "along_exec.py"), "start", "demo",
                   "--allow-root", "../contracts", "--write-scope", "packages/auth"]
            res = subprocess.run(cmd, cwd=ws, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stderr + res.stdout)
            roots, scope = containment.issue_scope(ws)
            self.assertEqual(roots, [containment.canonical("../contracts", ws)])
            self.assertEqual(scope, [containment.canonical("packages/auth", ws)])
            bad = subprocess.run(cmd[:5] + ["--allow-root"], cwd=ws, capture_output=True, text=True)
            self.assertEqual(bad.returncode, 2)
        finally:
            shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
