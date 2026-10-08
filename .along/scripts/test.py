#!/usr/bin/env python3
# Status: verified
"""
test.py - Automated Test Runner Hook for along repository.
Executes the comprehensive unit test suite via Python standard unittest.

This is the only supported entry point for this repository's suite: the tests refuse
raw `python -m unittest` / `pytest` because they need `ALONG_TEST_RUNNER`, the syntax
gate, and the resolved dependencies set up here. Pass `-q` / `--quiet` for dot output
(`npm run test:quiet`). See [bug--test-quiet-script-guard-conflict].
"""

import sys
import os
import time
import unittest

# The engines depend on ruamel.yaml. Resolve it before the suite imports them, so
# `python .along/scripts/test.py` works from a bare interpreter as documented.
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scripts"))
from alongkit import bootstrap, gates, testruns

# The suite also needs the `dev` group (the dashboard stack), which the shared runtime
# environment `~/.along/venv` does not carry: run inside the project environment first.
# See [bug--test-hook-lacks-dashboard-deps].
bootstrap.ensure_project_env(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ("ruamel.yaml", "fastapi", "pydantic"))
bootstrap.ensure_deps()


class TimingTestResult(unittest.TextTestResult):
    """Tracks per-test elapsed time [feat--test-gate-cost-reduction] REQ-3."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.durations = []
        self._test_start_times = {}

    def startTest(self, test):
        super().startTest(test)
        self._test_start_times[test.id()] = time.monotonic()

    def stopTest(self, test):
        super().stopTest(test)
        start = self._test_start_times.pop(test.id(), None)
        if start is not None:
            self.durations.append((time.monotonic() - start, test.id()))


class TimingTestRunner(unittest.TextTestRunner):
    resultclass = TimingTestResult


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    # Pre-Flight Syntax Gate: halt before test discovery if syntax errors exist
    if not gates.syntax_gate(repo_root, label="Pre-Flight Syntax Gate"):
        print("[CRITICAL] Syntax validation failed before test discovery. Aborting.", file=sys.stderr)
        sys.exit(1)

    tests_dir = os.path.join(repo_root, "tests")
    
    os.environ["ALONG_TEST_RUNNER"] = "1"
    # The suite must not see the agent session that launched it: gates bind per session id.
    from alongkit import session
    for var in session.SESSION_ENV_VARS:
        os.environ.pop(var, None)

    is_doc = any(arg in ("--doc", "--doc-tests") for arg in sys.argv[1:])
    loader = unittest.TestLoader()
    args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    if is_doc:
        doc_targets = gates.get_doc_tests(repo_root)
        suite = unittest.TestSuite()
        for target in doc_targets:
            if target.endswith(".py") or "*" in target:
                suite.addTests(loader.discover(start_dir=tests_dir, pattern=target))
            else:
                suite.addTests(loader.loadTestsFromName(target))
    elif args:
        suite = unittest.TestSuite()
        for target in args:
            if target.endswith(".py") or "*" in target:
                suite.addTests(loader.discover(start_dir=tests_dir, pattern=target))
            else:
                suite.addTests(loader.loadTestsFromName(target))
    else:
        suite = loader.discover(start_dir=tests_dir, pattern="test_*.py")
    quiet = any(arg in ("-q", "--quiet") for arg in sys.argv[1:])
    runner = TimingTestRunner(verbosity=1 if quiet else 2)
    result = runner.run(suite)

    durations = sorted(getattr(result, "durations", []), key=lambda x: x[0], reverse=True)
    slowest_limit = 5
    for a in sys.argv[1:]:
        if a.startswith("--slowest="):
            try:
                slowest_limit = int(a.split("=")[1])
            except ValueError:
                pass
    if durations and slowest_limit > 0:
        top = durations[:slowest_limit]
        print(f"\nSlowest tests (top {len(top)}):")
        for dur, tid in top:
            print(f"  {dur:6.2f}s  {tid}")

    # [feat--test-gate-cost-reduction] REQ-1 & REQ-6: record green run for full suite
    if result.wasSuccessful() and not is_doc and not args:
        tree = testruns.tree_hash(repo_root)
        if tree:
            testruns.record_run(repo_root, True, tree, "test.py")

    sys.exit(0 if result.wasSuccessful() else 1)

if __name__ == "__main__":
    main()
