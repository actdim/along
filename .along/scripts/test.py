#!/usr/bin/env python3
# Status: verified
"""
test.py - Automated Test Runner Hook for along repository.
Executes the comprehensive unit test suite via Python standard unittest.
"""

import sys
import os
import unittest

# The engines depend on ruamel.yaml. Resolve it before the suite imports them, so
# `python .along/scripts/test.py` works from a bare interpreter as documented.
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scripts"))
from alongkit import bootstrap

bootstrap.ensure_deps()

def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    tests_dir = os.path.join(repo_root, "tests")
    
    os.environ["ALONG_TEST_RUNNER"] = "1"
    
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=tests_dir, pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    sys.exit(0 if result.wasSuccessful() else 1)

if __name__ == "__main__":
    main()
