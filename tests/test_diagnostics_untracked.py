#!/usr/bin/env python3
"""
tests/test_diagnostics_untracked.py - per-machine `.along/diagnostics/` stays out of git.

Covers [bug--diagnostics-files-stay-tracked]: `repo.ensure_diagnostics_dir` makes the
directory ignore itself, which does not untrack files committed before. The
`untracked_exports` gate rejects staging them (root and nested contexts) while letting the
removal through, `gitgates.untrack_diagnostics` and migration Step 14 take them out of the
index without touching the files on disk, and `along doctor` reports them. Every case runs
in a throwaway git repository.
"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
for _path in (SCRIPTS_DIR, TESTS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import hermetic  # noqa: F401  (enforces the official test runner)
from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import gitgates, migration, repochecks

AUDIT = ".along/diagnostics/hooks_audit.jsonl"
NESTED = "apps/web/.along/diagnostics/activity/claude--s1.json"


def _du_git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", check=True)


def _du_write(root, rel, text="{}\n"):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


def _du_tracked(root):
    return set(_du_git(root, "ls-files").stdout.split())


class TestDiagnosticsGateCheck(unittest.TestCase):

    def test_diagnostics_paths_are_rejected_at_any_depth(self):
        files = [AUDIT, NESTED, ".along/diagnostics/circuit_breaker.json",
                 "docs/diagnostics/notes.md", ".along/diagnosticsx/a.json",
                 ".along/ISSUES.md", "src/diagnostics.py"]
        found = [loc for loc, _ in repochecks.check_untracked_exports(files, lambda _p: "", {})]
        self.assertEqual(sorted(found), sorted([AUDIT, NESTED, ".along/diagnostics/circuit_breaker.json"]))

    def test_message_names_the_fix(self):
        (_, message), = repochecks.check_untracked_exports([AUDIT], lambda _p: "", {})
        self.assertIn("git rm --cached", message)
        self.assertIn("along migrate --apply", message)

    def test_dashboard_exports_are_still_rejected(self):
        found = [loc for loc, _ in repochecks.check_untracked_exports(
            [".along/dashboard.html", "sub/.along/DASHBOARD.md"], lambda _p: "", {})]
        self.assertEqual(len(found), 2)


class GitRepoCase(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along_diag_untracked_")
        _du_git(self.root, "init", "-q")
        _du_git(self.root, "config", "user.email", "t@example.com")
        _du_git(self.root, "config", "user.name", "t")
        _du_git(self.root, "config", "core.autocrlf", "false")
        _du_write(self.root, ".along/ISSUES.md", "# Issues\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def commit_with_diagnostics(self):
        """A history from before the self-ignore: diagnostics committed with the rest."""
        for rel in (AUDIT, NESTED):
            _du_write(self.root, rel)
        _du_git(self.root, "add", "-A")
        _du_git(self.root, "commit", "-q", "--no-verify", "-m", "init")


class TestPreCommitGate(GitRepoCase):

    def _gates(self):
        return {v.gate for v in gitgates.check_pre_commit(self.root)}

    def test_staging_diagnostics_is_rejected(self):
        _du_write(self.root, AUDIT)
        _du_git(self.root, "add", "-A")
        self.assertIn("untracked_exports", self._gates())

    def test_untracking_diagnostics_passes(self):
        self.commit_with_diagnostics()
        _du_git(self.root, "rm", "--cached", "-q", AUDIT, NESTED)
        self.assertNotIn("untracked_exports", self._gates())


class TestUntrackDiagnostics(GitRepoCase):

    def test_untrack_keeps_files_on_disk_and_is_idempotent(self):
        self.commit_with_diagnostics()
        self.assertEqual(gitgates.tracked_diagnostics(self.root), sorted([AUDIT, NESTED]))

        self.assertEqual(gitgates.untrack_diagnostics(self.root, dry_run=True), sorted([AUDIT, NESTED]))
        self.assertIn(AUDIT, _du_tracked(self.root), "dry run must not touch the index")

        self.assertEqual(gitgates.untrack_diagnostics(self.root), sorted([AUDIT, NESTED]))
        tracked = _du_tracked(self.root)
        self.assertNotIn(AUDIT, tracked)
        self.assertNotIn(NESTED, tracked)
        self.assertIn(".along/ISSUES.md", tracked, "only diagnostics leave the index")
        for rel in (AUDIT, NESTED):
            self.assertTrue(os.path.isfile(os.path.join(self.root, *rel.split("/"))))
        self.assertEqual(gitgates.untrack_diagnostics(self.root), [])

    def test_outside_git_is_a_no_op(self):
        plain = tempfile.mkdtemp(prefix="along_diag_nogit_")
        self.addCleanup(shutil.rmtree, plain, ignore_errors=True)
        _du_write(plain, AUDIT)
        self.assertEqual(gitgates.tracked_diagnostics(plain), [])
        self.assertEqual(gitgates.untrack_diagnostics(plain), [])


class TestMigrationStep(GitRepoCase):

    def setUp(self):
        super().setUp()
        import migrate_protocol
        self.mp = migrate_protocol

    def run_step(self, dry_run):
        mig = migration.Migration(self.root, dry_run=dry_run, printer=lambda _m: None)
        with contextlib.redirect_stdout(io.StringIO()):
            return self.mp.step_untrack_diagnostics(mig, self.root), mig

    def test_step_untracks_and_records(self):
        self.commit_with_diagnostics()
        paths, mig = self.run_step(dry_run=True)
        self.assertEqual(paths, sorted([AUDIT, NESTED]))
        self.assertIn(AUDIT, _du_tracked(self.root))

        paths, mig = self.run_step(dry_run=False)
        self.assertEqual(paths, sorted([AUDIT, NESTED]))
        self.assertNotIn(AUDIT, _du_tracked(self.root))
        self.assertEqual(mig.count("untrack diagnostics"), 2)
        self.assertEqual(self.run_step(dry_run=False)[0], [])

    def test_up_to_date_repository_still_untracks(self):
        """A repository already at the current version skips the chain, not Step 14."""
        from alongkit.version import CURRENT_PROTOCOL_VERSION
        _du_write(self.root, ".along/" + migration.STATE_FILENAME, CURRENT_PROTOCOL_VERSION + "\n")
        self.commit_with_diagnostics()
        with contextlib.redirect_stdout(io.StringIO()):
            code = self.mp.run_migrations(self.root, dry_run=False, backup=False)
        self.assertEqual(code, 0)
        self.assertEqual(gitgates.tracked_diagnostics(self.root), [])
        self.assertTrue(os.path.isfile(os.path.join(self.root, *AUDIT.split("/"))))


class TestDoctorReport(GitRepoCase):

    def doctor(self):
        import along_exec
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            try:
                along_exec.handle_doctor_command(self.root, [])
            except SystemExit:
                pass
        return out.getvalue()

    def test_doctor_warns_about_tracked_diagnostics(self):
        self.commit_with_diagnostics()
        report = self.doctor()
        self.assertIn("per-machine diagnostics file(s) tracked in git", report)
        self.assertIn(AUDIT, report)

    def test_doctor_is_quiet_when_nothing_is_tracked(self):
        _du_git(self.root, "add", "-A")
        _du_git(self.root, "commit", "-q", "--no-verify", "-m", "init")
        self.assertNotIn("diagnostics file(s) tracked", self.doctor())


if __name__ == "__main__":
    unittest.main()
