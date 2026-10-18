#!/usr/bin/env python3
"""
tests/test_scaffold_profiles.py - Hermetic tests for protocol rendering per profile.

Covers [feat--gate-strictness-profiles] REQ-3, REQ-6 and [debt--agents-md-core-slimming]
REQ-1, REQ-2, REQ-4, REQ-5:
- Profile-scoped sections (`<!-- profile: light -->` / `<!-- profile: !light -->` ...
  `<!-- /profile -->`) are resolved for the active profile and the markers stripped.
- The AGENTS.md core and the on-demand reference (`docs/topic--along-protocol.md`) both
  render per profile: light eases plan approval and along-team escalation and compacts
  the completion checklist; strict and standard keep the full ceremony.
- No rule of the pre-slimming block is lost: every gate tag stays in the core and every
  named rule has its full wording in the reference.
- `along init` and `along update` write the reference, keep `## Project specifics` and
  honour the repository profile.
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
REFERENCE_PATH = os.path.join(REPO_ROOT, "skills", "along-init", "protocol-reference.md")

#: Gate tags of the managed block before [debt--agents-md-core-slimming]; the core keeps all.
PRE_SLIMMING_GATE_TAGS = (
    "subproject-boundary", "projection-protection", "untracked-exports", "require-active-issue",
    "require-plan-approval", "commit-issue-binding", "issue-lifecycle", "entity-reference-integrity",
    "entity-deletion-protection", "doc-manual-lock", "rule-pack-protection", "doc-routing-compliance",
    "test_before_stop", "wrap_before_stop", "projection_sync_before_stop", "workspace-containment",
    "cli_safety", "team-step-active", "team-reviews-before-stop",
)

#: Named rules of the pre-slimming block; each keeps its full wording in the reference.
PRE_SLIMMING_RULES = (
    "Nearest Context Boundary", "Subproject Localization", "Multi-Subproject Work", "Subproject Boundary",
    "Precedence", "Zero-Manual-Merge Rule", "Append-Only Merge Driver", "Untracked Exports",
    "Context Isolation", "Parallel Closeout", "No Code Without Issue", "Session Binding & Plan Approval",
    "Exemptions", "Commit Binding", "No AI Co-Authors", "Entity types", "Canonical keys", "ADRs",
    "Issue lifecycle", "Entity references", "Auto-entity creation", "Stable Entry Point", "Portable Links",
    "Fact Grounding", "Fast Retrieval", "Doc Blast Radius", "Manual Document Lock", "Managed Rule Packs",
    "Documentation Routing Tree", "Token hygiene", "Lifecycle hooks first", "Post-change review",
    "Stage & Session Completion Checklist", "Contract-First Lifecycle", "Environment Isolation",
    "Workspace Containment", "Runtimes Without Along Hooks", "File Modification & Anti-Deletion",
    "Clean ASCII", "Markdown", "Commit-time checks", "Bypass Is The User's Call", "File Content Via Tools Only",
    "No Ad-Hoc Shell Code Probing", "CLI Black-Box Invariance", "Verify Written Files", "Hermetic Tests",
    "Inquiry Read-Only Invariance (Zero-Mutation Rule on Questions)",
    "Mandatory Adaptive Complexity Escalation & Execution Mode Routing",
    "Windows-safe filenames", "Keep `ISSUES.md` compact", "Never write secrets into tracked files",
)


class TestProfileSections(unittest.TestCase):
    TEXT = (
        "a\n"
        "<!-- profile: light -->\n"
        "light only\n"
        "<!-- /profile -->\n"
        "<!-- profile: !light -->\n"
        "not light\n"
        "<!-- /profile -->\n"
        "<!-- profile: strict, light -->\n"
        "strict or light\n"
        "<!-- /profile -->\n"
        "z\n"
    )

    def test_standard_keeps_negated_sections_only(self):
        self.assertEqual(scaffold.render_profile_sections(self.TEXT, "standard"), "a\nnot light\nz\n")

    def test_light_keeps_named_sections(self):
        self.assertEqual(scaffold.render_profile_sections(self.TEXT, "light"), "a\nlight only\nstrict or light\nz\n")

    def test_strict_matches_a_list(self):
        self.assertEqual(scaffold.render_profile_sections(self.TEXT, "strict"), "a\nnot light\nstrict or light\nz\n")

    def test_none_means_standard(self):
        self.assertEqual(scaffold.render_profile_sections(self.TEXT, None),
                         scaffold.render_profile_sections(self.TEXT, "standard"))


class TestScaffoldProtocolBlockProfiles(unittest.TestCase):
    def setUp(self):
        self.raw_protocol = textio.read_text(PROTOCOL_PATH, strict=False)
        self.raw_reference = textio.read_text(REFERENCE_PATH, strict=False)

    def test_no_marker_leaks_into_any_rendering(self):
        for profile in ("strict", "standard", "light"):
            block = scaffold.render_protocol_block(self.raw_protocol, profile=profile)
            reference = scaffold.render_protocol_reference(self.raw_reference, profile)
            for text in (block, reference):
                self.assertNotIn("<!-- profile", text)
                self.assertNotIn("<!-- /profile", text)

    def test_standard_profile_core(self):
        block = scaffold.render_protocol_block(self.raw_protocol, profile="standard")
        self.assertIn("<!-- BEGIN ALONG-PROTOCOL root (managed by along-init - do not edit by hand) -->", block)
        self.assertIn("docs/topic--along-protocol.md", block)
        self.assertIn("Source edits unlock after the user approves the plan", block)
        self.assertIn("route to `along-team`; plans MUST declare", block)
        self.assertNotIn("Align the plan with the user", block)

    def test_core_keeps_every_gate_tag(self):
        block = scaffold.render_protocol_block(self.raw_protocol, profile="standard")
        for tag in PRE_SLIMMING_GATE_TAGS:
            self.assertIn(f"[gate: {tag}]", block, f"gate {tag} lost from the AGENTS.md core")

    def test_reference_keeps_every_rule(self):
        reference = scaffold.render_protocol_reference(self.raw_reference, "standard")
        self.assertTrue(scaffold.is_managed_reference(reference))
        for rule in PRE_SLIMMING_RULES:
            self.assertIn(rule, reference, f"rule '{rule}' has no destination in the protocol reference")
        self.assertIn("9. [ ] **Compaction**", reference)

    def test_light_profile_core_and_reference(self):
        from alongkit.version import CURRENT_PROTOCOL_VERSION
        block = scaffold.render_protocol_block(self.raw_protocol, profile="light")
        self.assertIn("<!-- BEGIN ALONG-PROTOCOL root profile=light (managed by along-init - do not edit by hand) -->", block)
        self.assertIn(f"# ALONG-PROTOCOL v{CURRENT_PROTOCOL_VERSION} (profile: light)", block)
        self.assertIn("Align the plan with the user", block)
        self.assertNotIn("Source edits unlock after the user approves the plan", block)
        self.assertIn("direct execution with user alignment is permitted", block)
        for tag in ("require-active-issue", "test_before_stop", "wrap_before_stop", "workspace-containment"):
            self.assertIn(f"[gate: {tag}]", block)

        reference = scaffold.render_protocol_reference(self.raw_reference, "light")
        self.assertIn("5. [ ] **Projections** [gate: projection_sync_before_stop]", reference)
        self.assertNotIn("9. [ ] **Compaction**", reference)
        self.assertIn("Session Binding & Plan Alignment", reference)
        self.assertIn("Adaptive Complexity Escalation & Execution Mode Routing", reference)
        self.assertNotIn("Mandatory Adaptive Complexity Escalation", reference)

    def test_strict_profile_annotates_header(self):
        from alongkit.version import CURRENT_PROTOCOL_VERSION
        block = scaffold.render_protocol_block(self.raw_protocol, profile="strict")
        self.assertIn("<!-- BEGIN ALONG-PROTOCOL root profile=strict (managed by along-init - do not edit by hand) -->", block)
        self.assertIn(f"# ALONG-PROTOCOL v{CURRENT_PROTOCOL_VERSION} (profile: strict)", block)
        reference = scaffold.render_protocol_reference(self.raw_reference, "strict")
        self.assertIn("9. [ ] **Compaction**", reference)


class TestReferenceAction(unittest.TestCase):
    def test_actions(self):
        rendered = scaffold.render_protocol_reference(textio.read_text(REFERENCE_PATH, strict=False))
        self.assertEqual(scaffold.reference_action(None, rendered), "create")
        self.assertEqual(scaffold.reference_action(rendered, rendered), "untouched")
        self.assertEqual(scaffold.reference_action(rendered.replace("Along Protocol Reference", "Old"), rendered), "update")
        self.assertEqual(scaffold.reference_action("# My own article\n", rendered), "foreign")


class TestAlongInitProfileIntegration(unittest.TestCase):
    def setUp(self):
        self.root = make_repo_fixture(prefix="along-init-prof-", with_docs=False)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _init(self):
        from along_init import scaffold_agents_md, scaffold_protocol_reference
        from alongkit import migration

        report = {"created": [], "updated": [], "untouched": []}
        mig = migration.Migration(self.root, dry_run=False, state_dir=os.path.join(self.root, ".along"))
        scaffold_agents_md(mig, self.root, textio.read_text(PROTOCOL_PATH, strict=False), report)
        scaffold_protocol_reference(mig, self.root, textio.read_text(REFERENCE_PATH, strict=False), report)
        return report

    def test_scaffold_respects_repo_config_profile(self):
        textio.write_text(os.path.join(self.root, ".along", "config.json"), '{"profile": "light"}')
        self._init()
        agents_content = textio.read_text(os.path.join(self.root, "AGENTS.md"))
        self.assertIn("profile=light", agents_content)
        self.assertIn("profile: light", agents_content)
        self.assertIn("Align the plan with the user", agents_content)

        reference = textio.read_text(os.path.join(self.root, *scaffold.REFERENCE_DOC_RELPATH))
        self.assertNotIn("9. [ ] **Compaction**", reference)

    def test_foreign_reference_is_left_alone(self):
        path = os.path.join(self.root, *scaffold.REFERENCE_DOC_RELPATH)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        textio.write_text(path, "# Hand-written\n")
        report = self._init()
        self.assertEqual(textio.read_text(path), "# Hand-written\n")
        self.assertTrue(report.get("warnings"))


class TestAlongUpdateRefresh(unittest.TestCase):
    """REQ-5: `along update` keeps Project specifics, writes the reference, keeps the profile."""

    def setUp(self):
        self.root = make_repo_fixture(prefix="along-update-ref-", with_docs=False)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_update_preserves_specifics_and_writes_reference(self):
        import along_update

        textio.write_text(os.path.join(self.root, ".along", "config.json"), '{"profile": "light"}')
        old_block = (
            "<!-- BEGIN ALONG-PROTOCOL root (managed by along-init - do not edit by hand) -->\n"
            "# ALONG-PROTOCOL v0.0.1\nOld long protocol text.\n<!-- END ALONG-PROTOCOL -->\n"
        )
        specifics = "## Project specifics\n\n- Build with `make all`; keep this line.\n"
        textio.write_text(os.path.join(self.root, "AGENTS.md"), old_block + "\n" + specifics)

        ok = along_update.apply_migration_to_context(
            ctx_dir=self.root,
            protocol_text=textio.read_text(PROTOCOL_PATH, strict=False).strip(),
            migrate_script=None,
            reference_text=textio.read_text(REFERENCE_PATH, strict=False),
        )
        self.assertTrue(ok)
        agents = textio.read_text(os.path.join(self.root, "AGENTS.md"))
        self.assertIn("- Build with `make all`; keep this line.", agents)
        self.assertNotIn("Old long protocol text.", agents)
        self.assertIn("profile=light", agents)

        reference_path = os.path.join(self.root, *scaffold.REFERENCE_DOC_RELPATH)
        reference = textio.read_text(reference_path)
        self.assertTrue(scaffold.is_managed_reference(reference))
        self.assertNotIn("9. [ ] **Compaction**", reference)


if __name__ == "__main__":
    unittest.main(verbosity=2)
