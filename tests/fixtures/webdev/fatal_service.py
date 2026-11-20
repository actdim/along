#!/usr/bin/env python3
"""Fixture fatal service: prints fatal error pattern and crashes."""

import sys
import time

print("Initializing...")
sys.stdout.flush()
time.sleep(0.2)
print("FATAL_ERROR: Segmentation fault in core engine")
sys.stdout.flush()
sys.exit(2)
