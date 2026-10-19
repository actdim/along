#!/usr/bin/env python3
"""
tests/test_wrap_engine_writes.py - engine-written files reach the wrap commit; retired
gate artifacts leave through the migration.

Covers [bug--wrap-misses-engine-writes]:
- REQ-1/REQ-2: `closeout.managed_only_agents_changes` selects an `AGENTS.md` whose only
  change lies inside the managed blocks, and `_auto_commit_wrapped_work` commits it with
  `docs/topic--along-protocol.md`; a hand edit outside the blocks keeps `AGENTS.md` out.
- REQ-3/REQ-4: migration Step 15 discards `circuit_breaker.json`, `syntax_churn.json` and
  `.along/tool_rules.yaml` with a backup, reports a `tools:` section in gates.yaml, keeps
  the live activity traces, is idempotent and also runs for an up-to-date repository.
Every case runs in a throwaway git repository.
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

from alongkit import closeout, lifecycle, migration

AGENTS_V1 = (
    "<!-- BEGIN ALONG-PROTOCOL root (managed by along-init - do not edit by hand) -->\n"
    "# ALONG-PROTOCOL v0.0.1\nOld core.\n<!-- END ALONG-PROTOCOL -->\n\n"
    "## Project specifics\n\n"
    "<!-- BEGIN ALONG-RULES -->\n- old rules\n<!-- END ALONG-RULES -->\n"
    "- Build with `make`.\n"
)
REFERENCE = "---\nprotocol: along\nslug: along-protocol\n---\n<!-- ALONG-PROTOCOL-REFERENCE (managed by along-init - do not edit by hand) -->\n\n# Ref v1\n"


def _we_git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
                          cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True)


def _we_write(root, rel, text):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


class _GitRepo(unittest.TestCase):

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="along_wrap_engine_"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        _we_git(self.root, "init", "-q")
        _we_write(self.root, ".along/ISSUES.md", "# Active Issues\n")
        _we_write(self.root, "AGENTS.md", AGENTS_V1)
        _we_write(self.root, "docs/topic--along-protocol.md", REFERENCE)
        _we_write(self.root, "apps/web/AGENTS.md", AGENTS_V1)
        _we_git(self.root, "add", "-A")
        _we_git(self.root, "commit", "-q", "-m", "init")


class TestManagedOnlyAgentsChanges(_GitRepo):

    def test_block_only_changes_are_selected(self):
        refreshed = AGENTS_V1.replace("Old core.", "New core.").replace("- old rules", "- new rules")
        _we_write(self.root, "AGENTS.md", refreshed)
        _we_write(self.root, "apps/web/AGENTS.md", refreshed)
        self.assertEqual(closeout.managed_only_agents_changes(self.root), ["AGENTS.md", "apps/web/AGENTS.md"])

    def test_hand_edit_outside_blocks_is_left_out(self):
        _we_write(self.root, "AGENTS.md", AGENTS_V1.replace("Old core.", "New core.").replace("`make`", "`make all`"))
        self.assertEqual(closeout.managed_only_agents_changes(self.root), [])

    def test_untracked_agents_md_is_left_out(self):
        _we_write(self.root, "pkg/AGENTS.md", AGENTS_V1)
        self.assertEqual(closeout.managed_only_agents_changes(self.root), [])

    def test_line_endings_alone_do_not_count_as_a_hand_edit(self):
        refreshed = AGENTS_V1.replace("Old core.", "New core.").replace("\n", "\r\n")
        with open(os.path.join(self.root, "AGENTS.md"), "w", encoding="utf-8", newline="") as handle:
            handle.write(refreshed)
        self.assertEqual(closeout.managed_only_agents_changes(self.root), ["AGENTS.md"])


class TestAutoCommitIncludesEngineWrites(_GitRepo):

    def _plan(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = lifecycle._auto_commit_wrapped_work(self.root, "x", {}, dry_run=True)
        self.assertEqual(code, 0)
        return buf.getvalue()

    def test_managed_agents_and_reference_are_committed(self):
        self.assertIn("docs/topic--along-protocol.md", closeout.PROJECTION_FILES)
        _we_write(self.root, "AGENTS.md", AGENTS_V1.replace("Old core.", "New core."))
        _we_write(self.root, "docs/topic--along-protocol.md", REFERENCE.replace("Ref v1", "Ref v2"))
        out = self._plan()
        self.assertIn("     AGENTS.md", out)
        self.assertIn("docs/topic--along-protocol.md", out)

    def test_hand_edited_agents_stays_out(self):
        _we_write(self.root, "AGENTS.md", AGENTS_V1.replace("`make`", "`make all`"))
        _we_write(self.root, "docs/topic--along-protocol.md", REFERENCE.replace("Ref v1", "Ref v2"))
        out = self._plan()
        self.assertNotIn("     AGENTS.md", out)
        self.assertIn("docs/topic--along-protocol.md", out)


class TestRetiredGateArtifacts(unittest.TestCase):

    RETIRED = (".along/diagnostics/circuit_breaker.json", ".along/diagnostics/syntax_churn.json",
               ".along/tool_rules.yaml")
    LIVE = (".along/diagnostics/activity_trace.json", ".along/diagnostics/activity/claude--s1.json")

    def setUp(self):
        import migrate_protocol
        self.mp = migrate_protocol
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="along_retired_"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        _we_write(self.root, ".along/ISSUES.md", "# Active Issues\n")
        for rel in self.RETIRED + self.LIVE:
            _we_write(self.root, rel, "{}\n")

    def _step(self, dry_run=False):
        mig = migration.Migration(self.root, dry_run=dry_run, state_dir=os.path.join(self.root, ".along"),
                                  printer=lambda _m: None)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            removed = self.mp.step_remove_retired_gate_artifacts(mig, self.root)
        return removed, mig, buf.getvalue()

    def _exists(self, rel):
        return os.path.isfile(os.path.join(self.root, *rel.split("/")))

    def test_dry_run_touches_nothing(self):
        removed, _mig, _out = self._step(dry_run=True)
        self.assertEqual(len(removed), 3)
        self.assertTrue(all(self._exists(r) for r in self.RETIRED))

    def test_discards_with_backup_keeps_live_traces_and_is_idempotent(self):
        removed, mig, _out = self._step()
        self.assertEqual(len(removed), 3)
        self.assertEqual(mig.count("remove"), 3)
        self.assertFalse(any(self._exists(r) for r in self.RETIRED))
        self.assertTrue(all(self._exists(r) for r in self.LIVE))
        backups = os.path.join(self.root, ".along", ".migration-backup")
        self.assertTrue(os.path.isdir(backups) and os.listdir(backups), "discard must back up first")
        self.assertEqual(self._step()[0], [])

    def test_tools_section_in_gates_yaml_is_reported_not_rewritten(self):
        text = "gates: []\ntools:\n  - name: Bash\n"
        path = _we_write(self.root, ".along/rules/gates.yaml", text)
        _removed, mig, out = self._step()
        self.assertIn("tools:", out)
        self.assertEqual(mig.count("review"), 1)
        with open(path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), text)

    def test_up_to_date_repository_still_heals(self):
        from alongkit.version import CURRENT_PROTOCOL_VERSION
        _we_write(self.root, ".along/" + migration.STATE_FILENAME, CURRENT_PROTOCOL_VERSION + "\n")
        with contextlib.redirect_stdout(io.StringIO()):
            code = self.mp.run_migrations(self.root, dry_run=False, backup=True)
        self.assertEqual(code, 0)
        self.assertFalse(any(self._exists(r) for r in self.RETIRED))
        self.assertTrue(all(self._exists(r) for r in self.LIVE))


if __name__ == "__main__":
    unittest.main()
