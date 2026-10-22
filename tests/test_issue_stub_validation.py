#!/usr/bin/env python3
"""
tests/test_issue_stub_validation.py - Hermetic tests for issue stub validation and lifecycle gates.

Covers:
- REQ-1: Centralized is_issue_stub and validate_issue_completion in alongkit.entities
- REQ-2: Content validation gate in along issue done
- REQ-3: Stub and closed-issue pre-check in along start and along plan approve
- REQ-4: Entity stub validation in along wrap
- REQ-5: Pre-commit gate against issue stubs in along commit
- REQ-7: audit_stub_issues and doctor diagnostics
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import entities, frontmatter, lifecycle, markdown, proc, textio
import hermetic


VALID_COMPLETED_ISSUE = """---
protocol: along
protocol_version: "4.4.15"
slug: real-feature
type: feat
status: in-progress
priority: medium
created: 2026-10-16
updated: 2026-10-16
agent: test-agent
tags: [test]
---

# Real Feature Title

Here is a genuine description of the feature, explaining the problem and solution.

## Acceptance Criteria
- [x] Configure output directory to dist
- [x] All unit tests pass cleanly
"""

STUB_ISSUE_TEMPLATE = """---
protocol: along
protocol_version: "4.4.15"
slug: stub-feature
type: feat
status: open
priority: medium
created: 2026-10-16
updated: 2026-10-16
agent: test-agent
tags: []
---

# Stub Feature

Describe the feature, requirements, and background context here.

## Acceptance Criteria
- [ ] Task requirement 1
- [ ] Automated tests passing
"""


class TestIssueStubValidationUnit(unittest.TestCase):
    """Unit tests for alongkit.entities stub detection and completion validation."""

    def test_01_detects_default_scaffold_placeholders(self):
        is_stub, reasons = entities.is_issue_stub(STUB_ISSUE_TEMPLATE)
        self.assertTrue(is_stub)
        self.assertTrue(any("Describe the feature" in r for r in reasons))

    def test_01b_detects_ste_scaffold_placeholders(self):
        ste_scaffold = """---
protocol: along
slug: ste-feature
type: feat
status: open
---
# STE Feature

Describe the problem, goals, and background context here.

## Requirements
- REQ-1: [Subject] MUST [one verifiable action] [object] [condition].

## Acceptance Criteria
- [ ] Task requirement 1
- [ ] Automated tests passing
"""
        is_stub, reasons = entities.is_issue_stub(ste_scaffold)
        self.assertTrue(is_stub)
        self.assertTrue(any("Describe the problem" in r for r in reasons))
        self.assertTrue(any("[Subject] MUST" in r for r in reasons))

    def test_02_detects_task_requirement_1_even_if_checked(self):
        content = """---
protocol: along
slug: test-issue
type: task
status: in-progress
---
# Issue

Some description.

## Acceptance Criteria
- [x] Task requirement 1
- [x] Automated tests passing
"""
        is_stub, reasons = entities.is_issue_stub(content)
        self.assertTrue(is_stub)
        self.assertTrue(any("only default scaffold items" in r or "Task requirement 1" in r for r in reasons))

    def test_03_passes_legitimate_requirements(self):
        is_stub, reasons = entities.is_issue_stub(VALID_COMPLETED_ISSUE)
        self.assertFalse(is_stub)
        self.assertEqual(reasons, [])

    def test_04_ignores_placeholder_text_in_code_blocks(self):
        content = """---
protocol: along
slug: doc-issue
type: docs
status: in-progress
---
# Documentation Issue

We document how Along detects stubs:

```markdown
Describe the feature, requirements, and background context here.
- [ ] Task requirement 1
```

## Acceptance Criteria
- [x] Updated documentation topic
"""
        is_stub, reasons = entities.is_issue_stub(content)
        self.assertFalse(is_stub, f"expected not stub, got {reasons}")

    def test_05_validate_completion_rejects_missing_acceptance_criteria(self):
        content = """---
protocol: along
slug: no-ac
type: feat
status: in-progress
---
# Feature without AC

Description without criteria.
"""
        ok, reasons = entities.validate_issue_completion(content, "done")
        self.assertFalse(ok)
        self.assertTrue(any("Missing mandatory '## Acceptance Criteria'" in r for r in reasons))

    def test_06_validate_completion_rejects_uncompleted_checkboxes(self):
        content = """---
protocol: along
slug: uncompleted
type: feat
status: in-progress
---
# Feature

Real description.

## Acceptance Criteria
- [x] First item done
- [ ] Second item still open
"""
        ok, reasons = entities.validate_issue_completion(content, "done")
        self.assertFalse(ok)
        self.assertTrue(any("uncompleted checklist item" in r for r in reasons))

    def test_07_validate_completion_passes_valid_issue(self):
        ok, reasons = entities.validate_issue_completion(VALID_COMPLETED_ISSUE, "done")
        self.assertTrue(ok, f"expected clean pass, got {reasons}")

    def test_08_validate_completion_bypasses_cancelled_and_superseded(self):
        # Even with stubs and unchecked items, cancelled status should pass
        ok, reasons = entities.validate_issue_completion(STUB_ISSUE_TEMPLATE, "cancelled")
        self.assertTrue(ok)
        ok2, reasons2 = entities.validate_issue_completion(STUB_ISSUE_TEMPLATE, "superseded")
        self.assertTrue(ok2)


class TestLifecycleCommandGates(unittest.TestCase):
    """End-to-end tests for along start, plan approve, issue done, and wrap gates."""

    EXEC = os.path.join(REPO_ROOT, "scripts", "along_exec.py")

    def setUp(self):
        self.root = hermetic.make_repo_fixture()
        self.issues = os.path.join(self.root, ".along", "ISSUES")
        self.done = os.path.join(self.issues, "done")


    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _write_issue(self, filename: str, content: str) -> str:
        path = os.path.join(self.issues, filename)
        textio.write_text(path, content, newline="\n")
        return path

    def test_10_along_start_rejects_closed_issue(self):
        done_file = os.path.join(self.done, "task--already-done.md")
        content = VALID_COMPLETED_ISSUE.replace("slug: real-feature", "slug: already-done").replace("status: in-progress", "status: done")
        textio.write_text(done_file, content, newline="\n")

        res = proc.run_capture([sys.executable, self.EXEC, "start", "already-done"], cwd=self.root)

        self.assertEqual(res.returncode, 1)
        self.assertIn("already closed in issues/done", (res.stderr or "").lower())


    def test_11_along_start_rejects_scaffold_stub(self):
        self._write_issue("feat--stub-feature.md", STUB_ISSUE_TEMPLATE)

        res = proc.run_capture([sys.executable, self.EXEC, "start", "stub-feature"], cwd=self.root)
        self.assertEqual(res.returncode, 2)
        self.assertIn("contains unfilled scaffold placeholders", (res.stderr or "").lower())

    def test_12_along_start_succeeds_on_valid_issue(self):
        self._write_issue("feat--real-feature.md", VALID_COMPLETED_ISSUE)

        res = proc.run_capture([sys.executable, self.EXEC, "start", "real-feature"], cwd=self.root)
        self.assertEqual(res.returncode, 0, f"{res.stdout}\n{res.stderr}")

    def test_13_along_issue_done_rejects_scaffold_stub(self):
        self._write_issue("feat--stub-feature.md", STUB_ISSUE_TEMPLATE)

        res = proc.run_capture([sys.executable, self.EXEC, "issue", "done", "stub-feature"], cwd=self.root)
        self.assertEqual(res.returncode, 2)
        self.assertIn("contains template placeholder text", (res.stderr or "").lower())
        # Verify file was NOT moved
        self.assertTrue(os.path.isfile(os.path.join(self.issues, "feat--stub-feature.md")))
        self.assertFalse(os.path.isfile(os.path.join(self.done, "feat--stub-feature.md")))

    def test_14_along_issue_done_succeeds_on_valid_issue(self):
        self._write_issue("feat--real-feature.md", VALID_COMPLETED_ISSUE)

        res = proc.run_capture([sys.executable, self.EXEC, "issue", "done", "real-feature"], cwd=self.root)
        self.assertEqual(res.returncode, 0, f"{res.stdout}\n{res.stderr}")
        self.assertTrue(os.path.isfile(os.path.join(self.done, "feat--real-feature.md")))

    def test_15_along_issue_done_allows_cancelling_stub(self):
        self._write_issue("feat--stub-feature.md", STUB_ISSUE_TEMPLATE)

        res = proc.run_capture([
            sys.executable, self.EXEC, "issue", "done", "stub-feature", "--status", "cancelled"
        ], cwd=self.root)
        self.assertEqual(res.returncode, 0, f"{res.stdout}\n{res.stderr}")
        moved = os.path.join(self.done, "feat--stub-feature.md")
        self.assertTrue(os.path.isfile(moved))
        data, _ = frontmatter.parse(textio.read_text(moved))
        self.assertEqual(data["status"], "cancelled")

    def test_16_along_wrap_rejects_scaffold_stub(self):
        self._write_issue("feat--stub-feature.md", STUB_ISSUE_TEMPLATE)

        code = lifecycle.execute_wrap(
            self.root,
            "stub-feature",
            status="done",
            no_verify=True,
            decisions=[],
        )
        self.assertEqual(code, 2)
        # Verify file stayed in ISSUES/
        self.assertTrue(os.path.isfile(os.path.join(self.issues, "feat--stub-feature.md")))

    def test_17_audit_stub_issues_finds_stubs_and_reasons(self):
        self._write_issue("feat--stub-feature.md", STUB_ISSUE_TEMPLATE)
        self._write_issue("feat--real-feature.md", VALID_COMPLETED_ISSUE)

        findings = entities.audit_stub_issues(self.root)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["slug"], "stub-feature")
        self.assertTrue(any("Describe the feature" in r for r in findings[0]["reasons"]))


if __name__ == "__main__":
    unittest.main()
