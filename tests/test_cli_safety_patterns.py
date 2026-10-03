#!/usr/bin/env python3
"""
tests/test_cli_safety_patterns.py - cli_safety detection matrix and default mode.

Regression suite for [bug--cli-safety-heredoc-gaps]: every heredoc delimiter, PowerShell
here-strings sent to files and inline shell writers are caught, while searches that only
name a writer, bash here-strings and shift operators pass. cli_safety enforces by default.
"""

from __future__ import annotations

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit.hooks import HookEvent, HookEventType
from alongkit.hooks.config import HooksConfig
from alongkit.hooks.predicates import check_cli_safety

BLOCKED = (
    "cat <<EOF > test.py\nx = 1\nEOF",
    "python - <<'PY'\nprint(1)\nPY",
    "cat <<-\"END\" > a.txt\n\tx\nEND",
    "git commit -m \"$(cat <<'EOF'\nmsg\nEOF\n)\"",
    "@'\nline\n'@ | Set-Content out.txt",
    "@\"\nline\n\"@ > out.txt",
    "Set-Content -Path a.txt -Value 'x'",
    "$x = 1; Add-Content log.txt 'y'",
    "[System.IO.File]::WriteAllText('a.txt', 'x')",
    "New-Item -Path a.txt -ItemType File -Value 'x'",
    "echo hello > notes.md",
    "printf 'a\\n' >> src/app.py",
    "sed -i 's/a/b/' file.txt",
    "perl -pi -e 's/a/b/' file.txt",
)

ALLOWED = (
    "git status",
    "cat <<< \"$var\"",
    "python -c \"print(1 << 2)\"",
    "Select-String -Path x.py -Pattern 'Set-Content'",
    "grep -n \"sed -i\" README.md",
    "echo done 2>&1",
    "echo hi > /dev/null",
    "echo hi > $null",
    "\"exit=$LASTEXITCODE\"",
    "git commit -m 'one line message (refs #a-b)'",
)


def _cmd(command: str) -> HookEvent:
    return HookEvent(event_type=HookEventType.PRE_TOOL_USE, tool_name="run_command",
                     tool_args={"CommandLine": command}, workspace_root=REPO_ROOT, runtime="claude")


class TestCliSafetyMatrix(unittest.TestCase):
    def test_blocked(self):
        for command in BLOCKED:
            self.assertIsNotNone(check_cli_safety(_cmd(command), REPO_ROOT), command)

    def test_allowed(self):
        for command in ALLOWED:
            self.assertIsNone(check_cli_safety(_cmd(command), REPO_ROOT), command)

    def test_enforced_by_default(self):
        self.assertTrue(HooksConfig().is_enforcing("cli_safety"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
