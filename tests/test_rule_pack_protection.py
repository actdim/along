#!/usr/bin/env python3
"""
tests/test_rule_pack_protection.py - [gate: rule-pack-protection] and lifecycle-hook edits.

Covers [feat--rule-pack-protection-gate]: the runtime predicate denies file-tool and shell
writes to managed rule packs (`.along/rules/**/*.md`) while `gates.yaml`, reads and
`along rules ...` pass; the git/ci check flags a rule pack whose body no longer matches its
managed header hash; and edits under `.along/scripts/` count as source edits for
test_before_stop. Every fixture is a throwaway directory or git repository.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import gitgates, repochecks, rules
from alongkit.hooks import GateDecision, HookEvent, HookEventType
from alongkit.hooks.declarative import DEFAULT_GATES_FILE, DeclarativeGate, load_gate_definitions
from alongkit.hooks import predicates

GATE_ID = "rule_pack_protection"


def _rp_pack(body: str, rule: str = "platforms/web.md") -> str:
    return rules.format_rule_header(rule, rules.compute_rule_hash(body)) + body


def _rp_write(root: str, rel: str, text: str) -> str:
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


def _rp_git(cwd: str, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


class TestRulePackRuntimeGate(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="along-rule-pack-")
        defn = next(d for d in load_gate_definitions(DEFAULT_GATES_FILE) if d.id == GATE_ID)
        self.assertEqual(sorted(defn.enforcement), ["ci", "git", "runtime"])
        self.gate = DeclarativeGate(defn, repo_root=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _file_event(self, target: str, tool: str = "replace_file_content") -> HookEvent:
        return HookEvent(event_type=HookEventType.PRE_TOOL_USE, tool_name=tool,
                         tool_args={"TargetFile": target, "ReplacementContent": "x"},
                         workspace_root=self.tmp)

    def _shell_event(self, command: str) -> HookEvent:
        return HookEvent(event_type=HookEventType.PRE_TOOL_USE, tool_name="run_command",
                         tool_args={"CommandLine": command}, workspace_root=self.tmp)

    def test_file_tools_denied_on_rule_packs(self):
        for target in (".along/rules/platforms/web.md",
                       os.path.join(self.tmp, ".along", "rules", "languages", "python.md"),
                       "packages/ui/.along/rules/platforms/web.md",
                       ".along/rules/custom/deep/house.MD"):
            for tool in ("write_to_file", "replace_file_content"):
                res = self.gate.evaluate(self._file_event(target, tool))
                self.assertEqual(res.decision, GateDecision.DENY, (target, tool))
                self.assertIn("[gate: rule-pack-protection]", res.reason)
                self.assertIn("along rules restore", res.reason)

    def test_file_tools_allowed_elsewhere(self):
        for target in (".along/rules/gates.yaml", ".along/rules/gates.yml", "rules/platforms/web.md",
                       "docs/topic--frontend-architecture.md", "AGENTS.md",
                       ".along/scripts/test.py", ".along/ISSUES/feat--x.md"):
            res = self.gate.evaluate(self._file_event(target))
            self.assertEqual(res.decision, GateDecision.ALLOW, target)

    def test_shell_writes_denied(self):
        for command in ("cp web.md .along/rules/platforms/web.md",
                        "Copy-Item notes.md .along\\rules\\platforms\\web.md",
                        "git status && mv x.md .along/rules/languages/python.md",
                        "cat extra.md >> .along/rules/platforms/web.md"):
            res = self.gate.evaluate(self._shell_event(command))
            self.assertEqual(res.decision, GateDecision.DENY, command)
            self.assertIn("[gate: rule-pack-protection]", res.reason)

    def test_shell_reads_and_along_rules_allowed(self):
        for command in ("cat .along/rules/platforms/web.md",
                        "git diff -- .along/rules/platforms/web.md",
                        "along rules restore platforms/web.md",
                        "python scripts/along_exec.py rules restore .along/rules/platforms/web.md",
                        "cp a.yaml .along/rules/gates.yaml",
                        "ls rules/platforms"):
            res = self.gate.evaluate(self._shell_event(command))
            self.assertEqual(res.decision, GateDecision.ALLOW, command)


class TestRulePackRepoCheck(unittest.TestCase):

    def test_integrity_findings(self):
        body = "# Web\n\nRule.\n"
        files = {
            ".along/rules/platforms/web.md": _rp_pack(body),
            ".along/rules/languages/python.md": _rp_pack("# Py\n", "languages/python.md") + "Extra project rule.\n",
            "sub/.along/rules/platforms/mobile.md": "# Mobile, no header\n",
            ".along/rules/gates.yaml": "gates: []\n",
            "rules/platforms/web.md": "# Template source, not a managed copy\n",
        }
        found = dict(repochecks.check_rule_pack_integrity(list(files), files.get, {}))
        self.assertEqual(sorted(found), [".along/rules/languages/python.md",
                                         "sub/.along/rules/platforms/mobile.md"])
        self.assertIn("along rules restore", found[".along/rules/languages/python.md"])
        self.assertIn("no managed header", found["sub/.along/rules/platforms/mobile.md"])

    def test_crlf_checkout_stays_pristine(self):
        text = _rp_pack("# Web\n\nRule.\n").replace("\n", "\r\n")
        files = {".along/rules/platforms/web.md": text}
        self.assertEqual(repochecks.check_rule_pack_integrity(list(files), files.get, {}), [])


class TestRulePackGitGate(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along-rule-pack-git-")
        _rp_git(self.root, "init", "-q")
        _rp_git(self.root, "config", "user.email", "t@example.invalid")
        _rp_git(self.root, "config", "user.name", "t")
        _rp_git(self.root, "config", "core.autocrlf", "false")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _rule_pack_violations(self):
        return [v for v in gitgates.check_pre_commit(self.root) if v.gate == GATE_ID]

    def test_pre_commit_flags_edited_rule_pack(self):
        path = _rp_write(self.root, ".along/rules/platforms/web.md", _rp_pack("# Web\n"))
        _rp_git(self.root, "add", "-A")
        self.assertEqual(self._rule_pack_violations(), [])

        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write("Use our in-house state library.\n")
        _rp_git(self.root, "add", "-A")
        violations = self._rule_pack_violations()
        self.assertEqual([v.location for v in violations], [".along/rules/platforms/web.md"])
        self.assertIn("[gate: rule-pack-protection]", violations[0].render())


class TestLifecycleHookEditsAreSource(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="along-rule-pack-trace-")
        os.makedirs(os.path.join(self.tmp, ".along", "scripts"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _edit(self, target: str) -> None:
        predicates.record_tool_activity(HookEvent(
            event_type=HookEventType.POST_TOOL_USE, tool_name="write_to_file",
            tool_args={"TargetFile": target, "CodeContent": "x = 1\n"}, workspace_root=self.tmp),
            repo_root=self.tmp)

    def _stop(self):
        return predicates.check_test_before_stop(
            HookEvent(event_type=HookEventType.STOP, workspace_root=self.tmp), repo_root=self.tmp,
            options={"enforce_unbound": True})

    def test_is_source_edit(self):
        self.assertTrue(predicates.is_source_edit("src/app.py"))
        self.assertTrue(predicates.is_source_edit(".along/scripts/test.py"))
        self.assertTrue(predicates.is_source_edit("pkg/.along/scripts/bump_version.py"))
        self.assertFalse(predicates.is_source_edit(".along/ISSUES/feat--x.md"))
        self.assertFalse(predicates.is_source_edit("pkg/.along/SESSIONS/2026/x.md"))
        self.assertFalse(predicates.is_source_edit(".along/scripts"))

    def test_agent_state_edit_needs_no_test_run(self):
        self._edit(".along/ISSUES/feat--x.md")
        self.assertIsNone(self._stop())

    def test_lifecycle_hook_edit_needs_test_run(self):
        self._edit(".along/scripts/test.py")
        self.assertIn("[gate: test-before-stop]", self._stop() or "")


if __name__ == "__main__":
    unittest.main()
