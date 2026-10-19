#!/usr/bin/env python3
"""
tests/test_entity_slimming.py - the slimmed entity model [debt--entity-model-slimming].

- `spike` is an issue type: keys parse, `along issue create spike` writes an Outcome section.
- Migration Step 16 turns RISKS/ records into `debt` issues tagged `risk` and SPIKES/ records
  into `spike--<slug>` issues, rewrites references, discards the scaffolded checklists, moves
  a custom checklist to docs/, backs everything up, keeps a collision, and is idempotent;
  it also runs for a repository already at the current version.
- Migration Step 3 no longer scaffolds RISKS/, SPIKES/, CHECKLISTS/.
- `along session gc` archives the blackboard of a closed issue into its session log.
Every case runs in a throwaway fixture repository.
"""

from __future__ import annotations

import contextlib
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
from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import entities, frontmatter, lifecycle, migration, proc, session, textio

EXEC = os.path.join(SCRIPTS_DIR, "along_exec.py")

RISK_RESOLVED = """---
protocol: along
slug: index-truncation
title: "Index truncation"
severity: high
status: resolved
owner: user
mitigation: "Fixed upstream."
created: 2026-09-07
updated: 2026-09-10
---

# Index truncation

Upstream defect.
"""

RISK_ACTIVE = """---
protocol: along
slug: rate-limit-hit
title: Rate limit
severity: low
status: active
created: 2026-09-07
updated: 2026-09-07
---

Provider rate limit.
"""

SPIKE_OPEN = """---
protocol: along
slug: headless-runtimes
type: spike
title: Headless runtimes
status: hypothesis
created: 2026-10-17
updated: 2026-10-17
tags: [spike, runtimes]
related: [task--fixture-sample-task]
---

# Spike: headless runtimes

## Questions
1. Which flags?
"""

SPIKE_DONE = """---
protocol: along
slug: duckdb-vs-sqlite
title: DuckDB vs SQLite
status: concluded
hypothesis: SQLite is smaller.
outcome: SQLite won.
created: 2026-08-30
---

# DuckDB vs SQLite
"""

REFERRER = """---
protocol: along
slug: uses-legacy-refs
type: bug
status: done
priority: medium
created: 2026-09-01
updated: 2026-09-01
completed: 2026-09-01
superseded_by: index-truncation
related: [risk--rate-limit-hit]
---

# Uses legacy refs

## Acceptance Criteria
- [x] Done
"""


def _slim_write(root, rel, text):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    textio.write_text(path, text, newline="\n")
    return path


class TestSpikeIssueType(unittest.TestCase):
    def test_spike_key_parses(self):
        self.assertEqual(entities.parse_key("spike--headless-runtimes"), ("spike", "headless-runtimes"))
        self.assertIn("spike", entities.ISSUE_TYPES)

    def test_issue_create_spike_has_outcome_section(self):
        with hermetic.repo_fixture() as root:
            res = proc.run_capture([sys.executable, EXEC, "issue", "create", "spike", "cache-eviction-probe",
                                    "--no-milestone"], cwd=root, env=hermetic.isolated_home_env())
            self.assertEqual(res.returncode, 0, res.stderr)
            path = os.path.join(root, ".along", "ISSUES", "spike--cache-eviction-probe.md")
            fm, body = frontmatter.parse(textio.read_text(path))
            self.assertEqual(fm["type"], "spike")
            self.assertIn("## Outcome", body)
            self.assertIn("## Acceptance Criteria", body)


class TestStep16(unittest.TestCase):
    def setUp(self):
        import migrate_protocol
        self.mp = migrate_protocol
        self.root = hermetic.make_repo_fixture(prefix="along_slim_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.along = os.path.join(self.root, ".along")
        _slim_write(self.root, ".along/RISKS/.gitkeep", "")
        _slim_write(self.root, ".along/RISKS/index-truncation.md", RISK_RESOLVED)
        _slim_write(self.root, ".along/RISKS/rate-limit-hit.md", RISK_ACTIVE)
        _slim_write(self.root, ".along/SPIKES/spike--headless-runtimes.md", SPIKE_OPEN)
        _slim_write(self.root, ".along/SPIKES/duckdb-vs-sqlite.md", SPIKE_DONE)
        _slim_write(self.root, ".along/CHECKLISTS/pre-commit.md", "---\nprotocol: along\nslug: pre-commit\n---\n\nx\n")
        _slim_write(self.root, ".along/CHECKLISTS/stage-completion.md", "---\nprotocol: along\n---\n\nx\n")
        _slim_write(self.root, ".along/CHECKLISTS/adaptive-ui-devices.md", "---\nprotocol: along\n---\n\n- [ ] phone\n")
        _slim_write(self.root, ".along/ISSUES/done/bug--uses-legacy-refs.md", REFERRER)

    def _step(self, dry_run=False):
        mig = migration.Migration(self.root, dry_run=dry_run, state_dir=self.along, printer=lambda _m: None)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            converted = self.mp.step_slim_entity_model(mig, self.root)
        return converted, mig, buf.getvalue()

    def _fm(self, rel):
        return frontmatter.parse(textio.read_text(os.path.join(self.along, *rel.split("/"))))

    def test_dry_run_writes_nothing(self):
        converted, _mig, _out = self._step(dry_run=True)
        self.assertEqual(len(converted), 4)
        self.assertTrue(os.path.isfile(os.path.join(self.along, "RISKS", "index-truncation.md")))
        self.assertFalse(os.path.exists(os.path.join(self.along, "ISSUES", "done",
                                                     "debt--index-truncation.md")))

    def test_converts_rewrites_and_cleans_up(self):
        converted, mig, out = self._step()
        self.assertEqual(sorted(converted), ["debt--index-truncation", "debt--rate-limit-hit",
                                             "spike--duckdb-vs-sqlite", "spike--headless-runtimes"])
        fm, body = self._fm("ISSUES/done/debt--index-truncation.md")
        self.assertEqual((fm["type"], fm["status"], fm["priority"], fm["completed"]),
                         ("debt", "done", "high", "2026-09-10"))
        self.assertIn("risk", fm["tags"])
        self.assertEqual(fm["owner"], "user")
        self.assertNotIn("severity", fm)
        self.assertIn("## Mitigation\n\nFixed upstream.", body)
        self.assertIn("- [x]", body)
        fm, body = self._fm("ISSUES/debt--rate-limit-hit.md")
        self.assertEqual((fm["status"], fm["priority"]), ("open", "low"))
        self.assertIn("# Rate limit", body)
        self.assertIn("- [ ]", body)
        fm, body = self._fm("ISSUES/spike--headless-runtimes.md")
        self.assertEqual((fm["type"], fm["status"], fm["priority"]), ("spike", "open", "medium"))
        self.assertIn("## Outcome", body)
        self.assertIn("## Questions", body)
        fm, body = self._fm("ISSUES/done/spike--duckdb-vs-sqlite.md")
        self.assertEqual(fm["status"], "done")
        self.assertIn("## Hypothesis\n\nSQLite is smaller.", body)
        self.assertIn("## Outcome\n\nSQLite won.", body)
        ref, _ = self._fm("ISSUES/done/bug--uses-legacy-refs.md")
        self.assertEqual(ref["superseded_by"], "debt--index-truncation")
        self.assertEqual(ref["related"], ["debt--rate-limit-hit"])
        for d in ("RISKS", "SPIKES", "CHECKLISTS"):
            self.assertFalse(os.path.exists(os.path.join(self.along, d)), d)
        moved = os.path.join(self.root, "docs", "topic--adaptive-ui-devices.md")
        self.assertIn("- [ ] phone", textio.read_text(moved))
        self.assertIn("[AGENT ACTION]", out)
        backups = os.path.join(self.along, migration.BACKUP_DIRNAME)
        self.assertTrue(os.path.isdir(backups) and os.listdir(backups), "removals are backed up")
        self.assertEqual(entities.find_issue_by_slug(self.root, "headless-runtimes")["type"], "spike")
        self.assertEqual(self._step()[0], [], "second run is a no-op")

    def test_collision_is_kept(self):
        _slim_write(self.root, ".along/ISSUES/debt--rate-limit-hit.md", "---\nprotocol: along\n---\n\n# taken\n")
        _converted, mig, out = self._step()
        self.assertTrue(os.path.isfile(os.path.join(self.along, "RISKS", "rate-limit-hit.md")))
        self.assertIn("collides", out)
        self.assertGreaterEqual(mig.count("keep"), 1)

    def test_up_to_date_repository_still_heals(self):
        from alongkit.version import CURRENT_PROTOCOL_VERSION
        _slim_write(self.root, ".along/" + migration.STATE_FILENAME, CURRENT_PROTOCOL_VERSION + "\n")
        with contextlib.redirect_stdout(io.StringIO()):
            code = self.mp.run_migrations(self.root, dry_run=False, backup=True)
        self.assertEqual(code, 0)
        self.assertFalse(os.path.exists(os.path.join(self.along, "RISKS")))
        self.assertTrue(os.path.isfile(os.path.join(self.along, "ISSUES", "debt--rate-limit-hit.md")))


class TestStep3Skeleton(unittest.TestCase):
    def test_no_legacy_entity_folders_are_scaffolded(self):
        import migrate_protocol
        with hermetic.repo_fixture(prefix="along_skel_") as root:
            along = os.path.join(root, ".along")
            mig = migration.Migration(root, dry_run=False, state_dir=along, printer=lambda _m: None)
            with contextlib.redirect_stdout(io.StringIO()):
                migrate_protocol.step_migrate_v1_5_entity_ecosystem(mig, root, along)
            for d in ("RISKS", "SPIKES", "CHECKLISTS"):
                self.assertFalse(os.path.exists(os.path.join(along, d)), d)
            self.assertTrue(os.path.isdir(os.path.join(along, "MILESTONES")))


class TestSessionGc(unittest.TestCase):
    SLUG = "fixture-sample-task"

    def test_closed_issue_blackboard_is_archived_and_removed(self):
        with hermetic.repo_fixture(prefix="along_gc_") as root:
            session.init_session(root, self.SLUG)
            session.append_trace(root, self.SLUG, "left behind")
            issue = os.path.join(root, ".along", "ISSUES", f"task--{self.SLUG}.md")
            content = frontmatter.update(textio.read_text(issue), {"status": "done", "completed": "2026-10-19"})
            textio.write_text(os.path.join(root, ".along", "ISSUES", "done", f"task--{self.SLUG}.md"), content)
            os.remove(issue)
            self.assertEqual(lifecycle.gc_closed_blackboards(root, dry_run=True), [self.SLUG])
            self.assertTrue(os.path.isdir(session.get_session_dir(root, self.SLUG)))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(lifecycle.gc_closed_blackboards(root), [self.SLUG])
            self.assertFalse(os.path.isdir(session.get_session_dir(root, self.SLUG)))
            log = lifecycle.session_log_path(root, self.SLUG, entities.today_iso())
            self.assertIn("archived by session gc", textio.read_text(log))

    def test_open_issue_blackboard_is_kept(self):
        with hermetic.repo_fixture(prefix="along_gc_") as root:
            session.init_session(root, self.SLUG)
            self.assertEqual(lifecycle.gc_closed_blackboards(root), [])
            self.assertTrue(os.path.isdir(session.get_session_dir(root, self.SLUG)))


if __name__ == "__main__":
    unittest.main()
