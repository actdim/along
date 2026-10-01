#!/usr/bin/env python3
"""
tests/test_repo_state_gates.py - protocol rules moved from prose into deterministic checks.

Covers [debt--prose-rules-to-deterministic-checks]: every `alongkit.repochecks` check
(Windows-safe filenames, untracked exports, code fence languages, portable links, stable
entry point, issue lifecycle placement, tracked secrets), the `along: allow-<gate>`
pragma, the git/ci-only catalogue entries staying out of the runtime pipeline, and the
`alongkit.gitgates` wiring (pre-commit reads staged blobs, CI reads the tree) in
throwaway git repositories. Nothing touches the live repository.

Secret-shaped fixtures are assembled at runtime so this file never trips the gate itself.
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

from alongkit import gitgates, repochecks
from alongkit.hooks.declarative import DEFAULT_GATES_FILE, get_all_declarative_gates, load_gate_definitions

FENCE = "`" * 3
REPO_GATES = ("windows_safe_filenames", "untracked_exports", "code_fence_language",
              "portable_links", "stable_entry_point", "issue_lifecycle", "no_tracked_secrets")


def _rs_reader(files):
    return lambda path: files.get(path)


def _rs_run(check, files, options=None):
    return check(list(files), _rs_reader(files), options or {})


def _rs_issue(status):
    return f"---\nslug: x\ntype: feat\nstatus: {status}\n---\n\n# X\n"


def _rs_git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", check=True)


def _rs_write(root, rel, text):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


class TestRepoChecks(unittest.TestCase):

    def test_windows_safe_filenames(self):
        bad = ["docs/a:b.md", "notes/trailing.", "src/CON.txt", "x/nul", "a/b?.md"]
        good = ["docs/2026-09-30--x.md", "src/console.py", "README.md"]
        found = [loc for loc, _ in _rs_run(repochecks.check_windows_safe_filenames,
                                            {p: "" for p in bad + good})]
        self.assertEqual(sorted(found), sorted(bad))

    def test_untracked_exports(self):
        files = {".along/dashboard.html": "", "sub/.along/DASHBOARD.md": "",
                 "docs/DASHBOARD.md": "", ".along/ISSUES.md": ""}
        found = [loc for loc, _ in _rs_run(repochecks.check_untracked_exports, files)]
        self.assertEqual(sorted(found), [".along/dashboard.html", "sub/.along/DASHBOARD.md"])

    def test_code_fence_language(self):
        text = "\n".join([
            f"{FENCE}python", "x = 1", FENCE,              # ok
            FENCE, "plain", FENCE,                          # line 4: missing language
            f"{FENCE}`markdown", FENCE, "inner", FENCE, FENCE + "`",  # nested, closed by 4 ticks
            "~~~", "tilde", "~~~",                          # line 12: missing language
            f"{FENCE}  along: allow-code-fence-language", "x", FENCE,
        ])
        found = _rs_run(repochecks.check_code_fence_language, {"docs/a.md": text, "a.py": FENCE})
        self.assertEqual([loc for loc, _ in found], ["docs/a.md:4", "docs/a.md:12"])

    def test_portable_links(self):
        text = "\n".join([
            "[ok](./topic--x.md) [web](https://example.com)",
            "[bad](file:///C:/repo/x.md)",
            "[bad](..\\docs\\x.md)",
            "`[code](file:///x)` is inline code",
            FENCE + "text", "[fenced](file:///x)", FENCE,
            "[pragma](file:///x) along: allow-portable-links",
        ])
        found = _rs_run(repochecks.check_portable_links, {"README.md": text})
        self.assertEqual([loc for loc, _ in found], ["README.md:2", "README.md:3"])

    def test_stable_entry_point(self):
        files = {
            "README.md": "[a](.along/ISSUES.md)\n[b](docs/INDEX.md)\n[c](https://x/.along/y)\n",
            "docs/topic--x.md": "[a](../.along/DECISIONS.md#top)\n[b](./INDEX.md)\n",
            "docs/sub/y.md": "[a](../../.along/HISTORY.md)\n",
            ".along/ISSUES/feat--x.md": "[fine](../HISTORY.md)\n",
            "skills/x/SKILL.md": "[out of scope](../../.along/ISSUES.md)\n",
        }
        found = [loc for loc, _ in _rs_run(repochecks.check_stable_entry_point, files)]
        self.assertEqual(sorted(found), ["README.md:1", "docs/sub/y.md:1", "docs/topic--x.md:1"])
        scoped = _rs_run(repochecks.check_stable_entry_point, files, {"scope": ["skills/*"]})
        self.assertEqual([loc for loc, _ in scoped], ["skills/x/SKILL.md:1"])

    def test_issue_lifecycle(self):
        files = {
            ".along/ISSUES/feat--open.md": _rs_issue("open"),
            ".along/ISSUES/feat--closed.md": _rs_issue("done"),
            ".along/ISSUES/done/feat--old.md": _rs_issue("done"),
            ".along/ISSUES/done/feat--reopened.md": _rs_issue("in-progress"),
            "sub/.along/ISSUES/bug--gone.md": _rs_issue("cancelled"),
            ".along/ISSUES.md": "# board\nstatus: done\n",
        }
        found = [loc for loc, _ in _rs_run(repochecks.check_issue_lifecycle, files)]
        self.assertEqual(sorted(found), [".along/ISSUES/done/feat--reopened.md",
                                         ".along/ISSUES/feat--closed.md",
                                         "sub/.along/ISSUES/bug--gone.md"])

    def test_no_tracked_secrets(self):
        aws = "AKIA" + "Q" * 16
        key_header = "-----BEGIN " + "RSA PRIVATE KEY-----"
        gh = "ghp_" + "a1" * 18
        files = {
            "config.py": f"KEY = '{aws}'\n",
            "id_rsa.txt": key_header + "\n",
            "notes.md": f"token {gh}\n",
            "fixture.py": f"KEY = '{aws}'  # along: allow-no-tracked-secrets\n",
            "logo.png": aws,
            "clean.py": "API_KEY = os.environ['API_KEY']\n",
        }
        found = [loc for loc, _ in _rs_run(repochecks.check_no_tracked_secrets, files)]
        self.assertEqual(sorted(found), ["config.py:1", "id_rsa.txt:1", "notes.md:1"])
        excluded = _rs_run(repochecks.check_no_tracked_secrets, files, {"exclude_paths": ["*.py"]})
        self.assertEqual(sorted(loc for loc, _ in excluded), ["id_rsa.txt:1", "notes.md:1"])


class TestRepoGateCatalogue(unittest.TestCase):

    def test_catalogue_declares_git_and_ci_only(self):
        defs = {d.id: d for d in load_gate_definitions(DEFAULT_GATES_FILE)}
        for gate_id in REPO_GATES:
            with self.subTest(gate=gate_id):
                self.assertIn(gate_id, defs)
                self.assertEqual(sorted(defs[gate_id].enforcement), ["ci", "git"])
                handler = defs[gate_id].rules[0].handler_name
                self.assertTrue(handler.startswith(gitgates.REPO_CHECK_PREFIX))
                self.assertTrue(callable(getattr(repochecks, handler.rsplit(".", 1)[1])))

    def test_runtime_pipeline_skips_repo_gates(self):
        names = {gate.name for gate in get_all_declarative_gates(None)}
        self.assertTrue(names.isdisjoint(REPO_GATES))
        self.assertIn("typography", names)


class TestRepoGatesThroughGit(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along_repo_gates_")
        _rs_git(self.root, "init", "-q")
        _rs_git(self.root, "config", "user.email", "t@example.com")
        _rs_git(self.root, "config", "user.name", "t")
        _rs_git(self.root, "config", "core.autocrlf", "false")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _gates(self, violations):
        return sorted({v.gate for v in violations})

    def test_pre_commit_reads_staged_blob_not_worktree(self):
        _rs_write(self.root, "docs/a.md", f"{FENCE}\nplain\n{FENCE}\n")
        _rs_write(self.root, ".along/dashboard.html", "<html></html>\n")
        _rs_git(self.root, "add", "-A")
        violations = gitgates.check_repo_state(
            self.root, ["docs/a.md", ".along/dashboard.html"], "git", gitgates._index_reader(self.root))
        self.assertEqual(self._gates(violations), ["code_fence_language", "untracked_exports"])

        # Fixing only the working tree does not help: the staged blob is what gets committed.
        _rs_write(self.root, "docs/a.md", f"{FENCE}text\nplain\n{FENCE}\n")
        staged = gitgates.check_repo_state(self.root, ["docs/a.md"], "git",
                                           gitgates._index_reader(self.root))
        self.assertEqual(self._gates(staged), ["code_fence_language"])
        tree = gitgates.check_repo_state(self.root, ["docs/a.md"], "ci",
                                         gitgates._tree_reader(self.root))
        self.assertEqual(tree, [])

    def test_ci_checks_every_tracked_file(self):
        _rs_write(self.root, "README.md", "[kb](.along/ISSUES.md)\n")
        _rs_write(self.root, ".along/ISSUES/feat--x.md", _rs_issue("done"))
        _rs_git(self.root, "add", "-A")
        _rs_git(self.root, "commit", "-q", "--no-verify", "-m", "init")
        violations = gitgates.check_ci(self.root, commit_range=None, links=False)
        gates = self._gates(violations)
        self.assertIn("stable_entry_point", gates)
        self.assertIn("issue_lifecycle", gates)
        rendered = [v.render() for v in violations if v.gate == "issue_lifecycle"]
        self.assertTrue(rendered[0].startswith("[gate: issue-lifecycle] .along/ISSUES/feat--x.md"))


if __name__ == "__main__":
    unittest.main()
