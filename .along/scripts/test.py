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
import unittest

# The engines depend on ruamel.yaml. Resolve it before the suite imports them, so
# `python .along/scripts/test.py` works from a bare interpreter as documented.
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scripts"))
from alongkit import bootstrap, gates

bootstrap.ensure_deps()

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
    
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=tests_dir, pattern="test_*.py")
    quiet = any(arg in ("-q", "--quiet") for arg in sys.argv[1:])
    runner = unittest.TextTestRunner(verbosity=1 if quiet else 2)
    result = runner.run(suite)
    
    sys.exit(0 if result.wasSuccessful() else 1)

if __name__ == "__main__":
    main()
