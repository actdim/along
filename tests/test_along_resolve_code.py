#!/usr/bin/env python3
"""
tests/test_along_resolve_code.py - Hermetic tests for test-gated code conflict resolution and prediction.

Covers [feat--test-gated-code-merge-pipeline]:
- Code conflict parsing and language-aware reconciliation (imports, definitions)
- Collision detection and conflict marker retention
- Quality Gate Verification Pipeline (syntax, typography, tests)
- Transactional rollback via FileTransaction on test/gate failures
- Pre-merge conflict prediction across Low, Medium, and High risk scenarios
"""

from __future__ import annotations

import os
import sys

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

import unittest
from typing import List

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import conflict_check, proc, repo, resolve_code, textio
import along_conflict_check
import along_resolve
from tests import hermetic


class TestCodeImportReconciliation(unittest.TestCase):
    """Test import statement set-union deduplication."""

    def test_reconcile_python_imports_disjoint(self):
        ours = ["import os\n", "from typing import List\n"]
        theirs = ["import sys\n", "from typing import Dict\n"]
        merged = resolve_code.reconcile_python_imports(ours, theirs)
        self.assertIsNotNone(merged)
        merged_str = "".join(merged)
        self.assertIn("import os\n", merged_str)
        self.assertIn("from typing import List\n", merged_str)
        self.assertIn("import sys\n", merged_str)
        self.assertIn("from typing import Dict\n", merged_str)

    def test_reconcile_python_imports_with_duplicates(self):
        ours = ["import os\n", "import sys\n"]
        theirs = ["import sys\n", "import json\n"]
        merged = resolve_code.reconcile_python_imports(ours, theirs)
        self.assertIsNotNone(merged)
        merged_str = "".join(merged)
        self.assertEqual(merged_str.count("import sys\n"), 1)
        self.assertIn("import os\n", merged_str)
        self.assertIn("import json\n", merged_str)

    def test_reconcile_js_imports_union(self):
        ours = ["import { foo } from './foo';\n"]
        theirs = ["import { bar } from './bar';\n"]
        merged = resolve_code.reconcile_js_imports(ours, theirs)
        self.assertIsNotNone(merged)
        merged_str = "".join(merged)
        self.assertIn("import { foo } from './foo';\n", merged_str)
        self.assertIn("import { bar } from './bar';\n", merged_str)


class TestCodeDefinitionReconciliation(unittest.TestCase):
    """Test AST-aware definition reconciliation and collision detection."""

    def test_reconcile_disjoint_python_functions(self):
        ours = [
            "def handle_alpha():\n",
            "    return 'alpha'\n",
        ]
        theirs = [
            "def handle_beta():\n",
            "    return 'beta'\n",
        ]
        merged = resolve_code.reconcile_python_definitions(ours, theirs)
        self.assertIsNotNone(merged)
        merged_str = "".join(merged)
        self.assertIn("def handle_alpha():", merged_str)
        self.assertIn("def handle_beta():", merged_str)
        # Verify valid Python syntax
        compile(merged_str, "<test>", "exec")

    def test_collision_retains_none(self):
        ours = [
            "def calculate(x):\n",
            "    return x + 1\n",
        ]
        theirs = [
            "def calculate(x):\n",
            "    return x * 2\n",
        ]
        merged = resolve_code.reconcile_python_definitions(ours, theirs)
        # Colliding symbol names must not be auto-merged
        self.assertIsNone(merged)

    def test_resolve_code_content_preserves_collision_markers(self):
        code = (
            "import os\n\n"
            "<<<<<<< ours\n"
            "def compute(a):\n"
            "    return a + 10\n"
            "=======\n"
            "def compute(a):\n"
            "    return a + 20\n"
            ">>>>>>> theirs\n"
        )
        merged, clean, warnings = resolve_code.resolve_code_content(code, file_path="calc.py")
        self.assertFalse(clean)
        self.assertIn("<<<<<<< ours", merged)
        self.assertIn("=======", merged)
        self.assertIn(">>>>>>> theirs", merged)


class TestQualityGatesAndTransactionalRollback(unittest.TestCase):
    """Test verification pipeline and atomic rollback on failures."""

    def test_successful_resolution_commits_and_stages(self):
        with hermetic.repo_fixture() as root:
            target = os.path.join(root, "service.py")
            conflicted = (
                "<<<<<<< ours\n"
                "import os\n"
                "def func_a():\n"
                "    return 1\n"
                "=======\n"
                "import sys\n"
                "def func_b():\n"
                "    return 2\n"
                ">>>>>>> theirs\n"
            )
            textio.write_text(target, conflicted)

            success, notes = resolve_code.resolve_and_verify_code(
                root, target_files=[target], run_tests=False
            )
            self.assertTrue(success)

            resolved = textio.read_text(target)
            self.assertNotIn("<<<<<<<", resolved)
            self.assertIn("def func_a():", resolved)
            self.assertIn("def func_b():", resolved)

    def test_syntax_failure_triggers_atomic_rollback(self):
        with hermetic.repo_fixture() as root:
            target = os.path.join(root, "broken.py")
            conflicted = (
                "<<<<<<< ours\n"
                "def broken_syntax(:\n"
                "=======\n"
                "def other():\n"
                "    pass\n"
                ">>>>>>> theirs\n"
            )
            textio.write_text(target, conflicted)

            success, notes = resolve_code.resolve_and_verify_code(
                root, target_files=[target], run_tests=False
            )
            self.assertFalse(success)

            # Rollback must restore original conflict markers byte-for-byte
            current_content = textio.read_text(target)
            self.assertEqual(current_content, conflicted)

    def test_test_failure_triggers_atomic_rollback(self):
        with hermetic.repo_fixture() as root:
            target = os.path.join(root, "module.py")
            conflicted = (
                "<<<<<<< ours\n"
                "def alpha():\n"
                "    return 10\n"
                "=======\n"
                "def beta():\n"
                "    return 20\n"
                ">>>>>>> theirs\n"
            )
            textio.write_text(target, conflicted)

            # Pass a test command guaranteed to fail (exit code 1)
            failing_cmd = [sys.executable, "-c", "import sys; sys.exit(1)"]

            success, notes = resolve_code.resolve_and_verify_code(
                root, target_files=[target], run_tests=True, test_cmd=failing_cmd
            )
            self.assertFalse(success)
            self.assertTrue(any("Test suite verification failed" in n for n in notes))

            # Must have rolled back to original conflict markers
            current_content = textio.read_text(target)
            self.assertEqual(current_content, conflicted)


class TestPreMergeConflictPredictor(unittest.TestCase):
    """Test pre-merge conflict prediction across risk categories."""

    def _init_git_repo(self, root: str) -> None:
        proc.git(["init"], cwd=root)
        proc.git(["config", "user.name", "Test Agent"], cwd=root)
        proc.git(["config", "user.email", "test@example.com"], cwd=root)
        init_file = os.path.join(root, "init.txt")
        textio.write_text(init_file, "init\n")
        proc.git(["add", "init.txt"], cwd=root)
        proc.git(["commit", "-m", "initial commit"], cwd=root)

    def test_predict_conflicts_on_self(self):
        with hermetic.repo_fixture() as root:
            self._init_git_repo(root)
            report = conflict_check.predict_conflicts(root, "HEAD")
            self.assertEqual(report.risk_level, "LOW")
            self.assertEqual(len(report.overlapping_files), 0)

    def test_predict_conflicts_with_divergent_branches(self):
        with hermetic.repo_fixture() as root:
            self._init_git_repo(root)
            # Create a base file and commit
            py_file = os.path.join(root, "shared.py")
            textio.write_text(py_file, "def existing():\n    return 0\n")
            proc.git(["add", "shared.py"], cwd=root)
            proc.git(["commit", "-m", "add base shared.py"], cwd=root)

            # Get current branch name (e.g. master or main)
            res_branch = proc.git(["branch", "--show-current"], cwd=root)
            main_branch = res_branch.stdout.strip() or "master"

            # Create branch-feature from base
            proc.git(["checkout", "-b", "branch-feature"], cwd=root)
            textio.write_text(py_file, "def existing():\n    return 100\n\ndef feature():\n    return 1\n")
            proc.git(["commit", "-am", "modify existing in branch-feature"], cwd=root)

            # Switch back to main and create conflicting change
            proc.git(["checkout", main_branch], cwd=root)
            textio.write_text(py_file, "def existing():\n    return 200\n\ndef other():\n    return 2\n")
            proc.git(["commit", "-am", "modify existing in main"], cwd=root)

            # Predict conflict between main and branch-feature
            report = conflict_check.predict_conflicts(root, "branch-feature")
            self.assertEqual(report.risk_level, "HIGH")
            self.assertIn("shared.py", report.overlapping_files)
            self.assertIn("shared.py", report.colliding_symbols)
            self.assertIn("existing", report.colliding_symbols["shared.py"])


class TestCLIExecution(unittest.TestCase):
    """Test CLI commands along resolve --code and along conflict-check."""

    def test_along_resolve_cli_code_flag(self):
        with hermetic.repo_fixture() as root:
            target = os.path.join(root, "app.py")
            conflicted = (
                "<<<<<<< ours\n"
                "import os\n"
                "=======\n"
                "import sys\n"
                ">>>>>>> theirs\n"
            )
            textio.write_text(target, conflicted)

            # Run via along_resolve run_resolve
            parser_args = along_resolve.argparse.Namespace(
                code=True,
                docs=False,
                files=[target],
                dry_run=False,
                strict=True,
                no_tests=True,
                no_kb_sync=True,
            )
            exit_code = along_resolve.run_resolve(parser_args)
            self.assertEqual(exit_code, 0)

            resolved = textio.read_text(target)
            self.assertNotIn("<<<<<<<", resolved)
            self.assertIn("import os", resolved)
            self.assertIn("import sys", resolved)


if __name__ == "__main__":
    unittest.main()
