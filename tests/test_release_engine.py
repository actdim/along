#!/usr/bin/env python3
"""
tests/test_release_engine.py - the release must verify before it writes, and be undoable.

Every case corresponds to a way `along_version_bump.py` used to damage a repository, from
`[bug--release-engine-mutates-before-tests-and-reinstalls-globals]`:

- it bumped the version, rewrote the tree with the sanitizer, and flipped milestone files
  to `completed`, and only THEN ran the tests, then printed "Release aborted" and exited
  over a half-released tree with no rollback;
- it ran those tests only when `--commit` was passed, so a plain `patch` verified nothing;
- it reconciled milestones with two unanchored `re.sub` calls over the whole file, so
  `status: open` in a target-issue table was rewritten as well, and matched milestones by
  filename substring;
- it staged the release commit with `git add -A`, sweeping in every unrelated edit;
- it finished by running `install.ps1 -Target all`, which deletes and recreates
  `~/.claude/rules` and recopies four providers' skill folders, with the exit code ignored.

Fixtures are throwaway trees from `tests/hermetic.py`; the git cases build their own
temporary repository. Nothing here points the engine at the repository that contains it.
"""

from __future__ import annotations

import ast
import io
import os
import shutil
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
for _path in (SCRIPTS_DIR, TESTS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import hermetic
from alongkit import proc, textio, transaction

RELEASE_ENGINE = os.path.join(SCRIPTS_DIR, "along_version_bump.py")

#: A lifecycle test hook that records the version it saw, then exits with `EXIT_CODE`.
#: The recorded value is the proof that the gate ran before the bump: it must be the OLD
#: version, whatever the release later writes.
TEST_HOOK = """#!/usr/bin/env python3
import os

with open("VERSION", "r", encoding="utf-8") as handle:
    seen = handle.read().strip()
with open(os.path.join(".along", "gate-saw.txt"), "w", encoding="utf-8") as handle:
    handle.write(seen)
raise SystemExit({exit_code})
"""

#: The milestone the release should reconcile. Its body repeats `status:` and
#: `progress_pct:` on purpose: those lines are what the old global `re.sub` corrupted.
TARGET_MILESTONE = """---
protocol: along
protocol_version: "{version}"
slug: v1.4.3-target-milestone
title: "Target milestone"
status: in-progress
due_date: 2026-12-31
created: 2026-09-01
target_issues: [fixture-sample-task]
progress_pct: 40
---

# Target milestone

| issue | state |
| :--- | :--- |
| fixture-sample-task | status: open |

The line `progress_pct: 40` belongs to the body and must survive a reconciliation.
"""

#: Filename carries the version, front-matter slug does not: the old substring match on
#: `os.path.basename` claimed this file, the slug match must not.
DECOY_MILESTONE = """---
protocol: along
protocol_version: "{version}"
slug: unrelated-milestone
title: "Unrelated milestone"
status: in-progress
due_date: 2026-12-31
created: 2026-09-01
target_issues: []
progress_pct: 40
---

# Unrelated milestone

Named after a version it does not target.
"""

#: `1.4.3` is a prefix of `1.4.30`, which a substring match cannot tell apart.
NEIGHBOUR_MILESTONE = """---
protocol: along
protocol_version: "{version}"
slug: v1.4.30-much-later-milestone
title: "Much later milestone"
status: in-progress
due_date: 2027-12-31
created: 2026-09-01
target_issues: []
progress_pct: 5
---

# Much later milestone

A version whose string merely starts with the one being released.
"""


def snapshot_tree(root):
    """Every file under `root` as {relative path: exact bytes}."""
    out = {}
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        for name in files:
            path = os.path.join(current, name)
            rel = os.path.relpath(path, root).replace("\\", "/")
            with io.open(path, "rb") as handle:
                out[rel] = handle.read()
    return out


def code_string_literals(path):
    """Every string literal in `path` except docstrings.

    A structural check has to distinguish code from prose: this engine's docstring
    describes the installer call it no longer makes, and a plain substring search over
    the source cannot tell the difference between documenting a defect and committing it.
    """
    with io.open(path, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)

    docstrings = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
            continue
        body = getattr(node, "body", None)
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            docstrings.add(id(body[0].value))

    return [node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and id(node) not in docstrings]


class ReleaseEngineFixtureCase(unittest.TestCase):
    """A throwaway project with a VERSION manifest, three milestones, and a test hook."""

    def setUp(self):
        self.root = hermetic.make_repo_fixture(prefix="along-release-")
        self.version_file = os.path.join(self.root, "VERSION")
        textio.write_text(self.version_file, "1.4.2\n")

        milestones = os.path.join(self.root, ".along", "MILESTONES")
        self.target = os.path.join(milestones, "v1.4.3-target-milestone.md")
        self.decoy = os.path.join(milestones, "v1.4.3-named-after-a-version.md")
        self.neighbour = os.path.join(milestones, "v1.4.30-much-later-milestone.md")
        version = hermetic.CURRENT_PROTOCOL_VERSION
        textio.write_text(self.target, TARGET_MILESTONE.format(version=version))
        textio.write_text(self.decoy, DECOY_MILESTONE.format(version=version))
        textio.write_text(self.neighbour, NEIGHBOUR_MILESTONE.format(version=version))

        self.install_test_hook(0)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def install_test_hook(self, exit_code):
        textio.write_text(os.path.join(self.root, ".along", "scripts", "test.py"),
                          TEST_HOOK.format(exit_code=exit_code))

    def run_release(self, *args):
        return proc.run_python([RELEASE_ENGINE, *args], cwd=self.root)

    def read(self, path):
        return textio.read_text(path)

    def gate_saw(self):
        path = os.path.join(self.root, ".along", "gate-saw.txt")
        return self.read(path).strip() if os.path.exists(path) else None


class TestGatesPrecedeMutations(ReleaseEngineFixtureCase):
    """REQ-1: the gates run on the untouched tree, whether or not --commit is passed."""

    def test_a_bump_without_commit_still_runs_the_tests(self):
        result = self.run_release("patch")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.gate_saw(), "1.4.2",
                         "the test hook did not run, or ran after the bump")
        self.assertEqual(self.read(self.version_file).strip(), "1.4.3")

    def test_the_typography_and_link_gates_also_run_without_commit(self):
        result = self.run_release("patch")
        self.assertIn("Typography clean", result.stdout)
        self.assertIn("Link integrity verified", result.stdout)

    def test_failing_tests_leave_the_tree_byte_identical(self):
        self.install_test_hook(1)
        before = snapshot_tree(self.root)

        result = self.run_release("patch")

        self.assertEqual(result.returncode, 1)
        self.assertIn("Release aborted", result.stderr)
        after = snapshot_tree(self.root)
        # The hook's own record is the one expected new file.
        after.pop(".along/gate-saw.txt", None)
        before.pop(".along/gate-saw.txt", None)
        self.assertEqual(after, before,
                         "a failed release must not leave a single modified byte")
        self.assertEqual(self.read(self.version_file).strip(), "1.4.2")

    def test_no_verify_is_the_only_way_to_skip_the_gates(self):
        self.install_test_hook(1)
        result = self.run_release("patch", "--no-verify")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(self.gate_saw(), "--no-verify still ran the test hook")
        self.assertEqual(self.read(self.version_file).strip(), "1.4.3")


class TestReleaseRollsBackOnFailure(ReleaseEngineFixtureCase):
    """REQ-2: a failure after the first write restores the tree and says what it restored."""

    def test_a_failure_after_the_bump_restores_every_file(self):
        # A CHANGELOG that is not valid UTF-8 fails the changelog step, which runs after
        # the version bump and the milestone reconciliation have already written.
        changelog = os.path.join(self.root, "CHANGELOG.md")
        with io.open(changelog, "wb") as handle:
            handle.write(b"# Changelog\n\n\xff\xfe not utf-8\n")
        before = snapshot_tree(self.root)

        result = self.run_release("patch")

        self.assertEqual(result.returncode, 1)
        self.assertIn("Rolled back", result.stderr)
        after = snapshot_tree(self.root)
        after.pop(".along/gate-saw.txt", None)
        before.pop(".along/gate-saw.txt", None)
        self.assertEqual(after, before, "the rollback did not restore the tree exactly")

    def test_the_abort_names_the_files_it_put_back(self):
        changelog = os.path.join(self.root, "CHANGELOG.md")
        with io.open(changelog, "wb") as handle:
            handle.write(b"# Changelog\n\n\xff\xfe not utf-8\n")

        result = self.run_release("patch")
        self.assertIn("VERSION", result.stderr)
        self.assertIn("v1.4.3-target-milestone.md", result.stderr)


class TestMilestoneReconciliationIsAnchored(ReleaseEngineFixtureCase):
    """REQ-5: front-matter of the milestone whose own slug names the version, nothing else."""

    def test_only_front_matter_of_the_matching_milestone_changes(self):
        decoy_before = snapshot_tree(self.root)[
            os.path.relpath(self.decoy, self.root).replace("\\", "/")]
        neighbour_rel = os.path.relpath(self.neighbour, self.root).replace("\\", "/")
        neighbour_before = snapshot_tree(self.root)[neighbour_rel]

        result = self.run_release("patch")
        self.assertEqual(result.returncode, 0, result.stderr)

        target = self.read(self.target)
        head, _, body = target.partition("\n---\n")
        self.assertIn("status: completed", head)
        self.assertIn("progress_pct: 100", head)
        self.assertIn("| fixture-sample-task | status: open |", body,
                      "the body's status line was rewritten")
        self.assertIn("`progress_pct: 40` belongs to the body", body)

        after = snapshot_tree(self.root)
        self.assertEqual(after[os.path.relpath(self.decoy, self.root).replace("\\", "/")],
                         decoy_before,
                         "a milestone matched by filename rather than slug was rewritten")
        self.assertEqual(after[neighbour_rel], neighbour_before,
                         "v1.4.30 was matched as a substring of v1.4.3")

    def test_matching_is_reported_when_no_milestone_names_the_version(self):
        textio.write_text(self.version_file, "2.9.9\n")
        os.remove(self.target)
        result = self.run_release("patch")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("nothing to reconcile", result.stdout)


class TestReleaseTouchesNoGlobalState(unittest.TestCase):
    """REQ-3: a version bump does not reinstall the machine's agent configuration."""

    def test_the_engine_never_invokes_an_installer(self):
        offenders = [literal for literal in code_string_literals(RELEASE_ENGINE)
                     if "install.ps1" in literal or "install.sh" in literal
                     or "powershell" in literal.lower()]
        self.assertEqual(offenders, [],
                         "a release must not run the installer: it deletes and recreates "
                         "~/.claude/rules and recopies four providers' skill folders")

    def test_the_global_sync_helper_is_gone(self):
        with io.open(RELEASE_ENGINE, "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("sync_local_global_install", source)

    def test_the_engine_reads_nothing_from_the_user_home(self):
        with io.open(RELEASE_ENGINE, "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("expanduser", source)


class TestReleaseCommitStagesOnlyItsOwnPaths(ReleaseEngineFixtureCase):
    """REQ-6 and REQ-7: explicit staging, an annotated tag, and a CHANGELOG entry."""

    def setUp(self):
        super().setUp()
        if not shutil.which("git"):
            self.skipTest("git is unavailable")
        for args in (["init", "-q"], ["config", "user.email", "fixture@example.invalid"],
                     ["config", "user.name", "Fixture"], ["add", "-A"],
                     ["commit", "-q", "-m", "chore: fixture baseline"]):
            result = proc.git(args, cwd=self.root)
            self.assertTrue(result.ok, f"git {args[0]} failed: {result.stderr}")

    def _commit_paths(self):
        shown = proc.git(["show", "--name-only", "--pretty=format:", "HEAD"], cwd=self.root)
        self.assertTrue(shown.ok, shown.stderr)
        return set(shown.lines())

    def test_unrelated_edits_stay_out_of_the_release_commit(self):
        textio.write_text(os.path.join(self.root, "README.md"),
                          "# Fixture Project\n\nAn edit in progress. See [Index](./docs/INDEX.md).\n")
        textio.write_text(os.path.join(self.root, "scratch.txt"), "untracked work\n")

        result = self.run_release("patch", "--commit")
        self.assertEqual(result.returncode, 0, result.stderr)

        committed = self._commit_paths()
        self.assertIn("VERSION", committed)
        self.assertNotIn("README.md", committed,
                         "git add -A swept an unrelated edit into the release commit")
        self.assertNotIn("scratch.txt", committed)

        status = proc.git(["status", "--porcelain", "-u"], cwd=self.root)
        self.assertIn("README.md", status.stdout, "the unrelated edit was consumed")

    def test_an_annotated_tag_and_a_changelog_section_are_created(self):
        result = self.run_release("patch", "--commit")
        self.assertEqual(result.returncode, 0, result.stderr)

        tags = proc.git(["tag", "-l"], cwd=self.root)
        self.assertIn("v1.4.3", tags.lines())
        kind = proc.git(["cat-file", "-t", "v1.4.3"], cwd=self.root)
        self.assertEqual(kind.out, "tag", "the release tag must be annotated, not lightweight")

        changelog = self.read(os.path.join(self.root, "CHANGELOG.md"))
        self.assertIn("## v1.4.3", changelog)
        self.assertIn("chore: fixture baseline", changelog,
                      "the changelog must list what git actually recorded")
        self.assertIn("CHANGELOG.md", self._commit_paths())


class TestFileTransaction(unittest.TestCase):
    """The rollback primitive itself: byte-exact restore, created files removed."""

    def setUp(self):
        self.root = hermetic.make_repo_fixture(prefix="along-transaction-")
        self.tx = transaction.FileTransaction(self.root, "unit test")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_a_modified_file_is_restored_byte_for_byte(self):
        path = os.path.join(self.root, "crlf.md")
        payload = b"# Title\r\n\r\nBody with CRLF endings.\r\n"
        with io.open(path, "wb") as handle:
            handle.write(payload)

        self.tx.write(path, "# Title\n\nRewritten with LF.\n")
        self.assertEqual(self.tx.rollback(), ["crlf.md"])
        with io.open(path, "rb") as handle:
            self.assertEqual(handle.read(), payload)

    def test_a_created_file_and_its_directory_are_removed(self):
        path = os.path.join(self.root, "new", "deeper", "created.md")
        self.tx.write(path, "created by the transaction\n")
        self.assertTrue(os.path.exists(path))

        restored = self.tx.rollback()
        self.assertEqual(restored, [os.path.join("new", "deeper", "created.md")
                                    + " (removed, did not exist)"])
        self.assertFalse(os.path.exists(os.path.join(self.root, "new")))

    def test_the_first_snapshot_wins(self):
        path = os.path.join(self.root, "twice.md")
        textio.write_text(path, "original\n")
        self.tx.write(path, "first\n")
        self.tx.write(path, "second\n")
        self.tx.rollback()
        self.assertEqual(textio.read_text(path), "original\n")

    def test_commit_gives_up_the_rollback(self):
        path = os.path.join(self.root, "kept.md")
        textio.write_text(path, "original\n")
        self.tx.write(path, "released\n")
        self.tx.commit()
        self.assertEqual(self.tx.rollback(), [])
        self.assertEqual(textio.read_text(path), "released\n")

    def test_changed_reports_only_what_actually_differs(self):
        touched = os.path.join(self.root, "touched.md")
        untouched = os.path.join(self.root, "untouched.md")
        textio.write_text(touched, "before\n")
        textio.write_text(untouched, "before\n")
        self.tx.protect(untouched)
        self.tx.write(touched, "after\n")
        self.assertEqual(self.tx.changed(), ["touched.md"])

    def test_an_unrestorable_mutation_is_reported_not_hidden(self):
        self.tx.mark_unrestorable("a child process wrote paths we cannot see")
        self.assertEqual(self.tx.unrestorable,
                         ["a child process wrote paths we cannot see"])


if __name__ == "__main__":
    unittest.main()
