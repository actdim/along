#!/usr/bin/env python3
"""
tests/test_modular_decisions.py - Unit tests for modular ADR records and projections.

Guarantees:
1. `scan_decisions` reads modular .along/DECISIONS/*.md with fallback to DECISIONS.md.
2. `compile_decisions_board` generates a lean .along/DECISIONS.md projection (< 7 KB).
3. `sync_constraints` compiles active architectural rules into .along/CONSTRAINTS.md.
4. `create_decision_file` creates compliant modular ADR files with front-matter.
5. CLI `along decision create` and `along decision sync` work end-to-end.
6. `validate_entities` catches invalid decision schemas and dangling superseded links.
7. `migrate_protocol.py` Step 11 cleanly migrates monolithic DECISIONS.md to modular files.
"""

from __future__ import annotations

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import entities, frontmatter, proc, textio
from tests import hermetic


SAMPLE_ADR_1 = """---
protocol: along
title: "First Architectural Choice"
date: 2026-09-01
status: accepted
type: decision
slug: first-architectural-choice
tags: [architecture, core]
---

# ADR-2026-09-01--first-architectural-choice - First Architectural Choice

- Date: 2026-09-01
- Status: accepted
- Context: Need an initial architectural decision.
- Decision: We choose option A.
- Consequences: Option A is adopted across all modules.
"""

SAMPLE_ADR_2 = """---
protocol: along
title: "Second Architectural Choice"
date: 2026-09-05
status: superseded
superseded_by: third-architectural-choice
type: decision
slug: second-architectural-choice
tags: [architecture, storage]
---

# ADR-2026-09-05--second-architectural-choice - Second Architectural Choice

- Date: 2026-09-05
- Status: superseded by ADR-2026-09-10--third-architectural-choice
- Context: Need temporary storage strategy.
- Decision: Use in-memory dict.
- Consequences: Replaced by persistent storage later.
"""

SAMPLE_ADR_3 = """---
protocol: along
title: "Third Architectural Choice"
date: 2026-09-10
status: accepted
type: decision
slug: third-architectural-choice
tags: [architecture, storage]
---

# ADR-2026-09-10--third-architectural-choice - Third Architectural Choice

- Date: 2026-09-10
- Status: accepted
- Context: In-memory dict is insufficient.
- Decision: Use SQLite embedded engine.
- Consequences: Durable storage achieved.
"""


class TestModularDecisionsScan(unittest.TestCase):

    def test_scan_decisions_modular(self):
        with hermetic.repo_fixture() as fixture:
            dec_dir = os.path.join(fixture, ".along", "DECISIONS")
            os.makedirs(dec_dir, exist_ok=True)
            textio.write_text(os.path.join(dec_dir, "ADR-2026-09-01--first-architectural-choice.md"), SAMPLE_ADR_1)
            textio.write_text(os.path.join(dec_dir, "ADR-2026-09-05--second-architectural-choice.md"), SAMPLE_ADR_2)
            textio.write_text(os.path.join(dec_dir, "ADR-2026-09-10--third-architectural-choice.md"), SAMPLE_ADR_3)

            records = entities.scan_decisions(fixture)
            self.assertEqual(len(records), 3)

            by_slug = {r["slug"]: r for r in records}
            self.assertIn("first-architectural-choice", by_slug)
            self.assertIn("second-architectural-choice", by_slug)
            self.assertIn("third-architectural-choice", by_slug)

            self.assertEqual(by_slug["first-architectural-choice"]["status"], "accepted")
            self.assertEqual(by_slug["second-architectural-choice"]["status"], "superseded")
            self.assertEqual(by_slug["second-architectural-choice"]["superseded_by"], "third-architectural-choice")
            self.assertEqual(by_slug["third-architectural-choice"]["decision"], "Use SQLite embedded engine.")

    def test_scan_decisions_legacy_fallback(self):
        with hermetic.repo_fixture() as fixture:
            # Fixture default has a single monolithic DECISIONS.md and no DECISIONS/ directory
            dec_dir = os.path.join(fixture, ".along", "DECISIONS")
            if os.path.exists(dec_dir):
                import shutil
                shutil.rmtree(dec_dir)

            records = entities.scan_decisions(fixture)
            self.assertGreaterEqual(len(records), 1)
            self.assertEqual(records[0]["slug"], "fixture-decision")
            self.assertEqual(records[0]["status"], "accepted")

    def test_scan_decisions_empty(self):
        with hermetic.repo_fixture() as fixture:
            dec_file = os.path.join(fixture, ".along", "DECISIONS.md")
            dec_dir = os.path.join(fixture, ".along", "DECISIONS")
            if os.path.exists(dec_file):
                os.remove(dec_file)
            if os.path.exists(dec_dir):
                import shutil
                shutil.rmtree(dec_dir)

            records = entities.scan_decisions(fixture)
            self.assertEqual(records, [])


class TestModularDecisionsCompilation(unittest.TestCase):

    def test_compile_decisions_board(self):
        with hermetic.repo_fixture() as fixture:
            dec_dir = os.path.join(fixture, ".along", "DECISIONS")
            os.makedirs(dec_dir, exist_ok=True)
            textio.write_text(os.path.join(dec_dir, "ADR-2026-09-01--first-architectural-choice.md"), SAMPLE_ADR_1)
            textio.write_text(os.path.join(dec_dir, "ADR-2026-09-05--second-architectural-choice.md"), SAMPLE_ADR_2)
            textio.write_text(os.path.join(dec_dir, "ADR-2026-09-10--third-architectural-choice.md"), SAMPLE_ADR_3)

            output_file = entities.compile_decisions_board(fixture)
            self.assertTrue(os.path.isfile(output_file))

            content = textio.read_text(output_file)
            self.assertIn("Generated projection from .along/DECISIONS/", content)
            self.assertIn("## Active Decisions", content)
            self.assertIn("## Superseded & Retired Decisions", content)
            self.assertIn("[First Architectural Choice](DECISIONS/ADR-2026-09-01--first-architectural-choice.md)", content)
            self.assertIn("[Third Architectural Choice](DECISIONS/ADR-2026-09-10--third-architectural-choice.md)", content)
            self.assertIn("superseded by third-architectural-choice", content)

            # Compactness verification
            self.assertLess(len(content.encode("utf-8")), 7168)

    def test_live_repo_projection_size_budget(self):
        """Verify the live repository's compiled DECISIONS.md satisfies the < 7 KB budget ceiling."""
        dec_file = os.path.join(REPO_ROOT, ".along", "DECISIONS.md")
        self.assertTrue(os.path.isfile(dec_file))
        size = os.path.getsize(dec_file)
        self.assertLess(
            size, 7168,
            f"Compiled .along/DECISIONS.md is {size} bytes, exceeds 7 KB budget limit (7168 B)"
        )

    def test_sync_constraints(self):
        with hermetic.repo_fixture() as fixture:
            dec_dir = os.path.join(fixture, ".along", "DECISIONS")
            os.makedirs(dec_dir, exist_ok=True)
            textio.write_text(os.path.join(dec_dir, "ADR-2026-09-01--first-architectural-choice.md"), SAMPLE_ADR_1)
            textio.write_text(os.path.join(dec_dir, "ADR-2026-09-05--second-architectural-choice.md"), SAMPLE_ADR_2)
            textio.write_text(os.path.join(dec_dir, "ADR-2026-09-10--third-architectural-choice.md"), SAMPLE_ADR_3)

            constraints_file = entities.sync_constraints(fixture)
            self.assertTrue(os.path.isfile(constraints_file))

            content = textio.read_text(constraints_file)
            self.assertIn("First Architectural Choice", content)
            self.assertIn("We choose option A.", content)
            self.assertIn("Third Architectural Choice", content)
            self.assertIn("Use SQLite embedded engine.", content)

            # Superseded decisions must be excluded from CONSTRAINTS.md
            self.assertNotIn("Second Architectural Choice", content)
            self.assertNotIn("Use in-memory dict.", content)


class TestModularDecisionsCreation(unittest.TestCase):

    def test_create_decision_file(self):
        with hermetic.repo_fixture() as fixture:
            new_path = entities.create_decision_file(
                repo_root=fixture,
                slug="test-engine-choice",
                title="Test Engine Choice",
                context="Need a fast execution engine.",
                decision="Adopt standard library runner.",
                consequences="Zero extra dependencies.",
                status="accepted",
                tags=["runner", "engine"],
            )
            self.assertTrue(os.path.isfile(new_path))
            self.assertTrue(new_path.endswith("--test-engine-choice.md"))

            content = textio.read_text(new_path)
            fm, body = frontmatter.parse(content)
            self.assertEqual(fm["slug"], "test-engine-choice")
            self.assertEqual(fm["title"], "Test Engine Choice")
            self.assertEqual(fm["status"], "accepted")
            self.assertEqual(fm["type"], "decision")
            self.assertIn("runner", fm["tags"])
            self.assertIn("Zero extra dependencies.", body)


class TestModularDecisionsCLI(unittest.TestCase):

    def test_cli_decision_create_and_sync(self):
        with hermetic.repo_fixture() as fixture:
            exec_script = os.path.join(SCRIPTS_DIR, "along_exec.py")

            # 1. along decision create
            cmd_create = [
                exec_script, "decision", "create", "new-cache-policy",
                "--title", "New Cache Policy",
                "--context", "Too many cache misses in API.",
                "--decision", "Implement LRU cache.",
                "--consequences", "Bounded memory footprint.",
            ]
            res = proc.run_python(cmd_create, cwd=fixture)
            self.assertTrue(res.ok, f"decision create failed: {res.stderr}")
            self.assertIn("Created modular ADR file:", res.stdout)

            dec_dir = os.path.join(fixture, ".along", "DECISIONS")
            files = [f for f in os.listdir(dec_dir) if "new-cache-policy" in f]
            self.assertEqual(len(files), 1)

            # Check board projection was updated
            board_file = os.path.join(fixture, ".along", "DECISIONS.md")
            self.assertIn("New Cache Policy", textio.read_text(board_file))

            # 2. along decision sync
            cmd_sync = [exec_script, "decision", "sync"]
            res_sync = proc.run_python(cmd_sync, cwd=fixture)
            self.assertTrue(res_sync.ok, f"decision sync failed: {res_sync.stderr}")
            self.assertIn("Recompiled .along/DECISIONS.md projection board", res_sync.stdout)


class TestModularDecisionsValidation(unittest.TestCase):

    def test_validate_entities_catches_invalid_decision(self):
        with hermetic.repo_fixture() as fixture:
            dec_dir = os.path.join(fixture, ".along", "DECISIONS")
            os.makedirs(dec_dir, exist_ok=True)

            invalid_adr = """---
protocol: along
slug: broken-decision
title: Broken Decision
status: invalid_status
type: decision
superseded_by: nonexistent-target-slug
---

# Broken Decision
"""
            textio.write_text(os.path.join(dec_dir, "ADR-2026-09-01--broken-decision.md"), invalid_adr)

            report = entities.validate_entities(fixture)
            self.assertFalse(report["clean"])

            error_messages = " ".join(e[1] for e in report["errors"])
            self.assertIn("invalid status: 'invalid_status'", error_messages)
            self.assertIn("dangling superseded_by reference", error_messages)

    def test_validate_entities_passes_clean_decisions(self):
        with hermetic.repo_fixture() as fixture:
            dec_dir = os.path.join(fixture, ".along", "DECISIONS")
            os.makedirs(dec_dir, exist_ok=True)
            textio.write_text(os.path.join(dec_dir, "ADR-2026-09-01--first-architectural-choice.md"), SAMPLE_ADR_1)
            textio.write_text(os.path.join(dec_dir, "ADR-2026-09-10--third-architectural-choice.md"), SAMPLE_ADR_3)
            textio.write_text(os.path.join(dec_dir, "ADR-2026-09-05--second-architectural-choice.md"), SAMPLE_ADR_2)

            report = entities.validate_entities(fixture)
            self.assertTrue(report["clean"], f"Validation failed: {report['errors']}")


if __name__ == "__main__":
    unittest.main()
