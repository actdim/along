"""
alongkit/verify.py - The repository's declared verification policy.

`.along/config.json`:

    {"verify": {"tests": "required" | "none", "reason": "", "tracked_by": "", "checks": []}}

`tests: "required"` (the default) means tests must actually run. `tests: "none"` is an
explicit, visible decision: it needs a `reason` and a `tracked_by` issue key (so the missing
tests stay on the board as debt) and runs the declared `checks` (`build`, `lint`,
`typecheck` lifecycle hooks) instead. A test hook that cannot run (missing npm script,
runner not found) is reported as misconfigured, never as failing tests.
[bug--test-gate-no-tests-policy]
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

if __name__ == "__main__":
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along test   (or: along doctor to see the verify policy)"
    )

from . import proc, repo, textio

TESTS_REQUIRED = "required"
TESTS_NONE = "none"
TEST_POLICIES = (TESTS_REQUIRED, TESTS_NONE)
#: Lifecycle hooks a `tests: none` policy may run instead of tests.
CHECK_NAMES = ("build", "lint", "typecheck")


@dataclass
class VerifyPolicy:
    tests: str = TESTS_REQUIRED
    reason: str = ""
    tracked_by: str = ""
    checks: List[str] = field(default_factory=list)
    declared: bool = False

    def describe(self) -> str:
        if self.tests == TESTS_NONE:
            checks = f"; checks: {', '.join(self.checks)}" if self.checks else ""
            return f"tests: none - {self.reason} ({self.tracked_by}){checks}"
        return "tests: required" + ("" if self.declared else " (default)")


def load_policy(repo_root: str) -> VerifyPolicy:
    """The `verify` block of `.along/config.json`; the default policy when absent or unreadable."""
    path = os.path.join(repo.state_dir(repo_root), "config.json")
    try:
        data = json.loads(textio.read_text(path)) if os.path.isfile(path) else {}
    except (OSError, ValueError):
        return VerifyPolicy()
    block = data.get("verify") if isinstance(data, dict) else None
    if not isinstance(block, dict):
        return VerifyPolicy()
    checks = block.get("checks") or []
    return VerifyPolicy(
        tests=str(block.get("tests") or TESTS_REQUIRED).strip().lower(),
        reason=str(block.get("reason") or "").strip(),
        tracked_by=str(block.get("tracked_by") or "").strip(),
        checks=[str(c).strip().lower() for c in checks if str(c).strip()] if isinstance(checks, list) else [],
        declared=True,
    )


def policy_problems(repo_root: str, policy: VerifyPolicy) -> List[str]:
    """Why `policy` is not a valid declaration (empty when it is)."""
    problems: List[str] = []
    if policy.tests not in TEST_POLICIES:
        problems.append(f"verify.tests must be one of {', '.join(TEST_POLICIES)} (got '{policy.tests}')")
        return problems
    if policy.tests == TESTS_NONE:
        if not policy.reason:
            problems.append("verify.tests = \"none\" needs a non-empty verify.reason")
        if not policy.tracked_by:
            problems.append("verify.tests = \"none\" needs verify.tracked_by (the issue key that tracks the missing tests)")
        elif not _issue_exists(repo_root, policy.tracked_by):
            problems.append(f"verify.tracked_by '{policy.tracked_by}' names no issue in this or an enclosing context")
    for name in policy.checks:
        if name not in CHECK_NAMES:
            problems.append(f"verify.checks: unknown check '{name}' (allowed: {', '.join(CHECK_NAMES)})")
    return problems


def _issue_exists(repo_root: str, key: str) -> bool:
    from . import entities
    return entities.reference_context(repo_root, key) is not None


# ---------------------------------------------------------------------------
# Hook misconfiguration
# ---------------------------------------------------------------------------

_MISCONFIG_RES: Tuple[Tuple[re.Pattern, str], ...] = (
    (re.compile(r"Missing script:?\s*\"?([\w:.-]+)\"?", re.IGNORECASE), 'npm script "{0}" not found'),
    (re.compile(r"Command \"?([\w:.-]+)\"? not found", re.IGNORECASE), 'package script "{0}" not found'),
    (re.compile(r"^(?:.*: )?([\w.-]+): (?:command )?not found$", re.MULTILINE), "runner '{0}' not found"),
    (re.compile(r"'([\w.-]+)' is not recognized as an internal or external command", re.IGNORECASE),
     "runner '{0}' not found"),
    (re.compile(r"Could not start ([^:\s]+)", re.IGNORECASE), "runner '{0}' did not start"),
    (re.compile(r"(?:Could not find|Cannot find|ENOENT)[^\n]*?((?:vitest|jest|pytest|tsconfig|vite)[\w.-]*\.(?:config\.)?(?:[jt]s|json|ini|toml|cfg))",
                re.IGNORECASE), "runner config '{0}' not found"),
)
#: Exit codes of a shell that could not find or execute the command.
_NOT_FOUND_EXIT_CODES = (126, 127, 9009)


def misconfiguration(output: str, exit_code: int) -> Optional[str]:
    """A short description when a failed test command could not run at all, else None."""
    if exit_code == 0:
        return None
    text = output or ""
    for rx, template in _MISCONFIG_RES:
        match = rx.search(text)
        if match:
            return template.format(match.group(1))
    if exit_code in _NOT_FOUND_EXIT_CODES:
        return f"the test command could not be started (exit {exit_code})"
    return None


def misconfiguration_message(detail: str) -> str:
    return (f"Test hook misconfigured: {detail}. Fix .along/scripts/test.py or set "
            "verify.tests = \"none\" (with verify.reason and verify.tracked_by) in .along/config.json.")


# ---------------------------------------------------------------------------
# Checks run instead of tests
# ---------------------------------------------------------------------------

def check_command(repo_root: str, name: str) -> Optional[List[str]]:
    """Command of check `name`: its `.along/scripts/<name>` hook, or for `build` the detected one."""
    import shlex

    from . import gates, lifecycle

    script = lifecycle.get_lifecycle_script_path(repo_root, name)
    if os.path.isfile(script) and not gates.is_unconfigured_hook(script):
        return lifecycle.build_interpreter_cmd(script, [])
    if name == "build":
        cmd, _verified = lifecycle.detect_lifecycle_action(repo_root, "build")
        if cmd:
            return shlex.split(cmd)
    return None


def run_checks(repo_root: str, checks: Sequence[str], label: str) -> bool:
    """Run each declared check; True when all passed. A check without a command fails."""
    ok = True
    for name in checks:
        cmd = check_command(repo_root, name)
        if not cmd:
            print(f"[Error] {label}: check '{name}' has no command (add .along/scripts/{name}.py).",
                  file=sys.stderr)
            ok = False
            continue
        print(f"-> [{label}] Running check '{name}': {' '.join(cmd)}")
        res = proc.run_capture(cmd, cwd=repo_root, trip_on_anomaly=False)
        if res.ok:
            print(f"-> [{label}] Check '{name}' passed.")
            continue
        ok = False
        detail = misconfiguration(res.stdout + "\n" + res.stderr, res.returncode)
        print(f"[Error] {label}: check '{name}' failed" + (f" ({detail})" if detail else "") + ".",
              file=sys.stderr)
        for stream in (res.stdout, res.stderr):
            if stream:
                print(stream, file=sys.stderr)
    return ok


# ---------------------------------------------------------------------------
# Change-aware skip
# ---------------------------------------------------------------------------

_DOC_SUFFIXES = (".md",)
_DOC_FILES = ("llms.txt", "llms-full.txt")
_VERSION_LINE = re.compile(r'^[+-]\s*"version"\s*:\s*"[^"]*",?\s*$')


def is_doc_only_path(rel: str) -> bool:
    """Documentation or Along state, never code: `*.md`, `docs/**`, `.along/**` (not scripts), llms*.txt."""
    path = rel.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    parts = [p for p in path.split("/") if p]
    for i, part in enumerate(parts):
        if part == ".along":
            if i + 1 < len(parts) and parts[i + 1] == "scripts":
                return False
            return True
    if path.startswith("docs/") or "docs" in parts[:-1] or path.endswith(_DOC_SUFFIXES):
        return True
    return os.path.basename(path) in _DOC_FILES


def version_only_manifest_change(diff_text: str) -> bool:
    """True when a package.json diff changes nothing but the `version` field."""
    changed = [line for line in (diff_text or "").splitlines()
               if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]
    return bool(changed) and all(_VERSION_LINE.match(line) for line in changed)


def docs_only_change(repo_root: str, paths: Sequence[str], diff_for=None) -> bool:
    """True when every changed path is documentation/state, or a version-only package.json.

    `diff_for(path)` returns the staged diff of one path (for package.json).
    """
    paths = [p for p in paths if p]
    if not paths:
        return False
    for path in paths:
        if is_doc_only_path(path):
            continue
        if os.path.basename(path) == "package.json" and diff_for is not None \
                and version_only_manifest_change(diff_for(path)):
            continue
        return False
    return True
