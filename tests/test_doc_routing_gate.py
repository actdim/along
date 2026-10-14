#!/usr/bin/env python3
"""
tests/test_doc_routing_gate.py - Hermetic tests for Documentation Routing Tree Gate.

Covers [feat--doc-routing-compliance-gate]:
- Core repocheck: deep code fences (>50 lines) and convention bloat (>50 lines) in README.md.
- Core repocheck: AGENTS.md referencing README.md for conventions instead of docs/.
- Pragma exemption: along: allow-doc-routing-compliance.
- Runtime predicate: check_doc_routing_compliance on file mutations (write_to_file, replace_file_content).
- Git pre-commit and CI enforcement via gitgates.
- Declarative gate catalogue registration.
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

from alongkit import gitgates, repochecks, textio
from alongkit.hooks import HookEvent, HookEventType
from alongkit.hooks import declarative, predicates

FENCE = "`" * 3


def _dr_reader(files):
    return lambda path: files.get(path)


def _dr_run(paths, files, options=None):
    return repochecks.check_doc_routing_compliance(paths, _dr_reader(files), options or {})


def _git_cmd(cwd, *args):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )


def _write_doc_routing_file(root, rel, text):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


class TestDocRoutingComplianceCore(unittest.TestCase):
    """Hermetic unit tests for repochecks.check_doc_routing_compliance."""

    def test_compliant_readme_and_agents_pass(self):
        readme_text = "\n".join([
            "# My Cool Project",
            "",
            "This is a high-level overview of the library.",
            "",
            f"{FENCE}bash",
            "pnpm install",
            "pnpm run dev",
            FENCE,
            "",
            "## Documentation",
            "See [Architecture](./docs/topic--architecture.md) for details.",
        ])
        agents_text = "\n".join([
            "# Agent Context",
            "",
            "Follow conventions documented in [Coding Conventions](docs/topic--frontend-conventions.md).",
            "Route public overviews to README.md and technical rules to docs/.",
        ])
        files = {
            "README.md": readme_text,
            "AGENTS.md": agents_text,
        }
        findings = _dr_run(["README.md", "AGENTS.md"], files)
        self.assertEqual(findings, [])

    def test_deep_code_fence_in_readme_is_flagged(self):
        # 60 lines inside a code fence
        code_lines = [f"const rule_{i} = 'spec_{i}';" for i in range(60)]
        readme_text = "\n".join([
            "# Overview",
            "",
            f"{FENCE}typescript",
            *code_lines,
            FENCE,
        ])
        files = {"README.md": readme_text}
        findings = _dr_run(["README.md"], files)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0][0], "README.md:3")
        self.assertIn("code fence in README.md exceeds 50 lines", findings[0][1])

    def test_bloated_conventions_section_in_readme_is_flagged(self):
        # Heading matching conventions with 60 lines of text
        rule_lines = [f"- Rule {i}: Component must adhere to invariant {i}." for i in range(60)]
        readme_text = "\n".join([
            "# Service Overview",
            "",
            "## Mandatory Architectural Rules & Invariants",
            *rule_lines,
            "",
            "## License",
            "MIT",
        ])
        files = {"packages/dashboard-ui/README.md": readme_text}
        findings = _dr_run(["packages/dashboard-ui/README.md"], files)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0][0], "packages/dashboard-ui/README.md:3")
        self.assertIn("section 'Mandatory Architectural Rules & Invariants' in README.md exceeds 50 lines", findings[0][1])

    def test_overall_bloated_readme_with_tech_sections_is_flagged(self):
        # 310 lines with a technical conventions section
        lines = ["# Large Overview", "", "## Coding Standards", "Brief intro."]
        for i in range(310):
            lines.append(f"Line {i} describing architectural context.")
        readme_text = "\n".join(lines)
        files = {"README.md": readme_text}
        findings = _dr_run(["README.md"], files)
        self.assertTrue(any(f[0] == "README.md:1" and "exceeds 300 lines" in f[1] for f in findings))

    def test_agents_referencing_readme_for_conventions_is_flagged(self):
        agents_text = "\n".join([
            "# Subproject Agent Context",
            "",
            "Follow all architectural rules documented in [Frontend Conventions](README.md).",
        ])
        files = {"packages/dashboard-ui/AGENTS.md": agents_text}
        findings = _dr_run(["packages/dashboard-ui/AGENTS.md"], files)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0][0], "packages/dashboard-ui/AGENTS.md:3")
        self.assertIn("references README.md for conventions or architecture rules", findings[0][1])

    def test_agents_referencing_readme_for_facts_passes(self):
        agents_text = "\n".join([
            "# Agent Guidelines",
            "",
            "- **Fact Grounding**: Agents MUST extract facts from actual code, README.md, docs/, and package.json.",
            "- Public overview / pitch / landing page -> README.md",
        ])
        files = {"AGENTS.md": agents_text}
        findings = _dr_run(["AGENTS.md"], files)
        self.assertEqual(findings, [])

    def test_pragma_allows_exemption(self):
        # Deep code fence with pragma exemption
        code_lines = [f"const test_{i} = {i};" for i in range(60)]
        readme_text = "\n".join([
            "<!-- along: allow-doc-routing-compliance -->",
            "# Test Fixture",
            "",
            f"{FENCE}typescript",
            *code_lines,
            FENCE,
        ])
        agents_text = "\n".join([
            "# Agent Context",
            "See [Conventions](README.md) <!-- along: allow-doc-routing-compliance -->",
        ])
        files = {
            "README.md": readme_text,
            "AGENTS.md": agents_text,
        }
        findings = _dr_run(["README.md", "AGENTS.md"], files)
        self.assertEqual(findings, [])


class TestDocRoutingRuntimePredicate(unittest.TestCase):
    """Hermetic unit tests for predicates.check_doc_routing_compliance."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along-doc-routing-")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_clean_write_to_readme_passes(self):
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={
                "TargetFile": os.path.join(self.root, "README.md"),
                "CodeContent": "# My Project\n\nHigh level overview.\n",
            },
            workspace_root=self.root,
        )
        res = predicates.check_doc_routing_compliance(event, repo_root=self.root)
        self.assertIsNone(res)

    def test_bloated_write_to_readme_is_denied(self):
        code_lines = [f"console.log({i});" for i in range(60)]
        bloated = "\n".join(["# Readme", "", f"{FENCE}javascript", *code_lines, FENCE])
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={
                "TargetFile": os.path.join(self.root, "README.md"),
                "CodeContent": bloated,
            },
            workspace_root=self.root,
        )
        res = predicates.check_doc_routing_compliance(event, repo_root=self.root)
        self.assertIsNotNone(res)
        self.assertIn("[gate: doc-routing-compliance]", res)
        self.assertIn("code fence in README.md exceeds 50 lines", res)

    def test_replace_file_content_on_readme_is_evaluated(self):
        initial = "# Project\n\n## Overview\nShort description.\n"
        readme_path = os.path.join(self.root, "README.md")
        textio.write_text(readme_path, initial)

        bloated_replacement = "\n".join([
            "## Architecture & Conventions",
            *[f"Rule {i}: Specification line." for i in range(60)],
        ])
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="replace_file_content",
            tool_args={
                "TargetFile": readme_path,
                "TargetContent": "## Overview\nShort description.",
                "ReplacementContent": bloated_replacement,
            },
            workspace_root=self.root,
        )
        res = predicates.check_doc_routing_compliance(event, repo_root=self.root)
        self.assertIsNotNone(res)
        self.assertIn("[gate: doc-routing-compliance]", res)
        self.assertIn("section 'Architecture & Conventions' in README.md exceeds 50 lines", res)

    def test_write_to_unrelated_file_is_ignored(self):
        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={
                "TargetFile": os.path.join(self.root, "src", "engine.py"),
                "CodeContent": "# 100 lines of code...\n" * 100,
            },
            workspace_root=self.root,
        )
        res = predicates.check_doc_routing_compliance(event, repo_root=self.root)
        self.assertIsNone(res)


class TestDocRoutingDeclarativeGate(unittest.TestCase):
    """Tests catalogue definition and profiles for doc_routing_compliance."""

    def test_catalogue_contains_doc_routing_compliance(self):
        gates = declarative.get_all_declarative_gates(repo_root=REPO_ROOT)
        gate_names = [g.name for g in gates]
        self.assertIn("doc_routing_compliance", gate_names)

        target = next(g for g in gates if g.name == "doc_routing_compliance")
        self.assertEqual(target.defn.event_type, HookEventType.PRE_TOOL_USE)
        self.assertIn("write_to_file", target.defn.tools)
        self.assertIn("replace_file_content", target.defn.tools)
        self.assertEqual(target.defn.profiles.get("strict"), "block")
        self.assertEqual(target.defn.profiles.get("standard"), "block")
        self.assertEqual(target.defn.profiles.get("light"), "warn")
        self.assertEqual(sorted(target.defn.enforcement), ["ci", "git", "runtime"])


class TestDocRoutingThroughGit(unittest.TestCase):
    """Tests git pre-commit and CI enforcement via throwaway Git repositories."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="along_git_doc_routing_")
        _git_cmd(self.root, "init", "-q")
        _git_cmd(self.root, "config", "user.email", "t@example.com")
        _git_cmd(self.root, "config", "user.name", "t")
        _git_cmd(self.root, "config", "core.autocrlf", "false")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_pre_commit_blocks_staged_bloated_readme(self):
        code_lines = [f"line_{i} = {i}" for i in range(60)]
        bloated = "\n".join(["# Readme", "", f"{FENCE}python", *code_lines, FENCE])
        _write_doc_routing_file(self.root, "README.md", bloated)
        _git_cmd(self.root, "add", "README.md")

        violations = gitgates.check_pre_commit(self.root)
        routing_violations = [v for v in violations if v.gate == "doc_routing_compliance"]
        self.assertGreaterEqual(len(routing_violations), 1)
        self.assertIn("README.md:3", routing_violations[0].location)
        self.assertIn("code fence in README.md exceeds 50 lines", routing_violations[0].message)

    def test_ci_detects_tracked_agents_reference_to_readme(self):
        _write_doc_routing_file(self.root, "README.md", "# Clean Overview\n")
        _write_doc_routing_file(self.root, "AGENTS.md", "See [Conventions](README.md) for rules.\n")
        _git_cmd(self.root, "add", "-A")
        _git_cmd(self.root, "commit", "-q", "--no-verify", "-m", "init")

        violations = gitgates.check_ci(self.root, commit_range=None, links=False)
        routing_violations = [v for v in violations if v.gate == "doc_routing_compliance"]
        self.assertEqual(len(routing_violations), 1)
        self.assertIn("AGENTS.md:1", routing_violations[0].location)
        self.assertIn("references README.md for conventions", routing_violations[0].message)


if __name__ == "__main__":
    unittest.main()
