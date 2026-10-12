#!/usr/bin/env python3
"""
tests/test_version_bump.py - test suite alias for along_version_bump and CI precondition checks.
"""

from __future__ import annotations

import unittest

# Re-export test cases from test_release_ci_check
from test_release_ci_check import TestReleaseCiCheck

if __name__ == "__main__":
    unittest.main()
