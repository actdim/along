#!/usr/bin/env python3
"""Fixture crash service: writes log, sleeps briefly, and exits with code 1."""

import sys
import time

print("Starting crash service...")
sys.stdout.flush()
time.sleep(0.3)
print("Crashing now!")
sys.stdout.flush()
sys.exit(1)
