#!/usr/bin/env python3
"""
alongkit.hooks.traceability - Bi-directional Prose-to-Gate Traceability Scanner.

Scans AGENTS.md, skills/*/SKILL.md, .along/rules/*.md, and docs/ for [gate: <id>]
badges, verifying that every documented rule maps to an active runtime gate and
every gate in default_gates.yaml is anchored in prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
from typing import Dict, List, Optional, Set, Tuple

from .. import repo, textio
from .declarative import (
    DEFAULT_GATES_FILE,
    DeclarativeGateDefinition,
    load_gate_definitions,
    resolve_handler,
)


GATE_BADGE_PATTERN = re.compile(
    r"(?:\[gate:\s*([a-zA-Z0-9_-]+)\]|<!--\s*gate:\s*([a-zA-Z0-9_-]+)\s*-->)"
)


@dataclass
class ProseAnchor:
    """A single [gate: <id>] badge discovered in documentation."""
    gate_id: str
    file_path: str
    line_number: int
    raw_match: str


@dataclass
class TraceabilityReport:
    """Audit outcome for prose-to-gate and gate-to-prose consistency."""
    total_gates: int = 0
    total_prose_anchors: int = 0
    mapped_gates: List[str] = field(default_factory=list)
    dangling_references: List[ProseAnchor] = field(default_factory=list)
    undocumented_gates: List[str] = field(default_factory=list)
    schema_errors: List[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not self.dangling_references and not self.schema_errors


def _canonical_id(raw_id: str) -> str:
    """Normalize hyphens and underscores for resilient identifier matching."""
    return raw_id.strip().lower().replace("-", "_")


def scan_prose_anchors(repo_root: str) -> List[ProseAnchor]:
    """Scan all markdown files in repo root for gate badges."""
    anchors: List[ProseAnchor] = []
    target_dirs = [
        os.path.join(repo_root, "skills"),
        os.path.join(repo_root, "docs"),
        os.path.join(repo.state_dir(repo_root), "rules"),
    ]

    files_to_scan: List[str] = []

    # 1. Root AGENTS.md and CLAUDE.md
    for root_file in ("AGENTS.md", "CLAUDE.md", "README.md"):
        full_path = os.path.join(repo_root, root_file)
        if os.path.isfile(full_path):
            files_to_scan.append(full_path)

    # 2. Directory targets
    for target in target_dirs:
        if os.path.isdir(target):
            for root, _dirs, files in os.walk(target):
                for f in files:
                    if f.endswith(".md"):
                        files_to_scan.append(os.path.join(root, f))

    for path in sorted(files_to_scan):
        try:
            content = textio.read_text(path, strict=False)
        except (OSError, UnicodeDecodeError):
            continue

        for line_idx, line in enumerate(content.splitlines(), start=1):
            for match in GATE_BADGE_PATTERN.finditer(line):
                gid = match.group(1) or match.group(2)
                if gid:
                    rel_path = repo.safe_relpath(path, repo_root).replace("\\", "/")
                    anchors.append(
                        ProseAnchor(
                            gate_id=gid.strip(),
                            file_path=rel_path,
                            line_number=line_idx,
                            raw_match=match.group(0),
                        )
                    )

    return anchors


def audit_traceability(repo_root: Optional[str] = None) -> TraceabilityReport:
    """Perform bi-directional traceability verification."""
    effective_root = repo_root or repo.find_repo_root() or os.getcwd()

    # Load defined gates from protocol defaults and repository overrides
    gates_by_canon: Dict[str, DeclarativeGateDefinition] = {}
    schema_errors: List[str] = []

    definitions: List[DeclarativeGateDefinition] = []
    if os.path.isfile(DEFAULT_GATES_FILE):
        definitions.extend(load_gate_definitions(DEFAULT_GATES_FILE))

    repo_yaml = os.path.join(repo.state_dir(effective_root), "rules", "gates.yaml")
    if os.path.isfile(repo_yaml):
        definitions.extend(load_gate_definitions(repo_yaml))

    for defn in definitions:
        cid = _canonical_id(defn.id)
        gates_by_canon[cid] = defn

        # Validate predicate handlers
        for rule in defn.rules:
            if rule.rule_type == "predicate" and rule.handler_name:
                try:
                    resolve_handler(rule.handler_name)
                except (ValueError, ImportError, AttributeError) as exc:
                    schema_errors.append(f"Gate '{defn.id}' invalid handler '{rule.handler_name}': {exc}")

    # Scan prose anchors
    prose_anchors = scan_prose_anchors(effective_root)

    anchored_canon_ids: Set[str] = set()
    dangling: List[ProseAnchor] = []

    for anchor in prose_anchors:
        cid = _canonical_id(anchor.gate_id)
        if cid in gates_by_canon:
            anchored_canon_ids.add(cid)
        else:
            dangling.append(anchor)

    undocumented = [
        defn.id for cid, defn in gates_by_canon.items()
        if cid not in anchored_canon_ids
    ]

    mapped = [
        defn.id for cid, defn in gates_by_canon.items()
        if cid in anchored_canon_ids
    ]

    return TraceabilityReport(
        total_gates=len(gates_by_canon),
        total_prose_anchors=len(prose_anchors),
        mapped_gates=sorted(mapped),
        dangling_references=dangling,
        undocumented_gates=sorted(undocumented),
        schema_errors=schema_errors,
    )


def format_traceability_report(report: TraceabilityReport) -> str:
    """Render a clean ASCII report for CLI and test output."""
    lines: List[str] = [
        "=== ALONG PROTOCOL GATE TRACEABILITY REPORT ===",
        f"Total Defined Gates: {report.total_gates}",
        f"Total Prose Badges:  {report.total_prose_anchors}",
        f"Enforced & Anchored: {len(report.mapped_gates)} / {report.total_gates}",
    ]

    if report.mapped_gates:
        lines.append("\n[Active & Traceable Gates]:")
        for gid in report.mapped_gates:
            lines.append(f"  + [gate: {gid}]")

    if report.undocumented_gates:
        lines.append(f"\n[Undocumented Gates ({len(report.undocumented_gates)})]:")
        for gid in report.undocumented_gates:
            lines.append(f"  ? {gid} (defined in gates.yaml but has no [gate: {gid}] in prose)")

    if report.dangling_references:
        lines.append(f"\n[Dangling References ({len(report.dangling_references)}) - GATE NOT FOUND IN YAML]:")
        for anchor in report.dangling_references:
            lines.append(f"  ! {anchor.file_path}:{anchor.line_number} -> {anchor.raw_match}")

    if report.schema_errors:
        lines.append(f"\n[Schema & Handler Errors ({len(report.schema_errors)})]:")
        for err in report.schema_errors:
            lines.append(f"  x {err}")

    status_str = "PASSED (Clean Bi-Directional Contract)" if report.is_clean else "FAILED"
    lines.append(f"\nVerdict: {status_str}")
    return "\n".join(lines)
