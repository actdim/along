#!/usr/bin/env python3
"""tests/test_docs.py - Structural and contract tests for documentation and protocol guidance."""

import ast
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import along_exec
from alongkit import frontmatter, markdown, repochecks, textio
from alongkit.hooks.declarative import DEFAULT_GATES_FILE, load_gate_entries
from alongkit.hooks.traceability import GATE_BADGE_PATTERN


def _known_along_commands() -> set[str]:
    """Derive the canonical set of `along` CLI subcommands from scripts/along_exec.py."""
    cmds = set(along_exec.TOOL_MAPPINGS.keys()) | set(along_exec.LIFECYCLE_ACTIONS) | {"kb", "graph"}
    exec_path = os.path.join(SCRIPTS_DIR, "along_exec.py")
    tree = ast.parse(textio.read_text(exec_path), filename=exec_path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "native_routers" and isinstance(node.value, ast.Dict):
                    for key in node.value.keys:
                        if isinstance(key, ast.Constant) and isinstance(key.value, str):
                            cmds.add(key.value)
    return cmds


def _known_gate_ids() -> set[str]:
    """Load canonical gate identifiers from default_gates.yaml (hyphen and underscore forms)."""
    ids: set[str] = set()
    for defn, _raw in load_gate_entries(DEFAULT_GATES_FILE):
        ids.add(defn.id)
        ids.add(defn.id.replace("_", "-"))
    return ids


def _extract_section(content: str, heading_anchor: str) -> str:
    """Return the Markdown body under the heading matching `heading_anchor`."""
    heading_re = re.compile(r"^ {0,3}(#{1,6})\s+(.+?)\s*$")
    lines = content.splitlines()
    tracker = markdown.FenceTracker()
    capturing = False
    target_level = 0
    captured: list[str] = []

    for line in lines:
        is_boundary = tracker.process_line(line)
        if is_boundary or tracker.in_fence:
            if capturing:
                captured.append(line)
            continue

        m = heading_re.match(line)
        if m:
            level = len(m.group(1))
            title = re.sub(r"\s+#+\s*$", "", m.group(2).strip())
            slug = markdown.github_heading_anchor(title)
            if capturing:
                if level <= target_level:
                    break
                captured.append(line)
            elif slug == heading_anchor:
                capturing = True
                target_level = level
        elif capturing:
            captured.append(line)

    return "\n".join(captured)


class TestDocumentationRules(unittest.TestCase):
    # Full rule wording moved from the AGENTS.md core to the on-demand protocol reference
    # (source and .along/ projection) in [debt--agents-md-core-slimming].
    REFERENCE_PATHS = (
        os.path.join(REPO_ROOT, "skills", "along-init", "protocol-reference.md"),
        os.path.join(REPO_ROOT, ".along", "PROTOCOL.md"),
    )
    CORE_PATHS = (
        os.path.join(REPO_ROOT, "AGENTS.md"),
        os.path.join(REPO_ROOT, "skills", "along-init", "protocol.md"),
    )

    @classmethod
    def setUpClass(cls):
        cls.known_commands = _known_along_commands()
        cls.known_gates = _known_gate_ids()

    def _assert_closed_and_labeled_fences(self, path: str, content: str) -> None:
        """Verify every fenced block has a language tag and is properly closed."""
        tracker = markdown.FenceTracker()
        for line in content.splitlines():
            tracker.process_line(line)
        rel = os.path.relpath(path, REPO_ROOT).replace("\\", "/")
        self.assertFalse(tracker.in_fence, f"{rel}: unclosed Markdown code fence")

        fence_findings = repochecks.check_code_fence_language([rel], lambda _p: content, {})
        self.assertEqual(fence_findings, [], f"{rel}: unlabeled code fence(s): {fence_findings}")

    def _assert_valid_relative_links(
        self, path: str, content: str, *, enforce_stable_entry_point: bool = True
    ) -> None:
        """Verify all relative Markdown links resolve on disk without forbidden schemes."""
        rel = os.path.relpath(path, REPO_ROOT).replace("\\", "/")
        if enforce_stable_entry_point:
            broken = markdown.find_broken_links(content, path, REPO_ROOT)
            self.assertEqual(broken, [], f"{rel}: broken or non-compliant Markdown links: {broken}")
            return

        for link in markdown.find_links(content, skip_external=True):
            target = link.target.strip()
            self.assertFalse(
                target.lower().startswith("file://"),
                f"{rel}:{link.line}: forbidden file:// link '{target}'",
            )
            self.assertNotIn("\\", target, f"{rel}:{link.line}: backslash in link '{target}'")
            if markdown.is_placeholder(target):
                continue
            resolved = markdown.resolve_target(target, path, REPO_ROOT)
            self.assertIsNotNone(resolved, f"{rel}:{link.line}: unresolvable link '{target}'")
            self.assertTrue(
                os.path.exists(resolved),
                f"{rel}:{link.line}: relative link target missing on disk: '{target}' -> {resolved}",
            )

    def _assert_valid_cli_commands(self, path: str, text: str) -> list[str]:
        """Verify backticked and shell-fenced `along <subcommand>` references map to along_exec."""
        rel = os.path.relpath(path, REPO_ROOT).replace("\\", "/")
        found = re.findall(r"`along\s+([a-z][a-z0-9-]*[a-z0-9])(?=[\s`])", text)
        shell_langs = {"bash", "sh", "shell", "zsh", "powershell", "pwsh", "console"}
        tracker = markdown.FenceTracker()
        active_lang = ""
        for line in text.splitlines():
            was_in_fence = tracker.in_fence
            is_boundary = tracker.process_line(line)
            if is_boundary:
                if not was_in_fence and tracker.in_fence:
                    m = re.match(r"^ {0,3}(?:`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
                    active_lang = (m.group(1).strip().split()[0].lower() if m and m.group(1).strip() else "")
                else:
                    active_lang = ""
                continue
            if tracker.in_fence and active_lang in shell_langs:
                cm = re.match(r"^\s*(?:\$\s+)?along\s+([a-z][a-z0-9-]*[a-z0-9])(?=\s|$)", line)
                if cm:
                    found.append(cm.group(1))
        unknown = [cmd for cmd in found if cmd not in self.known_commands]
        self.assertEqual(
            unknown,
            [],
            f"{rel}: documents unknown `along` CLI subcommand(s): {unknown}",
        )
        return found

    def _assert_gate_badges_exist(self, path: str, text: str) -> set[str]:
        """Verify all `[gate: <id>]` badges resolve to real gate definitions."""
        rel = os.path.relpath(path, REPO_ROOT).replace("\\", "/")
        badges = {m.group(1) or m.group(2) for m in GATE_BADGE_PATTERN.finditer(text)}
        unknown = [gid for gid in sorted(badges) if gid not in self.known_gates]
        self.assertEqual(unknown, [], f"{rel}: references unknown gate id(s): {unknown}")
        return badges

    def _assert_frontmatter_schema(
        self, path: str, content: str, required_keys: set[str], expected: dict | None = None
    ) -> tuple[dict, str]:
        """Strictly parse YAML frontmatter and assert schema fields and non-empty body."""
        rel = os.path.relpath(path, REPO_ROOT).replace("\\", "/")
        self.assertTrue(frontmatter.has_frontmatter(content), f"{rel}: missing YAML frontmatter block")
        self.assertEqual(frontmatter.lint(content, path=path), [], f"{rel}: frontmatter failed YAML lint")
        fm, body = frontmatter.parse(content, path=path)
        missing = sorted(required_keys - set(fm.keys()))
        self.assertEqual(missing, [], f"{rel}: missing required frontmatter keys: {missing}")
        if expected:
            for key, value in expected.items():
                self.assertEqual(fm.get(key), value, f"{rel}: frontmatter '{key}' mismatch")
        self.assertTrue(body.strip(), f"{rel}: Markdown body must not be empty")
        return fm, body

    def test_agents_md_prohibits_shell_code_probing(self):
        """Protocol reference and core must structurally define cli_safety and prohibit python -c probing."""
        for path in self.REFERENCE_PATHS:
            content = textio.read_text(path)
            fm, body = self._assert_frontmatter_schema(
                path,
                content,
                {"protocol", "slug", "title", "type", "write_policy", "tags", "created"},
                {"protocol": "along", "slug": "along-protocol", "type": "reference", "write_policy": "manual"},
            )
            self.assertIsInstance(fm["tags"], list)
            self.assertGreater(len(fm["tags"]), 0)
            self._assert_closed_and_labeled_fences(path, content)
            self._assert_valid_relative_links(path, content, enforce_stable_entry_point=True)

            anchors = markdown.extract_heading_anchors(body)
            self.assertTrue(
                {"tool-use-rules", "issue-anchoring-commits", "entity-ecosystem"}.issubset(anchors),
                f"{path}: missing required protocol-reference heading anchors in {sorted(anchors)}",
            )

            tool_rules = _extract_section(body, "tool-use-rules")
            self.assertTrue(tool_rules.strip(), f"{path}: Tool-Use Rules section must be non-empty")
            badges = self._assert_gate_badges_exist(path, tool_rules)
            self.assertIn("cli_safety", badges, f"{path}: Tool-Use Rules must carry [gate: cli_safety]")
            self.assertRegex(tool_rules, r"`python\s+-c`")
            self.assertRegex(tool_rules, r"`alongkit`")
            self.assertTrue(os.path.isdir(os.path.join(REPO_ROOT, "scripts", "alongkit")))
            self.assertRegex(tool_rules, r"`along\s+graph-\*`")

        for path in self.CORE_PATHS:
            content = textio.read_text(path)
            self._assert_closed_and_labeled_fences(path, content)
            self._assert_valid_relative_links(
                path,
                content,
                enforce_stable_entry_point=(os.path.basename(path) != "AGENTS.md"),
            )
            anchors = markdown.extract_heading_anchors(content)
            self.assertTrue(
                {"where-state-lives", "anchor-work-to-an-issue", "gates", "judgment-rules"}.issubset(anchors),
                f"{path}: missing core protocol headings in {sorted(anchors)}",
            )
            gates_section = _extract_section(content, "gates")
            badges = self._assert_gate_badges_exist(path, gates_section)
            self.assertIn("cli_safety", badges)
            self.assertRegex(gates_section, r"`python\s+-c`")

    def test_agents_md_prohibits_cli_reverse_engineering(self):
        """Protocol reference and core must structurally require CLI contract usage over engine probing."""
        for path in self.REFERENCE_PATHS:
            content = textio.read_text(path)
            tool_rules = _extract_section(content, "tool-use-rules")
            self._assert_gate_badges_exist(path, tool_rules)
            self.assertRegex(tool_rules, r"`along\s+<command>\s+--help`")
            self.assertRegex(tool_rules, r"`alongkit/\*\*`")
            self.assertRegex(tool_rules, r"`docs/`")
            self.assertTrue(os.path.isdir(os.path.join(REPO_ROOT, "docs")))

        for path in self.CORE_PATHS:
            content = textio.read_text(path)
            judgment_section = _extract_section(content, "judgment-rules")
            self.assertTrue(judgment_section.strip(), f"{path}: Judgment rules section must be non-empty")
            self.assertRegex(judgment_section, r"`along\s+<cmd>\s+--help`")
            cmds = self._assert_valid_cli_commands(path, content)
            for required in ("start", "wrap", "graph-impact"):
                self.assertIn(required, cmds, f"{path}: must reference canonical `along {required}` command")

    def test_along_team_skill_documents_anti_pattern(self):
        """skills/along-team/SKILL.md must pass frontmatter/link/fence validation and document probing rules."""
        skill_path = os.path.join(REPO_ROOT, "skills", "along-team", "SKILL.md")
        content = textio.read_text(skill_path)

        fm, body = self._assert_frontmatter_schema(
            skill_path,
            content,
            {"name", "description"},
            {"name": "along-team"},
        )
        self.assertIsInstance(fm["description"], str)
        self.assertGreater(len(fm["description"].strip()), 10)
        self._assert_closed_and_labeled_fences(skill_path, content)
        self._assert_valid_relative_links(skill_path, content, enforce_stable_entry_point=True)

        anchors = markdown.extract_heading_anchors(body)
        required_anchors = {
            "provider-capability-abstraction-primitive-mapping",
            "single-agent-degradation-path-ralph-style-execution",
            "isolated-workspace-contract",
            "conditional-observable-reviewer-rubric",
            "mandatory-execution-protocol-step-by-step",
            "prohibited-anti-patterns-ad-hoc-shell-code-probing",
            "why-this-is-prohibited",
            "prescribed-inspection-workflows",
        }
        self.assertTrue(
            required_anchors.issubset(anchors),
            f"skills/along-team/SKILL.md missing required headings: {sorted(required_anchors - anchors)}",
        )

        anti_section = _extract_section(body, "prohibited-anti-patterns-ad-hoc-shell-code-probing")
        self.assertRegex(anti_section, r"`python\s+-c`")
        self.assertRegex(anti_section, r"`alongkit`")
        self.assertRegex(anti_section, r"`scripts`")
        cmds = self._assert_valid_cli_commands(skill_path, anti_section)
        for required_cmd in ("graph-impact", "graph-arch", "graph-sync"):
            self.assertIn(required_cmd, cmds, f"along-team anti-pattern section must reference `along {required_cmd}`")
        self.assertTrue(os.path.isfile(os.path.join(REPO_ROOT, ".along", "scripts", "test.py")))

    def test_troubleshooting_guide_exists_and_explains_packaging(self):
        """docs/topic--troubleshooting.md must pass schema/link/fence checks and reference real scripts/CLIs."""
        guide_path = os.path.join(REPO_ROOT, "docs", "topic--troubleshooting.md")
        self.assertTrue(os.path.isfile(guide_path), "docs/topic--troubleshooting.md must exist")

        content = textio.read_text(guide_path)
        fm, body = self._assert_frontmatter_schema(
            guide_path,
            content,
            {"protocol", "slug", "title", "type", "created", "updated", "tags"},
            {"protocol": "along", "slug": "troubleshooting", "type": "guide"},
        )
        self.assertIsInstance(fm["tags"], list)
        self.assertGreater(len(fm["tags"]), 0)
        self.assertRegex(str(fm["created"]), frontmatter.ISO_DATE_RE)
        self.assertRegex(str(fm["updated"]), frontmatter.ISO_DATE_RE)

        self._assert_closed_and_labeled_fences(guide_path, content)
        self._assert_valid_relative_links(guide_path, content, enforce_stable_entry_point=True)

        anchors = markdown.extract_heading_anchors(body)
        required_anchors = {
            "1-internal-packaging-architecture",
            "2-the-anti-pattern-ad-hoc-shell-code-probing",
            "why-exploratory-python--c-fails",
            "cli-black-box-invariance",
            "3-recommended-workflows-for-api-discovery",
            "4-diagnostics-health-verification",
            "5-related-topics",
        }
        self.assertTrue(
            required_anchors.issubset(anchors),
            f"docs/topic--troubleshooting.md missing required headings: {sorted(required_anchors - anchors)}",
        )

        # Verify referenced codebase paths actually exist on disk
        packaging_section = _extract_section(body, "1-internal-packaging-architecture")
        referenced_repo_paths = (
            "scripts/alongkit",
            "scripts/alongkit/bootstrap.py",
            "scripts/along_commit.py",
            "scripts/along_kb_sync.py",
            "scripts/along_exec.py",
            ".along/scripts/test.py",
        )
        for rel in referenced_repo_paths:
            self.assertIn(rel, packaging_section, f"Packaging section must reference '{rel}'")
            self.assertTrue(
                os.path.exists(os.path.join(REPO_ROOT, rel)),
                f"Troubleshooting guide references missing repo path: {rel}",
            )

        # Verify PEP 723 metadata block is present inside a python code fence
        self.assertRegex(
            packaging_section,
            re.compile(
                r"```python\s+# /// script\s+# requires-python = .*?# dependencies = \[.*?ruamel\.yaml.*?\]\s+# ///",
                re.DOTALL,
            ),
        )
        self.assertRegex(packaging_section, r"`uv`")

        # Verify documented CLI commands resolve in along_exec
        cmds = self._assert_valid_cli_commands(guide_path, body)
        for required_cmd in ("doctor", "feedback", "gates", "lint", "graph-impact"):
            self.assertIn(required_cmd, cmds, f"Troubleshooting guide must document `along {required_cmd}`")

    def test_troubleshooting_registered_in_index(self):
        """docs/INDEX.md must pass schema/link/fence checks and link topic--troubleshooting.md."""
        index_path = os.path.join(REPO_ROOT, "docs", "INDEX.md")
        content = textio.read_text(index_path)

        fm, body = self._assert_frontmatter_schema(
            index_path,
            content,
            {"protocol", "slug", "title", "type", "created", "updated", "tags"},
            {"protocol": "along", "slug": "INDEX", "type": "index"},
        )
        self.assertIsInstance(fm["tags"], list)
        self._assert_closed_and_labeled_fences(index_path, content)
        self._assert_valid_relative_links(index_path, content, enforce_stable_entry_point=True)

        anchors = markdown.extract_heading_anchors(body)
        self.assertTrue({"knowledge-graph-topic-map", "articles", "related-context"}.issubset(anchors))

        expected_target = os.path.normpath(os.path.join(REPO_ROOT, "docs", "topic--troubleshooting.md"))
        resolved_targets = {
            os.path.normpath(resolved)
            for link in markdown.find_links(body, skip_external=True)
            for resolved in (markdown.resolve_target(link.target, index_path, REPO_ROOT),)
            if resolved is not None
        }
        self.assertIn(
            expected_target,
            resolved_targets,
            "docs/INDEX.md must contain a resolved Markdown link to docs/topic--troubleshooting.md",
        )

    def test_along_protocol_not_leaked_into_index_or_docs(self):
        """Internal agent protocol must not be scaffolded in docs/ or linked in docs/INDEX.md or llms.txt."""
        legacy_path = os.path.normpath(os.path.join(REPO_ROOT, "docs", "topic--along-protocol.md"))
        self.assertFalse(os.path.exists(legacy_path), "docs/topic--along-protocol.md must not exist")

        index_path = os.path.join(REPO_ROOT, "docs", "INDEX.md")
        index_content = textio.read_text(index_path)
        self._assert_valid_relative_links(index_path, index_content, enforce_stable_entry_point=True)
        index_targets = {
            os.path.normpath(resolved)
            for link in markdown.find_links(index_content, skip_external=True)
            for resolved in (markdown.resolve_target(link.target, index_path, REPO_ROOT),)
            if resolved is not None
        }
        self.assertNotIn(legacy_path, index_targets, "docs/INDEX.md must not link to topic--along-protocol.md")
        self.assertNotIn("T_ALONG_PROTOCOL", index_content)
        self.assertNotIn("topic--along-protocol.md", index_content)

        llms_path = os.path.join(REPO_ROOT, "llms.txt")
        self.assertTrue(os.path.isfile(llms_path), "llms.txt must exist")
        llms_content = textio.read_text(llms_path)
        self._assert_closed_and_labeled_fences(llms_path, llms_content)
        self._assert_valid_relative_links(llms_path, llms_content, enforce_stable_entry_point=True)
        llms_targets = {
            os.path.normpath(resolved)
            for link in markdown.find_links(llms_content, skip_external=True)
            for resolved in (markdown.resolve_target(link.target, llms_path, REPO_ROOT),)
            if resolved is not None
        }
        self.assertNotIn(legacy_path, llms_targets, "llms.txt must not link to topic--along-protocol.md")
        self.assertIn(
            os.path.normpath(os.path.join(REPO_ROOT, "docs", "topic--troubleshooting.md")),
            llms_targets,
            "llms.txt must link to docs/topic--troubleshooting.md",
        )


if __name__ == "__main__":
    unittest.main()
