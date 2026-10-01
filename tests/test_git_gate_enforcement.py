#!/usr/bin/env python3
"""
tests/test_git_gate_enforcement.py - runtime-agnostic gates via git hooks and CI.

Covers [feat--git-level-gate-enforcement]: the `enforcement` catalogue field, the
commit-time checks in `alongkit.gitgates` (added-line typography / conflict markers /
anti-stub, issue binding, AI co-author trailers, projection freshness), the opt-in hook
installer (chaining, core.hooksPath, uninstall), and real `git commit` runs through the
installed hooks in throwaway repositories. Nothing touches the live repository.
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

from alongkit import gitgates
from alongkit.hooks.declarative import DEFAULT_GATES_FILE, load_gate_definitions, parse_gate_dict
from alongkit.hooks.traceability import audit_traceability, format_traceability_report

EM_DASH = chr(0x2014)
AI_TRAILER = "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"


def _gg_diff(path, *added, start=1):
    body = [f"diff --git a/{path} b/{path}", f"--- a/{path}", f"+++ b/{path}",
            f"@@ -0,0 +{start},{len(added)} @@"]
    body += [f"+{line}" for line in added]
    return "\n".join(body) + "\n"


def _gg_issue(slug, status="open"):
    return (
        "---\nprotocol: along\n"
        f"slug: {slug}\ntype: feat\nstatus: {status}\npriority: medium\n"
        "created: 2026-09-20\nupdated: 2026-09-20\ntags: [git]\n---\n\n"
        f"# {slug}\n\nBody.\n"
    )


def _gg_git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", check=check)


def _gg_write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


class TestEnforcementCatalogue(unittest.TestCase):
    def test_default_is_runtime_and_unknown_layer_rejected(self):
        self.assertEqual(parse_gate_dict({"id": "x"}).enforcement, ["runtime"])
        self.assertEqual(parse_gate_dict({"id": "x", "enforcement": "ci"}).enforcement, ["ci"])
        with self.assertRaises(ValueError):
            parse_gate_dict({"id": "x", "enforcement": ["runtime", "cron"]})

    def test_commit_time_subset_declares_git_and_ci(self):
        by_id = {d.id: d.enforcement for d in load_gate_definitions(DEFAULT_GATES_FILE)}
        for gid in ("commit_issue_binding", "commit_no_conflict_markers", "commit_no_ai_coauthor",
                    "anti_stub_injection", "projection_protection", "typography"):
            self.assertEqual(by_id[gid], ["runtime", "git", "ci"], gid)
        self.assertEqual(by_id["cli_safety"], ["runtime"])

    def test_traceability_report_prints_matrix(self):
        report = audit_traceability(REPO_ROOT)
        self.assertIn("git", report.enforcement["typography"])
        text = format_traceability_report(report)
        self.assertIn("[Enforcement Matrix]", text)
        self.assertTrue(all(line == line.rstrip() for line in text.splitlines()))


class TestDiffChecks(unittest.TestCase):
    def test_added_lines_tracks_new_line_numbers(self):
        diff = _gg_diff("a.md", "one", "two", start=7)
        self.assertEqual(gitgates.added_lines(diff), {"a.md": [(7, "one"), (8, "two")]})

    def test_typography_only_in_governed_suffixes(self):
        violations = gitgates.check_diff(_gg_diff("docs/a.md", f"x {EM_DASH} y"), "")
        self.assertEqual([(v.gate, v.location) for v in violations], [("typography", "docs/a.md:1")])
        self.assertEqual(gitgates.check_diff(_gg_diff("data.json", f"x {EM_DASH} y"), ""), [])
        self.assertEqual(gitgates.check_diff(_gg_diff("locales/ru.md", f"x {EM_DASH} y"), ""), [])

    def test_conflict_markers_and_stub(self):
        # Built at runtime so this file never trips the same gates when committed.
        diff = _gg_diff("a.py", "<" * 7 + " HEAD", "# " + "..." + " rest of code", "ok = 1")
        gates = sorted(v.gate for v in gitgates.check_diff(diff, ""))
        self.assertEqual(gates, ["anti_stub_injection", "commit_no_conflict_markers"])

    def test_context_lines_are_ignored(self):
        diff = ("diff --git a/a.md b/a.md\n--- a/a.md\n+++ b/a.md\n@@ -1,2 +1,3 @@\n"
                f" old {EM_DASH} debt\n+clean line\n")
        self.assertEqual(gitgates.check_diff(diff, ""), [])


class TestMessageChecks(unittest.TestCase):
    def _gates(self, text):
        return [v.gate for v in gitgates.check_message(text, None)]

    def test_binding_forms(self):
        self.assertEqual(self._gates("feat: x (refs #my-slug)"), [])
        self.assertEqual(self._gates("feat: x [feat--my-slug]"), [])
        self.assertEqual(self._gates("feat: x"), ["commit_issue_binding"])

    def test_exempt_subjects_and_comments(self):
        self.assertEqual(self._gates("release: v1.2.3 - bump"), [])
        self.assertEqual(self._gates("Merge branch 'x'"), [])
        self.assertEqual(self._gates("# Please enter the commit message\n"), [])

    def test_ai_coauthor(self):
        self.assertEqual(self._gates(f"feat: x (refs #s)\n\n{AI_TRAILER}\n"), ["commit_no_ai_coauthor"])
        self.assertEqual(self._gates("feat: x (refs #s)\n\nCo-Authored-By: Jane <j@example.com>\n"), [])


@unittest.skipUnless(shutil.which("git"), "git not available")
class TestGitHooksEndToEnd(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="along-gitgates-")
        _gg_git(self.repo, "init", "-q", "-b", "main")
        for key, value in (("user.name", "Along Test"), ("user.email", "test@example.invalid"),
                           ("commit.gpgsign", "false"), ("core.autocrlf", "false")):
            _gg_git(self.repo, "config", key, value)
        _gg_write(os.path.join(self.repo, ".along", "ISSUES", "feat--a.md"), _gg_issue("feat--a"))
        _gg_write(os.path.join(self.repo, ".along", "ISSUES", "done", ".keep"), "keep\n")
        from alongkit import entities
        entities.sync_issues_board(self.repo)
        _gg_write(os.path.join(self.repo, "README.md"), "# Repo\n")
        _gg_git(self.repo, "add", "-A")
        _gg_git(self.repo, "commit", "-q", "-m", "base (refs #a)")
        self.hooks = gitgates.hooks_dir(self.repo)[0]

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def _commit(self, message):
        return _gg_git(self.repo, "commit", "-q", "-m", message, check=False)

    def test_install_is_idempotent_and_uninstall_clean(self):
        self.assertEqual(set(gitgates.install_hooks(self.repo).values()), {"installed"})
        self.assertEqual(set(gitgates.install_hooks(self.repo).values()), {"present"})
        self.assertTrue(all(gitgates.hooks_status(self.repo).values()))
        self.assertEqual(set(gitgates.install_hooks(self.repo, uninstall=True).values()), {"removed"})
        self.assertFalse(any(gitgates.hooks_status(self.repo).values()))

    def test_dry_run_writes_nothing(self):
        gitgates.install_hooks(self.repo, dry_run=True)
        self.assertFalse(any(gitgates.hooks_status(self.repo).values()))

    def test_foreign_hook_is_chained_and_restored(self):
        foreign = os.path.join(self.hooks, "pre-commit")
        _gg_write(foreign, "#!/bin/sh\nexit 0\n")
        os.chmod(foreign, 0o755)
        report = gitgates.install_hooks(self.repo)
        self.assertEqual(report["pre-commit"], "installed-chained-previous")
        self.assertTrue(os.path.isfile(foreign + gitgates.CHAINED_SUFFIX))
        report = gitgates.install_hooks(self.repo, uninstall=True)
        self.assertEqual(report["pre-commit"], "removed-restored-previous")
        with open(foreign, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "#!/bin/sh\nexit 0\n")

    def test_core_hooks_path_is_left_alone(self):
        _gg_git(self.repo, "config", "core.hooksPath", ".husky")
        self.assertEqual(set(gitgates.install_hooks(self.repo).values()), {"skipped-core-hooksPath"})
        self.assertFalse(os.path.isdir(os.path.join(self.repo, ".husky")))

    def test_hooks_block_violations_regardless_of_committer(self):
        gitgates.install_hooks(self.repo)

        _gg_write(os.path.join(self.repo, "README.md"), f"# Repo\n\nA {EM_DASH} B\n")
        _gg_git(self.repo, "add", "README.md")
        res = self._commit("docs: dash (refs #a)")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("typography", res.stderr + res.stdout)

        _gg_write(os.path.join(self.repo, "README.md"), "# Repo\n\nA - B\n")
        _gg_git(self.repo, "add", "README.md")
        res = self._commit("docs: no binding")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("commit-issue-binding", res.stderr + res.stdout)

        res = self._commit("docs: clean dash (refs #a)")
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_stale_projection_blocks_commit(self):
        gitgates.install_hooks(self.repo)
        _gg_write(os.path.join(self.repo, ".along", "ISSUES", "feat--b.md"), _gg_issue("feat--b"))
        _gg_git(self.repo, "add", "-A")
        res = self._commit("feat: add b (refs #b)")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn(".along/ISSUES.md", res.stderr + res.stdout)

        from alongkit import entities
        entities.sync_issues_board(self.repo)
        _gg_git(self.repo, "add", "-A")
        res = self._commit("feat: add b (refs #b)")
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_checks_never_mutate_the_working_tree(self):
        _gg_write(os.path.join(self.repo, ".along", "ISSUES", "feat--b.md"), _gg_issue("feat--b"))
        _gg_git(self.repo, "add", "-A")
        before = _gg_git(self.repo, "status", "--porcelain", "-u").stdout
        self.assertTrue(gitgates.check_pre_commit(self.repo))
        self.assertEqual(_gg_git(self.repo, "status", "--porcelain", "-u").stdout, before)

    def test_ci_range_reports_same_violations(self):
        _gg_write(os.path.join(self.repo, "README.md"), f"# Repo\n\nA {EM_DASH} B\n")
        _gg_git(self.repo, "add", "-A")
        _gg_git(self.repo, "commit", "-q", "--no-verify", "-m", "docs: unbound")
        gates = sorted({v.gate for v in gitgates.check_ci(self.repo, "HEAD^..HEAD", links=False)})
        self.assertEqual(gates, ["commit_issue_binding", "typography"])


if __name__ == "__main__":
    unittest.main()
