#!/usr/bin/env python3
"""
tests/test_update_maintenance_friction.py - [bug--update-maintenance-friction].

Covers: Along maintenance subcommands passing the plan gate (removal excluded), `along doctor
--fix` no longer classified read-only, schema findings on archived issues reported as warnings
while dangling issue references stay errors, `doctor --entities --fix` cleaning archived
issues, and migration backup retention, skip list and self-ignore file. Every test runs in a
throwaway directory; nothing touches the live repository.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import entities, migration
from alongkit.hooks import shellparse

from test_entity_reference_integrity import _ErRepo, _er_fm, _er_issue, _er_write


class TestMaintenanceCommands(unittest.TestCase):

    def test_maintenance_subcommands_pass_as_state_commands(self):
        for cmd in ("along update", "along update --local-only", "along init",
                    "along migrate --apply", "along doctor --entities --fix", "along hook install",
                    "along git setup", "along git sync", "along rules attach python",
                    "along rules restore", "python scripts/along_exec.py update --force"):
            self.assertTrue(shellparse.is_along_state_command(cmd), cmd)

    def test_removal_and_chained_mutations_do_not_pass(self):
        for cmd in ("along hook uninstall", "along hook install --uninstall",
                    "along update && rm -rf src", "along update > out.txt", "along bump patch",
                    "along commit -m x"):
            self.assertFalse(shellparse.is_along_state_command(cmd), cmd)

    def test_doctor_fix_is_not_read_only(self):
        self.assertTrue(shellparse.is_read_only_command("along doctor"))
        self.assertTrue(shellparse.is_read_only_command("along doctor --entities"))
        self.assertFalse(shellparse.is_read_only_command("along doctor --entities --fix"))
        self.assertFalse(shellparse.is_read_only_command("python scripts/along_exec.py doctor --fix"))


class TestArchivedIssues(_ErRepo):

    def test_schema_findings_on_archived_issue_are_warnings(self):
        _er_write(self.root, ".along/ISSUES/done/feat--old-task.md",
                  _er_issue("old-task", itype="refactor", status="done", milestone="v0.1.0-removed"))
        report = entities.validate_entities(self.root)
        self.assertEqual(report["errors"], [])
        warned = [msg for _, msg in report["warnings"]]
        self.assertIn("dangling milestone reference: 'v0.1.0-removed' (archived issue)", warned)
        self.assertTrue(any(m.startswith("invalid type: 'refactor'") for m in warned), warned)

    def test_open_issue_keeps_errors(self):
        _er_write(self.root, ".along/ISSUES/feat--new-task.md",
                  _er_issue("new-task", itype="refactor", milestone="v0.1.0-removed"))
        messages = [msg for _, msg in entities.validate_entities(self.root)["errors"]]
        self.assertIn("dangling milestone reference: 'v0.1.0-removed'", messages)
        self.assertTrue(any(m.startswith("invalid type: 'refactor'") for m in messages), messages)

    def test_dangling_issue_reference_on_archived_issue_stays_error(self):
        _er_write(self.root, ".along/ISSUES/done/feat--old-task.md",
                  _er_issue("old-task", status="done", blocked_by=["feat--long-gone-task"]))
        messages = [msg for _, msg in entities.validate_entities(self.root)["errors"]]
        self.assertEqual(messages, ["dangling blocked_by reference: 'feat--long-gone-task'"])

    def test_doctor_fix_drops_dangling_milestone_of_archived_issue(self):
        path = _er_write(self.root, ".along/ISSUES/done/feat--old-task.md",
                         _er_issue("old-task", status="done", milestone="v0.1.0-removed"))
        changed = entities.drop_dangling_milestones(self.root)
        self.assertEqual(changed, [".along/ISSUES/done/feat--old-task.md"])
        self.assertNotIn("milestone", _er_fm(path))


class TestMigrationBackups(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along_backup_")
        self.state = os.path.join(self.root, ".along")
        for rel in ("ISSUES/feat--a.md", "diagnostics/trace.json", ".session/s/plan.md",
                    "artifacts/lifecycle/test.log", "worktrees/w/x.txt"):
            _er_write(self.state, rel, "x\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _migration(self):
        return migration.Migration(self.root, dry_run=False, printer=lambda *_: None)

    def test_backup_skips_machine_local_state_and_ignores_itself(self):
        backup = self._migration().ensure_backup()
        copied = os.path.join(backup, ".along")
        self.assertTrue(os.path.isfile(os.path.join(copied, "ISSUES", "feat--a.md")))
        for skipped in ("diagnostics", ".session", "artifacts", "worktrees", migration.BACKUP_DIRNAME):
            self.assertFalse(os.path.exists(os.path.join(copied, skipped)), skipped)
        with open(os.path.join(self.state, migration.BACKUP_DIRNAME, ".gitignore"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "*\n")

    def test_prune_keeps_newest_snapshots(self):
        root = migration.backup_root(self.state)
        names = [f"2026-09-0{i}-120000" for i in range(1, 9)]
        for name in names:
            os.makedirs(os.path.join(root, name))
        removed = migration.prune_backups(self.state, keep=3)
        self.assertEqual(removed, names[:5])
        left = sorted(n for n in os.listdir(root) if n != ".gitignore")
        self.assertEqual(left, names[5:])


if __name__ == "__main__":
    unittest.main()
