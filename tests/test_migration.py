#!/usr/bin/env python3
"""
tests/test_migration.py - the migration must never be able to lose content.

Every case corresponds to a way `migrate_protocol.py` used to damage a repository, from
`[bug--migration-deletes-destination-without-backup]`:

- it moved legacy `.agents/` content onto `.along/` by calling `os.remove(dst)` first, so
  a repository holding both (a partial migration, or two branches migrating separately)
  lost the newer `DECISIONS.md` and `HISTORY.md`, which are append-only by protocol and
  therefore irrecoverable;
- it had no dry run, so there was no way to see the plan before it executed;
- it took no backup, so there was nothing to go back to;
- it read markdown with `errors="ignore"` and wrote the result back, deleting every
  undecodable byte of a file that was not valid UTF-8;
- it recorded no state, so all eight steps re-ran on every invocation;
- it was invoked implicitly by `install.ps1` and by the test suite, against whatever
  repository they happened to sit in.

The assertions are about content on disk, not about the engine's output: a migration that
prints "completed successfully" over a truncated `HISTORY.md` is the failure being tested.

Fixtures are throwaway trees; nothing here points the engine at the repository that
contains it.
"""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
for _path in (SCRIPTS_DIR, TESTS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import hermetic
from alongkit import migration, proc, textio
from alongkit.version import CURRENT_PROTOCOL_VERSION

ENGINE = os.path.join(SCRIPTS_DIR, "migrate_protocol.py")

#: An ADR only the current `.along/DECISIONS.md` knows about.
CURRENT_ADR = (
    "# Architectural Decisions\n\n"
    "## ADR-2026-09-01--current-decision - Recorded on the current branch\n\n"
    "- Date: 2026-09-01\n"
    "- Status: accepted\n"
    "- Context: Written after the repository had already moved to .along/.\n"
    "- Decision: Keep it.\n"
    "- Consequences: None.\n"
)

#: An ADR only the legacy `.agents/DECISIONS.md` knows about.
LEGACY_ADR = (
    "# Architectural Decisions\n\n"
    "## ADR-2026-08-20--legacy-decision - Recorded before the move\n\n"
    "- Date: 2026-08-20\n"
    "- Status: accepted\n"
    "- Context: Written while the repository still used .agents/.\n"
    "- Decision: Keep it too.\n"
    "- Consequences: None.\n"
)

CURRENT_HISTORY = ("# History\n\n"
                   "2026-09-01 - current-work - claude-code - Done on the new layout - .\n")
LEGACY_HISTORY = ("# History\n\n"
                  "2026-08-20 - legacy-work - antigravity - Done on the old layout - .\n")

CURRENT_ISSUE = """---
protocol: along
protocol_version: "{version}"
slug: shared-slug
type: bug
status: in-progress
priority: high
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [current]
---

# The current issue body

Written after the move to .along/, and the only copy that reflects today's work.
"""

LEGACY_ISSUE = """---
protocol: along
slug: shared-slug
type: bug
status: open
priority: low
created: 2026-08-20
updated: 2026-08-20
agent: antigravity
tags: [legacy]
---

# The legacy issue body

Written before the move, and stale, but still the author's text.
"""


def tree_digest(root: str) -> str:
    """A hash of every file path and its bytes under `root`, for before/after equality."""
    digest = hashlib.sha256()
    for current, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(files):
            path = os.path.join(current, name)
            digest.update(os.path.relpath(path, root).replace("\\", "/").encode("utf-8"))
            with open(path, "rb") as handle:
                digest.update(handle.read())
    return digest.hexdigest()


def read(path: str) -> str:
    with io.open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def migrate(root: str, *flags: str):
    """Run the engine as a child process, the way every caller reaches it."""
    return proc.run_capture([sys.executable, ENGINE, root, *flags])


def collision_fixture() -> str:
    """A repository mid-migration: a populated `.agents/` beside a populated `.along/`.

    This is the state the engine used to resolve by deleting the `.along/` side.
    """
    root = hermetic.make_repo_fixture(prefix="along-collision-")
    along = os.path.join(root, ".along")
    agents = os.path.join(root, ".agents")

    textio.write_text(os.path.join(along, "DECISIONS.md"), CURRENT_ADR)
    textio.write_text(os.path.join(along, "HISTORY.md"), CURRENT_HISTORY)
    textio.write_text(os.path.join(along, "ISSUES", "bug--shared-slug.md"),
                      CURRENT_ISSUE.format(version=CURRENT_PROTOCOL_VERSION))

    textio.write_text(os.path.join(agents, "DECISIONS.md"), LEGACY_ADR)
    textio.write_text(os.path.join(agents, "HISTORY.md"), LEGACY_HISTORY)
    textio.write_text(os.path.join(agents, "ISSUES.md"),
                      "# Active Issues\n\n## Active\n- [ ] `(bug)` stale-board-entry\n")
    textio.write_text(os.path.join(agents, "ISSUES", "bug--shared-slug.md"), LEGACY_ISSUE)
    textio.write_text(os.path.join(agents, "ISSUES", "feat--legacy-only.md"),
                      "---\nprotocol: along\nslug: legacy-only\ntype: feat\n"
                      "status: open\n---\n\n# Only in the legacy directory\n")
    return root


class TestUnionMerge(unittest.TestCase):
    """The primitive that replaces `os.remove(dst)` for append-only files."""

    def test_sections_from_both_sides_survive(self):
        merged, adopted = migration.union_merge(CURRENT_ADR, LEGACY_ADR)
        self.assertEqual(adopted, 1)
        self.assertIn("ADR-2026-09-01--current-decision", merged)
        self.assertIn("ADR-2026-08-20--legacy-decision", merged)

    def test_a_section_present_in_both_is_not_duplicated(self):
        merged, adopted = migration.union_merge(CURRENT_ADR, CURRENT_ADR)
        self.assertEqual(adopted, 0)
        self.assertEqual(merged, CURRENT_ADR)
        self.assertEqual(merged.count("ADR-2026-09-01--current-decision"), 1)

    def test_lines_from_both_sides_survive(self):
        merged, adopted = migration.union_merge(CURRENT_HISTORY, LEGACY_HISTORY)
        self.assertEqual(adopted, 1)
        self.assertIn("current-work", merged)
        self.assertIn("legacy-work", merged)
        self.assertEqual(merged.count("# History"), 1)

    def test_crlf_destination_keeps_its_line_endings(self):
        merged, _ = migration.union_merge(CURRENT_HISTORY.replace("\n", "\r\n"),
                                          LEGACY_HISTORY)
        self.assertIn("legacy-work", merged)
        self.assertTrue(merged.endswith("\r\n"))
        self.assertNotIn("\n", merged.replace("\r\n", ""),
                         "a CRLF destination must not gain a bare LF from the legacy copy")

    def test_an_empty_destination_takes_the_legacy_body(self):
        merged, adopted = migration.union_merge("", LEGACY_HISTORY)
        self.assertEqual(merged, LEGACY_HISTORY)
        self.assertEqual(adopted, 0)


class TestCollisionPolicy(unittest.TestCase):
    """`classify` decides what happens to a destination, and it is never deletion."""

    def test_append_only_files_are_recognized(self):
        for name in ("DECISIONS.md", "HISTORY.md"):
            self.assertEqual(migration.classify(os.path.join("x", ".along", name)),
                             migration.APPEND_ONLY, name)

    def test_projections_are_recognized(self):
        for name in ("ISSUES.md", "INDEX.md", "dashboard.html"):
            self.assertEqual(migration.classify(name), migration.PROJECTION, name)

    def test_entity_files_are_content(self):
        self.assertEqual(migration.classify("bug--x.md"), migration.CONTENT)

    def test_a_second_collision_gets_its_own_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "bug--x.md")
            textio.write_text(target, "destination\n")
            first = migration.sidecar_path(target)
            self.assertTrue(first.endswith("bug--x.legacy.md"))
            textio.write_text(first, "first legacy copy\n")
            second = migration.sidecar_path(target)
            self.assertTrue(second.endswith("bug--x.legacy-2.md"))


class TestMigrationLosesNothing(unittest.TestCase):
    """REQ-8: a populated `.agents/` beside a populated `.along/` loses no content."""

    def test_both_histories_are_present_after_migration(self):
        root = collision_fixture()
        try:
            result = migrate(root, "--apply")
            self.assertEqual(result.returncode, 0, result.stderr)

            decisions = read(os.path.join(root, ".along", "DECISIONS.md"))
            self.assertIn("ADR-2026-09-01--current-decision", decisions,
                          "the current ADR must survive the migration")
            self.assertIn("ADR-2026-08-20--legacy-decision", decisions,
                          "the legacy ADR must be adopted, not discarded")

            history = read(os.path.join(root, ".along", "HISTORY.md"))
            self.assertIn("current-work", history)
            self.assertIn("legacy-work", history)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_a_colliding_entity_keeps_the_destination_and_preserves_the_legacy_copy(self):
        root = collision_fixture()
        try:
            self.assertEqual(migrate(root, "--apply").returncode, 0)

            destination = os.path.join(root, ".along", "ISSUES", "bug--shared-slug.md")
            self.assertIn("The current issue body", read(destination),
                          "the destination entity must not be replaced by the legacy copy")

            sidecar = os.path.join(root, ".along", "ISSUES", "bug--shared-slug.legacy.md")
            self.assertTrue(os.path.isfile(sidecar),
                            "the legacy copy must be preserved beside the destination")
            self.assertIn("The legacy issue body", read(sidecar))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_legacy_only_entities_are_adopted(self):
        root = collision_fixture()
        try:
            self.assertEqual(migrate(root, "--apply").returncode, 0)
            adopted = os.path.join(root, ".along", "ISSUES", "feat--legacy-only.md")
            self.assertTrue(os.path.isfile(adopted),
                            "an entity that exists only in .agents/ must be moved over")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_the_destination_projection_wins_and_is_not_merged(self):
        """A board is derived state: the destination stays, the legacy copy goes."""
        root = collision_fixture()
        try:
            self.assertEqual(migrate(root, "--apply").returncode, 0)
            board = read(os.path.join(root, ".along", "ISSUES.md"))
            self.assertNotIn("stale-board-entry", board,
                             "a stale legacy projection must not overwrite the current board")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_a_backup_is_written_before_the_first_mutation(self):
        root = collision_fixture()
        try:
            self.assertEqual(migrate(root, "--apply").returncode, 0)
            backup_root = os.path.join(root, ".along", migration.BACKUP_DIRNAME)
            self.assertTrue(os.path.isdir(backup_root), "REQ-3: a backup must be written")
            stamps = [d for d in os.listdir(backup_root)
                      if os.path.isdir(os.path.join(backup_root, d))]
            self.assertEqual(len(stamps), 1, f"expected one timestamped backup, got {stamps}")

            saved = os.path.join(backup_root, stamps[0], ".agents", "DECISIONS.md")
            self.assertTrue(os.path.isfile(saved),
                            "the pre-migration state of .agents/ must be recoverable")
            self.assertIn("ADR-2026-08-20--legacy-decision", read(saved))
            self.assertTrue(
                os.path.isfile(os.path.join(backup_root, ".gitignore")),
                "the backup must keep itself out of the user's history")
        finally:
            shutil.rmtree(root, ignore_errors=True)


class TestDryRun(unittest.TestCase):
    """REQ-1: the plan is visible, and producing it changes nothing."""

    def test_dry_run_writes_nothing(self):
        root = collision_fixture()
        try:
            before = tree_digest(root)
            result = migrate(root, "--dry-run")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(tree_digest(root), before,
                             "a dry run must not change a single byte on disk")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_dry_run_prints_the_operations_it_would_perform(self):
        root = collision_fixture()
        try:
            out = migrate(root, "--dry-run").stdout
            self.assertIn("dry run", out.lower())
            self.assertIn("Planned operations:", out)
            self.assertIn("Full operation list:", out)
            self.assertIn("merge", out, "the plan must name the append-only merge")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_a_non_interactive_caller_gets_a_dry_run_by_default(self):
        """The installer and the test suite both invoked this engine with no flags."""
        root = collision_fixture()
        try:
            before = tree_digest(root)
            result = migrate(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(tree_digest(root), before,
                             "a tool-to-tool invocation must not mutate the repository")
            self.assertIn("--apply", result.stdout,
                          "the notice must say how to perform the migration")
        finally:
            shutil.rmtree(root, ignore_errors=True)


class TestMigrationState(unittest.TestCase):
    """REQ-4: a completed migration is recorded, and the next run is a no-op."""

    def test_the_state_marker_is_written(self):
        with hermetic.repo_fixture(prefix="along-state-") as root:
            self.assertEqual(migrate(root, "--apply").returncode, 0)
            self.assertEqual(migration.read_state(os.path.join(root, ".along")),
                             CURRENT_PROTOCOL_VERSION)

    def test_a_second_run_does_nothing(self):
        with hermetic.repo_fixture(prefix="along-state-") as root:
            self.assertEqual(migrate(root, "--apply").returncode, 0)
            after_first = tree_digest(root)

            second = migrate(root, "--apply")
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("nothing to do", second.stdout)
            self.assertEqual(tree_digest(root), after_first,
                             "a repository already at the current version must be left alone")

    def test_force_re_runs_the_steps(self):
        with hermetic.repo_fixture(prefix="along-state-") as root:
            self.assertEqual(migrate(root, "--apply").returncode, 0)
            forced = migrate(root, "--apply", "--force")
            self.assertEqual(forced.returncode, 0, forced.stderr)
            self.assertNotIn("nothing to do", forced.stdout)


class TestStrictReads(unittest.TestCase):
    """REQ-5: a file the engine cannot decode is reported, never rewritten."""

    def test_an_undecodable_entity_is_left_byte_identical(self):
        with hermetic.repo_fixture(prefix="along-encoding-") as root:
            broken = os.path.join(root, ".along", "ISSUES", "bug--cp1251-body.md")
            payload = ("---\nprotocol: along\nslug: cp1251-body\ntype: bug\n"
                       "status: open\n---\n\n# Windows-1251 body\n").encode("utf-8")
            payload += b"\xd0\xf3\xf1\xf1\xea\xe8\xe9 \xf2\xe5\xea\xf1\xf2\n"
            with open(broken, "wb") as handle:
                handle.write(payload)

            result = migrate(root, "--apply")
            self.assertEqual(result.returncode, 0, result.stderr)
            with open(broken, "rb") as handle:
                self.assertEqual(handle.read(), payload,
                                 "an undecodable file must not be rewritten from a partial read")
            self.assertIn("cp1251-body", result.stdout + result.stderr,
                          "a skipped file must be reported, not passed over in silence")


class TestAnAlreadyCurrentRepositoryIsLeftAlone(unittest.TestCase):
    """A migration with nothing to migrate must write nothing at all.

    The dry-run plan is what made this visible: run against a repository already at the
    current version, the engine still announced an AGENTS.md rewrite.
    """

    def test_a_crlf_agents_md_keeps_its_line_endings(self):
        with hermetic.repo_fixture(prefix="along-crlf-") as root:
            agents_md = os.path.join(root, "AGENTS.md")
            with open(agents_md, "rb") as handle:
                crlf = handle.read().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            with open(agents_md, "wb") as handle:
                handle.write(crlf)

            self.assertEqual(migrate(root, "--apply").returncode, 0)

            with open(agents_md, "rb") as handle:
                after = handle.read()
            self.assertNotIn(after.replace(b"\r\n", b""), (b"",),
                             "sanity: the file must not have been emptied")
            self.assertEqual(
                after.count(b"\n"), after.count(b"\r\n"),
                "the marker dedup must not rewrite CRLF as LF in a file it does not change")

    def test_duplicated_markers_are_still_collapsed(self):
        with hermetic.repo_fixture(prefix="along-dup-markers-") as root:
            agents_md = os.path.join(root, "AGENTS.md")
            body = read(agents_md)
            textio.write_text(agents_md,
                              body.replace(hermetic.BEGIN_MARKER,
                                           hermetic.BEGIN_MARKER + "\n" + hermetic.BEGIN_MARKER))

            self.assertEqual(migrate(root, "--apply").returncode, 0)
            self.assertEqual(read(agents_md).count(hermetic.BEGIN_MARKER), 1,
                             "a genuinely duplicated marker must still be collapsed")


class TestNoRawFileOperations(unittest.TestCase):
    """The engine may not reach past `alongkit.migration` to the filesystem.

    A structural guard rather than a behavioural one: every deletion this issue is about
    was one `os.remove` call, and each new one would have to be caught by a test written
    in advance. Routing them all through the recorded, backed-up, dry-runnable primitives
    is what makes that unnecessary.
    """

    FORBIDDEN = ("shutil.move", "shutil.rmtree", "shutil.copytree",
                 "os.remove", "os.rename", "os.unlink")

    def test_the_engine_calls_no_raw_destructive_operation(self):
        source = read(ENGINE)
        offenders = [call for call in self.FORBIDDEN if call in source]
        self.assertEqual(
            offenders, [],
            "migrate_protocol.py must go through alongkit.migration, which records, "
            f"backs up and honours --dry-run; found: {offenders}")


if __name__ == "__main__":
    unittest.main()
