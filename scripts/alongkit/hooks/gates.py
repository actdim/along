#!/usr/bin/env python3
"""
alongkit.hooks.gates - Individual gate implementations for lifecycle hooks.

Implements stateless content and command integrity gates:
- TypographyGate: Blocks writes containing forbidden non-ASCII typography.
- ProjectionProtectionGate: Blocks manual edits to compiled views.
- CliSafetyGate: Blocks dangerous shell patterns, heredocs, and inline writers.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .. import repo, sanitizer, typography
from .models import GateDecision, GateResult, HookEvent, HookEventType


class BaseGate:
    """Abstract base gate."""
    name: str = "base"

    def evaluate(self, event: HookEvent) -> GateResult:
        raise NotImplementedError


class TypographyGate(BaseGate):
    """Enforces clean ASCII typography on file creation and edits."""
    name: str = "typography"

    # Suffixes governed by the rule (code, docstrings, prose)
    GOVERNED_SUFFIXES: Tuple[str, ...] = (
        ".md", ".py", ".ts", ".js", ".tsx", ".jsx",
        ".sh", ".ps1", ".bat", ".rs", ".go", ".txt",
    )

    def evaluate(self, event: HookEvent) -> GateResult:
        if event.event_type != HookEventType.PRE_TOOL_USE:
            return GateResult(decision=GateDecision.ALLOW, gate_name=self.name)

        tool = event.tool_name
        args = event.tool_args

        target_file = args.get("TargetFile") or args.get("target_file") or args.get("path") or ""
        content = ""

        if tool in ("write_to_file", "write_file", "create_file"):
            content = args.get("CodeContent") or args.get("content") or ""
        elif tool in ("replace_file_content", "edit_file", "patch_file"):
            content = args.get("ReplacementContent") or args.get("replacement_content") or args.get("content") or ""
        else:
            return GateResult(decision=GateDecision.ALLOW, gate_name=self.name)

        if not content:
            return GateResult(decision=GateDecision.ALLOW, gate_name=self.name)

        # Check if file is inside a localized directory where non-ASCII characters are valid
        if target_file:
            norm_path = repo.normalize_posix(target_file)
            segments = norm_path.split("/")
            if any(seg in sanitizer.LOCALIZED_DIRS for seg in segments):
                return GateResult(decision=GateDecision.ALLOW, gate_name=self.name)

            _, ext = os.path.splitext(norm_path)
            if ext and ext.lower() not in self.GOVERNED_SUFFIXES:
                return GateResult(decision=GateDecision.ALLOW, gate_name=self.name)

        hits = typography.findings(content)
        if not hits:
            return GateResult(decision=GateDecision.ALLOW, gate_name=self.name)

        counts: Dict[str, int] = {}
        lines: List[int] = []
        for line_num, _col, char in hits:
            cname = typography.name_of(char)
            counts[cname] = counts.get(cname, 0) + 1
            if line_num not in lines:
                lines.append(line_num)

        detail = ", ".join(f"{c} {name}" for name, c in sorted(counts.items()))
        line_str = ", ".join(str(n) for n in lines[:6])
        if len(lines) > 6:
            line_str += ", ..."

        target_label = f" in '{target_file}'" if target_file else ""
        reason = (
            f"Typography Gate Violation: Detected forbidden non-ASCII typography{target_label}: "
            f"{detail} (lines: {line_str}). "
            f"Replace with standard ASCII equivalents ('-', '\"', ''', '...') before writing."
        )
        return GateResult(
            decision=GateDecision.DENY,
            reason=reason,
            gate_name=self.name,
            exit_code=2,
        )


class ProjectionProtectionGate(BaseGate):
    """Blocks manual edits to compiled views (.along/ISSUES.md, docs/INDEX.md)."""
    name: str = "projection_protection"

    PROTECTED_PROJECTIONS: Tuple[str, ...] = (
        ".along/issues.md",
        "docs/index.md",
    )

    def evaluate(self, event: HookEvent) -> GateResult:
        if event.event_type != HookEventType.PRE_TOOL_USE:
            return GateResult(decision=GateDecision.ALLOW, gate_name=self.name)

        tool = event.tool_name
        if tool not in ("write_to_file", "write_file", "replace_file_content", "edit_file", "patch_file"):
            return GateResult(decision=GateDecision.ALLOW, gate_name=self.name)

        args = event.tool_args
        target = args.get("TargetFile") or args.get("target_file") or args.get("path") or ""
        if not target:
            return GateResult(decision=GateDecision.ALLOW, gate_name=self.name)

        norm_path = repo.normalize_posix(target).lower()
        is_protected = any(
            norm_path == p or norm_path.endswith("/" + p)
            for p in self.PROTECTED_PROJECTIONS
        )

        if is_protected:
            reason = (
                f"Projection Protection Violation: Direct manual edits to '{target}' are forbidden. "
                "The Single Source of Truth (SSOT) is atomic files in '.along/ISSUES/' or 'docs/'. "
                "Modify atomic files and run 'along issue sync' or 'along kb sync' to recompile."
            )
            return GateResult(
                decision=GateDecision.DENY,
                reason=reason,
                gate_name=self.name,
                exit_code=2,
            )

        return GateResult(decision=GateDecision.ALLOW, gate_name=self.name)


class CliSafetyGate(BaseGate):
    """Blocks dangerous shell patterns, heredocs, and inline file writers."""
    name: str = "cli_safety"

    DANGEROUS_PATTERNS: List[Tuple[re.Pattern, str]] = [
        (re.compile(r"<<\s*['\"]?EOF['\"]?", re.IGNORECASE), "Heredoc syntax (<<EOF)"),
        (re.compile(r"python\d*\s+-c\s+.*open\(.*['\"][wa]['\"].*\)", re.DOTALL), "Inline Python file writer"),
        (re.compile(r"git\s+reset\s+--hard", re.IGNORECASE), "Destructive unstaged Git wipe (git reset --hard)"),
        (re.compile(r"git\s+clean\s+-[a-zA-Z]*f", re.IGNORECASE), "Destructive Git clean (git clean -f)"),
        (re.compile(r"npm\s+install\s+(-g|--global)", re.IGNORECASE), "Global package manager mutation (npm -g)"),
        (re.compile(r"(choco|winget)\s+install", re.IGNORECASE), "Global system package installation"),
    ]

    def evaluate(self, event: HookEvent) -> GateResult:
        if event.event_type != HookEventType.PRE_TOOL_USE:
            return GateResult(decision=GateDecision.ALLOW, gate_name=self.name)

        tool = event.tool_name
        if tool not in ("run_command", "execute_command", "bash", "shell"):
            return GateResult(decision=GateDecision.ALLOW, gate_name=self.name)

        cmd = event.tool_args.get("CommandLine") or event.tool_args.get("command") or ""
        if not cmd:
            return GateResult(decision=GateDecision.ALLOW, gate_name=self.name)

        for pattern, label in self.DANGEROUS_PATTERNS:
            if pattern.search(cmd):
                reason = (
                    f"CLI Safety Gate Violation: {label} detected in command: {cmd.strip()[:100]}. "
                    "Use native file editing tools and Along lifecycle scripts instead."
                )
                return GateResult(
                    decision=GateDecision.DENY,
                    reason=reason,
                    gate_name=self.name,
                    exit_code=2,
                )

        return GateResult(decision=GateDecision.ALLOW, gate_name=self.name)
