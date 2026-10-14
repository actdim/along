#!/usr/bin/env python3
"""
tests/test_scaffold_profiles.py - Hermetic tests for AGENTS.md protocol block rendering per profile.

Covers [feat--gate-strictness-profiles] REQ-3, REQ-6:
- Managed AGENTS.md block renders only the rules and checklist relevant to the active profile.
- light profile: compacts completion checklist to core invariants and eases along-team escalation.
- strict profile: full procedural ceremony and explicit strict rules.
- standard profile: preserves default Along protocol verbatim.
"""

from __future__ import annotations

import os
import shutil
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import scaffold, textio
from hermetic import make_repo_fixture

PROTOCOL_PATH = os.path.join(REPO_ROOT, "skills", "along-init", "protocol.md")


class TestScaffoldProtocolBlockProfiles(unittest.TestCase):
    def setUp(self):
        self.raw_protocol = textio.read_text(PROTOCOL_PATH, strict=False)

    def test_standard_profile_preserves_default_protocol(self):
        block = scaffold.render_protocol_block(self.raw_protocol, profile="standard")
        self.assertIn("<!-- BEGIN ALONG-PROTOCOL root (managed by along-init - do not edit by hand) -->", block)
        self.assertIn("## Stage & Session Completion Checklist", block)
        self.assertIn("9. [ ] **Compaction**", block)
        self.assertIn("Mandatory Adaptive Complexity Escalation", block)

    def test_light_profile_compacts_checklist_and_rules(self):
        from alongkit.version import CURRENT_PROTOCOL_VERSION
        block = scaffold.render_protocol_block(self.raw_protocol, profile="light")
        self.assertIn("<!-- BEGIN ALONG-PROTOCOL root profile=light (managed by along-init - do not edit by hand) -->", block)
        self.assertIn(f"# ALONG-PROTOCOL v{CURRENT_PROTOCOL_VERSION} (profile: light)", block)

        # 5-step compact checklist
        self.assertIn("1. [ ] **Tests** [gate: test_before_stop]", block)
        self.assertIn("2. [ ] **File Integrity**", block)
        self.assertIn("3. [ ] **Entity Reconciliation**", block)
        self.assertIn("4. [ ] **Session Log & Wrap** [gate: wrap_before_stop]", block)
        self.assertIn("5. [ ] **Projections** [gate: projection_sync_before_stop]", block)
        self.assertNotIn("9. [ ] **Compaction**", block)

        # Eased escalation rule
        self.assertIn("Adaptive Complexity Escalation & Execution Mode Routing", block)
        self.assertIn("Direct execution with user alignment is permitted for focused tasks", block)

        # Eased plan approval rule
        self.assertIn("Session Binding & Plan Alignment", block)
        self.assertIn("Formal plan mode is recommended for complex architectural refactors", block)

        # State invariants still present
        self.assertIn("[gate: require-active-issue]", block)
        self.assertIn("[gate: test_before_stop]", block)
        self.assertIn("[gate: wrap_before_stop]", block)
        self.assertIn("[gate: workspace-containment]", block)

    def test_strict_profile_annotates_header(self):
        from alongkit.version import CURRENT_PROTOCOL_VERSION
        block = scaffold.render_protocol_block(self.raw_protocol, profile="strict")
        self.assertIn("<!-- BEGIN ALONG-PROTOCOL root profile=strict (managed by along-init - do not edit by hand) -->", block)
        self.assertIn(f"# ALONG-PROTOCOL v{CURRENT_PROTOCOL_VERSION} (profile: strict)", block)
        self.assertIn("9. [ ] **Compaction**", block)


class TestAlongInitProfileIntegration(unittest.TestCase):
    def setUp(self):
        self.root = make_repo_fixture(prefix="along-init-prof-", with_docs=False)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_scaffold_agents_md_respects_repo_config_profile(self):
        from along_init import scaffold_agents_md
        from alongkit import migration

        cfg_path = os.path.join(self.root, ".along", "config.json")
        textio.write_text(cfg_path, '{"profile": "light"}')

        raw_protocol = textio.read_text(PROTOCOL_PATH, strict=False)
        report = {"created": [], "updated": [], "untouched": []}
        mig = migration.Migration(self.root, dry_run=False, state_dir=os.path.join(self.root, ".along"))

        scaffold_agents_md(mig, self.root, raw_protocol, report)
        agents_content = textio.read_text(os.path.join(self.root, "AGENTS.md"))

        self.assertIn("profile=light", agents_content)
        self.assertIn("profile: light", agents_content)
        self.assertNotIn("9. [ ] **Compaction**", agents_content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
