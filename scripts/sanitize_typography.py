#!/usr/bin/env python3
"""
sanitize_typography.py - Replace non-ASCII typographic and invisible characters
with standard ASCII equivalents across code, scripts, and markdown documentation.
"""

import os
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import typography

# The forbidden-character table lives in alongkit.typography, shared with the quality
# gate in tests/. Two copies of the rule meant a character could be banned by the gate
# and unknown to this sanitizer, or the reverse.
REPLACEMENTS = typography.REPLACEMENTS


def sanitize_content(content):
    """Replace every banned character; returns (cleaned, changed)."""
    return typography.clean(content)


def sanitize_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
        return False

    cleaned, modified = sanitize_content(content)
    if not modified:
        return False

    try:
        with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
            f.write(cleaned)
        return True
    except Exception as e:
        print(f"Error writing {filepath}: {e}", file=sys.stderr)
        return False

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    modified_count = 0
    patterns = ['**/*.md', '**/*.py', '**/*.sh', '**/*.ps1', '**/*.bat', '**/*.json', '**/*.yaml', '**/*.yml', '**/*.toml']

    for p in patterns:
        for f in glob.glob(os.path.join(root, p), recursive=True):
            rel_parts = os.path.relpath(f, root).replace('\\', '/').split('/')
            if any(part in ('.git', 'node_modules', 'dist', 'build', '.venv', 'venv') for part in rel_parts):
                continue
            if sanitize_file(f):
                print(f"Sanitized: {os.path.relpath(f, root)}")
                modified_count += 1

    print(f"Total files sanitized: {modified_count}")

if __name__ == '__main__':
    main()
