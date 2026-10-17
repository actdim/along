"""
alongkit/gatestats.py - How often each gate blocks, warns, and gets bypassed.

Aggregates `.along/diagnostics/hooks_audit.jsonl`: every non-allow hook decision
(`deny`, `ask`, `force_ask`; `mode: shadow` counts as a warning) and every recorded bypass
(`decision: bypass`, written by `alongkit.bypass`). A gate that is bypassed about as often as
it blocks is either wrong or too strict; the numbers show it instead of an impression.
[feat--gate-friction-and-bypass-accountability] REQ-5
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

if __name__ == "__main__":
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along gates stats   (or: python scripts/along_exec.py gates stats)"
    )

from . import repo, textio


@dataclass
class GateStats:
    gate: str
    blocked: int = 0
    warned: int = 0
    bypassed: int = 0

    @property
    def bypass_ratio(self) -> float:
        total = self.blocked + self.bypassed
        return self.bypassed / total if total else 0.0


def audit_path(repo_root: str) -> str:
    return os.path.join(repo.diagnostics_dir(repo_root), "hooks_audit.jsonl")


#: Identical blocks in one conversation from which `along gates stats` reports a loop.
LOOP_THRESHOLD = 3


@dataclass
class GateLoop:
    """The same gate blocked the same target this many times in one conversation."""
    conversation: str
    gate: str
    target: str
    count: int


def _entries(repo_root: str, since: Optional[str] = None) -> List[Dict[str, Any]]:
    path = audit_path(repo_root)
    if not os.path.isfile(path):
        return []
    try:
        lines = textio.read_text(path, strict=False).splitlines()
    except OSError:
        return []
    out: List[Dict[str, Any]] = []
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        if since and str(entry.get("timestamp") or "")[:10] < since:
            continue
        out.append(entry)
    return out


def _is_block(entry: Dict[str, Any]) -> bool:
    return entry.get("mode") != "shadow" and str(entry.get("decision") or "") in ("deny", "ask", "force_ask")


def collect(repo_root: str, since: Optional[str] = None) -> List[GateStats]:
    """Per-gate counts, most blocked first; `since` (YYYY-MM-DD) drops older entries."""
    stats: Dict[str, GateStats] = {}
    for entry in _entries(repo_root, since):
        gate = str(entry.get("gate") or "unknown")
        decision = str(entry.get("decision") or "")
        item = stats.setdefault(gate, GateStats(gate))
        if decision == "bypass":
            item.bypassed += 1
        elif entry.get("mode") == "shadow":
            item.warned += 1
        elif decision in ("deny", "ask", "force_ask"):
            item.blocked += 1
    return sorted(stats.values(), key=lambda s: (-s.blocked, -s.bypassed, s.gate))


def loops(repo_root: str, since: Optional[str] = None, threshold: int = LOOP_THRESHOLD) -> List[GateLoop]:
    """Repeated identical blocks per conversation: an agent retrying what a gate holds.

    Identical means same gate and same target (older entries without `target`: same reason).
    [debt--gate-simplification]
    """
    counts: Dict[Tuple[str, str, str], int] = {}
    for entry in _entries(repo_root, since):
        if not _is_block(entry) or not entry.get("conversation_id"):
            continue
        target = str(entry.get("target") or entry.get("reason") or "")
        key = (str(entry["conversation_id"]), str(entry.get("gate") or "unknown"), target)
        counts[key] = counts.get(key, 0) + 1
    found = [GateLoop(c, g, t, n) for (c, g, t), n in counts.items() if n >= threshold]
    return sorted(found, key=lambda lp: (-lp.count, lp.gate, lp.conversation))


def format_loops(rows: List[GateLoop], limit: int = 10) -> str:
    if not rows:
        return f"No repeated blocks (>= {LOOP_THRESHOLD} identical in one conversation)."
    out = [f"Repeated blocks (>= {LOOP_THRESHOLD} identical in one conversation):"]
    for lp in rows[:limit]:
        target = lp.target if len(lp.target) <= 80 else lp.target[:77] + "..."
        out.append(f"  {lp.count:4d}x  {lp.gate}  [{lp.conversation[:12]}]  {target}")
    if len(rows) > limit:
        out.append(f"  ... {len(rows) - limit} more")
    return "\n".join(out)


def format_table(rows: List[GateStats]) -> str:
    if not rows:
        return "No gate decisions recorded yet (.along/diagnostics/hooks_audit.jsonl)."
    width = max(len(r.gate) for r in rows)
    out = [f"{'gate'.ljust(width)}  blocked  warned  bypassed  bypass%"]
    for r in rows:
        out.append(f"{r.gate.ljust(width)}  {r.blocked:7d}  {r.warned:6d}  {r.bypassed:8d}  {r.bypass_ratio * 100:6.0f}%")
    return "\n".join(out)


def most_bypassed(rows: List[GateStats], limit: int = 3) -> List[GateStats]:
    """Gates with at least one bypass, highest bypass ratio first."""
    return sorted((r for r in rows if r.bypassed), key=lambda r: (-r.bypass_ratio, -r.bypassed))[:limit]
