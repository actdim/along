#!/usr/bin/env python3
"""
tests/test_rules.py - unit tests for alongkit.rules engine.

Hermetic tests for signature detection, rule pack attachment, case-insensitive
pruning on Windows, AGENTS.md injection, and library execution guard.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

from tests import hermetic
from alongkit import rules, textio

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestRulesEngine(unittest.TestCase):
    def test_detect_required_rules_python(self):
        with hermetic.repo_fixture() as repo:
            textio.write_text(os.path.join(repo, "pyproject.toml"), "[project]\nname = 'demo'\n")
            detected = rules.detect_required_rules(repo)
            self.assertIn("languages/python.md", detected)

    def test_detect_required_rules_typescript_and_web(self):
        with hermetic.repo_fixture() as repo:
            textio.write_text(os.path.join(repo, "tsconfig.json"), "{}\n")
            textio.write_text(
                os.path.join(repo, "package.json"),
                json.dumps({"dependencies": {"react-dom": "^18.0.0", "msw": "^2.0.0"}}) + "\n",
            )
            detected = rules.detect_required_rules(repo)
            self.assertIn("languages/typescript.md", detected)
            self.assertIn("platforms/web.md", detected)

    def test_detect_required_rules_ignores_ignored_dirs(self):
        with hermetic.repo_fixture() as repo:
            ignored = os.path.join(repo, "node_modules", "some-pkg")
            os.makedirs(ignored, exist_ok=True)
            textio.write_text(os.path.join(ignored, "tsconfig.json"), "{}\n")
            detected = rules.detect_required_rules(repo)
            self.assertNotIn("languages/typescript.md", detected)

    def test_attach_rules_copies_and_updates_agents(self):
        with hermetic.repo_fixture() as repo:
            # Create a mock global rules source
            with tempfile.TemporaryDirectory() as global_rules:
                py_rule = os.path.join(global_rules, "languages", "python.md")
                os.makedirs(os.path.dirname(py_rule), exist_ok=True)
                textio.write_text(py_rule, "# Python Standards\n")

                # Set repo to require python
                textio.write_text(os.path.join(repo, "pyproject.toml"), "[project]\n")

                orig_get_global = rules.get_global_rules_dir
                try:
                    rules.get_global_rules_dir = lambda: global_rules
                    rules.attach_rules(repo)
                finally:
                    rules.get_global_rules_dir = orig_get_global

                local_py = os.path.join(repo, ".along", "rules", "languages", "python.md")
                self.assertTrue(os.path.isfile(local_py))

                agents_md = textio.read_text(os.path.join(repo, "AGENTS.md"))
                self.assertIn("<!-- BEGIN ALONG-RULES -->", agents_md)
                self.assertIn("[languages/python.md](.along/rules/languages/python.md)", agents_md)
                self.assertIn("<!-- END ALONG-RULES -->", agents_md)

    def test_attach_rules_pruning_case_insensitive(self):
        with hermetic.repo_fixture() as repo:
            with tempfile.TemporaryDirectory() as global_rules:
                py_rule = os.path.join(global_rules, "languages", "python.md")
                os.makedirs(os.path.dirname(py_rule), exist_ok=True)
                textio.write_text(py_rule, "# Python Standards\n")
                mobile_tmpl = os.path.join(global_rules, "platforms", "mobile.md")
                os.makedirs(os.path.dirname(mobile_tmpl), exist_ok=True)
                textio.write_text(mobile_tmpl, "# Mobile Standards\n")

                # Pre-populate an obsolete legacy (headerless) rule matching its template: pruned
                obsolete_rule = os.path.join(repo, ".along", "rules", "platforms", "mobile.md")
                os.makedirs(os.path.dirname(obsolete_rule), exist_ok=True)
                textio.write_text(obsolete_rule, "# Mobile Standards\n")

                textio.write_text(os.path.join(repo, "pyproject.toml"), "[project]\n")

                orig_get_global = rules.get_global_rules_dir
                try:
                    rules.get_global_rules_dir = lambda: global_rules
                    rules.attach_rules(repo)
                finally:
                    rules.get_global_rules_dir = orig_get_global

                # Obsolete rule should be pruned
                self.assertFalse(os.path.exists(obsolete_rule))
                # Active rule should exist
                self.assertTrue(os.path.isfile(os.path.join(repo, ".along", "rules", "languages", "python.md")))

    def test_attach_rules_empty_does_not_pollute(self):
        with hermetic.repo_fixture() as repo:
            with tempfile.TemporaryDirectory() as global_rules:
                agents_before = textio.read_text(os.path.join(repo, "AGENTS.md"))

                orig_get_global = rules.get_global_rules_dir
                try:
                    rules.get_global_rules_dir = lambda: global_rules
                    rules.attach_rules(repo)
                finally:
                    rules.get_global_rules_dir = orig_get_global

                agents_after = textio.read_text(os.path.join(repo, "AGENTS.md"))
                self.assertNotIn("<!-- BEGIN ALONG-RULES -->", agents_after)
                self.assertEqual(agents_before.strip(), agents_after.strip())

    def test_rules_execution_guard(self):
        cmd = [sys.executable, os.path.join(REPO_ROOT, "scripts", "alongkit", "rules.py")]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("rules.py is a library module, not a command.", proc.stderr + proc.stdout)
    def test_alongkit_modules_execution_guards(self):
        alongkit_dir = os.path.join(REPO_ROOT, "scripts", "alongkit")
        for fname in sorted(os.listdir(alongkit_dir)):
            if not fname.endswith(".py") or fname.startswith("__") or fname == "cli.py":
                continue
            cmd = [sys.executable, os.path.join(alongkit_dir, fname)]
            res = subprocess.run(cmd, capture_output=True, text=True)
            output = (res.stderr or "") + (res.stdout or "")
            self.assertNotEqual(res.returncode, 0, f"{fname} exited 0 when executed directly")
            self.assertIn(f"{fname} is a library module, not a command.", output,
                          f"{fname} output did not name itself: {output}")
            self.assertNotIn("__main__", output,
                             f"{fname} output contained corrupted '__main__' prefix: {output}")
            self.assertEqual(output.count("is a library module"), 1,
                             f"{fname} emitted duplicated guard messages: {output}")

    def test_alongkit_cli_entry_point(self):
        cmd = [sys.executable, os.path.join(REPO_ROOT, "scripts", "alongkit", "cli.py"), "--version"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("along ", res.stdout)

    def test_rule_header_and_hashing(self):
        content = "# My Standards\nSome guidelines here.\n"
        h = rules.compute_rule_hash(content)
        self.assertEqual(len(h), 64)
        
        header = rules.format_rule_header("languages/python.md", h)
        full = header + content
        
        tmpl, parsed_h, body = rules.parse_rule_header(full)
        self.assertEqual(tmpl, "languages/python.md")
        self.assertEqual(parsed_h, h)
        self.assertEqual(rules.compute_rule_hash(body), h)

    def test_attach_rules_preserves_modified_rule(self):
        with hermetic.repo_fixture() as repo:
            with tempfile.TemporaryDirectory() as global_rules:
                py_rule = os.path.join(global_rules, "languages", "python.md")
                os.makedirs(os.path.dirname(py_rule), exist_ok=True)
                textio.write_text(py_rule, "# Python Standards\n")

                textio.write_text(os.path.join(repo, "pyproject.toml"), "[project]\n")

                # First attach: writes pristine template with header
                orig_get_global = rules.get_global_rules_dir
                try:
                    rules.get_global_rules_dir = lambda: global_rules
                    rules.attach_rules(repo)
                finally:
                    rules.get_global_rules_dir = orig_get_global

                local_py = os.path.join(repo, ".along", "rules", "languages", "python.md")
                self.assertTrue(os.path.isfile(local_py))
                
                # Now user/agent modifies the local rule file
                modified_text = "# Python Standards with Custom Local Changes\n"
                textio.write_text(local_py, rules.format_rule_header("languages/python.md", "oldhash") + modified_text)

                # Re-run attach: must NOT overwrite modified file!
                try:
                    rules.get_global_rules_dir = lambda: global_rules
                    rules.attach_rules(repo)
                finally:
                    rules.get_global_rules_dir = orig_get_global

                after_text = textio.read_text(local_py)
                self.assertIn("Custom Local Changes", after_text)

    def test_attach_rules_preserves_gates_yaml_during_prune(self):
        with hermetic.repo_fixture() as repo:
            with tempfile.TemporaryDirectory() as global_rules:
                py_rule = os.path.join(global_rules, "languages", "python.md")
                os.makedirs(os.path.dirname(py_rule), exist_ok=True)
                textio.write_text(py_rule, "# Python Standards\n")

                textio.write_text(os.path.join(repo, "pyproject.toml"), "[project]\n")

                # Put a repository gates.yaml in .along/rules/
                gates_path = os.path.join(repo, ".along", "rules", "gates.yaml")
                os.makedirs(os.path.dirname(gates_path), exist_ok=True)
                textio.write_text(gates_path, "gates: []\n")

                orig_get_global = rules.get_global_rules_dir
                try:
                    rules.get_global_rules_dir = lambda: global_rules
                    rules.attach_rules(repo)
                finally:
                    rules.get_global_rules_dir = orig_get_global

                # gates.yaml must survive pruning
                self.assertTrue(os.path.isfile(gates_path))

    def test_rules_audit_status_diff_restore(self):
        with hermetic.repo_fixture() as repo:
            with tempfile.TemporaryDirectory() as global_rules:
                py_rule = os.path.join(global_rules, "languages", "python.md")
                os.makedirs(os.path.dirname(py_rule), exist_ok=True)
                textio.write_text(py_rule, "# Python Standards\nLine 2\n")

                textio.write_text(os.path.join(repo, "pyproject.toml"), "[project]\n")

                orig_get_global = rules.get_global_rules_dir
                try:
                    rules.get_global_rules_dir = lambda: global_rules
                    
                    # 1. Audit before attach: reports missing
                    audits = rules.audit_rules(repo)
                    self.assertEqual(len(audits), 1)
                    self.assertEqual(audits[0]["status"], "missing")

                    # 2. Attach
                    rules.attach_rules(repo)
                    audits = rules.audit_rules(repo)
                    self.assertEqual(audits[0]["status"], "pristine")

                    # 3. Modify local file
                    local_py = os.path.join(repo, ".along", "rules", "languages", "python.md")
                    textio.write_text(local_py, "# Custom Python\nLine 2\n")
                    
                    audits = rules.audit_rules(repo)
                    self.assertEqual(audits[0]["status"], "modified")

                    # 4. Diff
                    diff = rules.diff_rule(repo, "languages/python.md")
                    self.assertIn("Custom Python", diff)

                    # 5. Restore
                    restored = rules.restore_rule(repo, "languages/python.md")
                    self.assertEqual(restored, ["languages/python.md"])
                    
                    audits_after = rules.audit_rules(repo)
                    self.assertEqual(audits_after[0]["status"], "pristine")
                    
                    # Verify backup exists
                    backup_dir = os.path.join(repo, ".along", ".migration-backup")
                    self.assertTrue(os.path.isdir(backup_dir))
                finally:
                    rules.get_global_rules_dir = orig_get_global

    def test_cli_rules_subcommands(self):
        exec_script = os.path.join(REPO_ROOT, "scripts", "along_exec.py")
        with hermetic.repo_fixture() as repo:
            textio.write_text(os.path.join(repo, "requirements.txt"), "pytest\n")
            
            # Status CLI
            cmd = [sys.executable, exec_script, "rules", "status", "--json"]
            res = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stderr + res.stdout)
            data = json.loads(res.stdout[res.stdout.find("["):])
            self.assertTrue(any(d["rule"] == "languages/python.md" for d in data))

    def test_attach_rules_conflict_strategies(self):
        with hermetic.repo_fixture() as repo:
            with tempfile.TemporaryDirectory() as global_rules:
                py_rule = os.path.join(global_rules, "languages", "python.md")
                os.makedirs(os.path.dirname(py_rule), exist_ok=True)
                textio.write_text(py_rule, "# Python Standards\nCanonical\n")

                textio.write_text(os.path.join(repo, "requirements.txt"), "pytest\n")

                orig_get_global = rules.get_global_rules_dir
                try:
                    rules.get_global_rules_dir = lambda: global_rules

                    # Attach first time
                    rules.attach_rules(repo)
                    local_py = os.path.join(repo, ".along", "rules", "languages", "python.md")
                    
                    # Modify locally
                    textio.write_text(local_py, "# Python Standards\nLocal Mod\n")

                    # Strategy 1: preserve (default)
                    rules.attach_rules(repo, on_conflict="preserve")
                    self.assertIn("Local Mod", textio.read_text(local_py))

                    # Strategy 2: diff
                    rules.attach_rules(repo, on_conflict="diff")
                    self.assertIn("Local Mod", textio.read_text(local_py))

                    # Strategy 3: overwrite
                    rules.attach_rules(repo, on_conflict="overwrite")
                    after_text = textio.read_text(local_py)
                    self.assertIn("Canonical", after_text)
                    self.assertNotIn("Local Mod", after_text)
                    
                    # Verify backup created
                    backup_dir = os.path.join(repo, ".along", ".migration-backup")
                    self.assertTrue(os.path.isdir(backup_dir))
                finally:
                    rules.get_global_rules_dir = orig_get_global

    def test_attach_rules_retains_modified_headerless_obsolete_rule(self):
        """A legacy (headerless) obsolete rule with local edits survives pruning
        [feat--rule-pack-protection-gate]."""
        with hermetic.repo_fixture() as repo:
            with tempfile.TemporaryDirectory() as global_rules:
                for rel, text in (("languages/python.md", "# Python Standards\n"),
                                  ("platforms/mobile.md", "# Mobile Standards\n")):
                    path = os.path.join(global_rules, *rel.split("/"))
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    textio.write_text(path, text)
                textio.write_text(os.path.join(repo, "pyproject.toml"), "[project]\n")

                rules_dir = os.path.join(repo, ".along", "rules")
                edited = os.path.join(rules_dir, "platforms", "mobile.md")
                custom = os.path.join(rules_dir, "custom", "house-style.md")
                for path, text in ((edited, "# Mobile Standards\nLocal edit\n"), (custom, "# House\n")):
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    textio.write_text(path, text)

                orig_get_global = rules.get_global_rules_dir
                try:
                    rules.get_global_rules_dir = lambda: global_rules
                    statuses = {a["rule"]: a["status"] for a in rules.audit_rules(repo)}
                    rules.attach_rules(repo)
                finally:
                    rules.get_global_rules_dir = orig_get_global

                self.assertEqual(statuses["platforms/mobile.md"], "modified_obsolete")
                self.assertEqual(statuses["custom/house-style.md"], "modified_obsolete")
                self.assertIn("Local edit", textio.read_text(edited))
                self.assertTrue(os.path.isfile(custom))


if __name__ == "__main__":
    unittest.main()

