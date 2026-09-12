#!/usr/bin/env python3
"""
alongkit.hooks.engine - Core execution pipeline for lifecycle gates.

Coordinates gate evaluation, respects shadow vs enforce modes, and logs telemetry.
"""

from __future__ import annotations

import sys
from typing import List, Optional

from .config import HooksConfig, load_config, record_audit_entry
from .declarative import get_all_declarative_gates
from .gates import BaseGate, CliSafetyGate, ProjectionProtectionGate, TypographyGate
from .models import GateDecision, GateResult, HookEvent
from .predicates import record_tool_activity


FALLBACK_GATES: List[BaseGate] = [
    TypographyGate(),
    ProjectionProtectionGate(),
    CliSafetyGate(),
]


class HookEngine:
    """Orchestrates gate evaluation for an incoming HookEvent."""

    def __init__(
        self,
        gates: Optional[List[BaseGate]] = None,
        config: Optional[HooksConfig] = None,
        repo_root: Optional[str] = None,
    ):
        self.repo_root = repo_root
        self.config: HooksConfig = config if config is not None else load_config(repo_root)

        if gates is not None:
            self.gates: List[BaseGate] = gates
        else:
            decl_gates = get_all_declarative_gates(repo_root=repo_root)
            self.gates = list(decl_gates) if decl_gates else list(FALLBACK_GATES)

    def evaluate(self, event: HookEvent, repo_root: Optional[str] = None) -> GateResult:
        """Run all registered gates against the event."""
        effective_root = repo_root or self.repo_root or event.workspace_root

        # Track session activity (edits and test runs)
        if effective_root:
            record_tool_activity(event, effective_root)

        for gate in self.gates:
            # Propagate effective repo_root to declarative gates if needed
            if hasattr(gate, "repo_root") and getattr(gate, "repo_root") is None:
                setattr(gate, "repo_root", effective_root)

            result = gate.evaluate(event)
            if result.is_denied:
                gate_mode = self.config.get_gate_mode(gate.name)
                record_audit_entry(effective_root, event, result, gate_mode)

                if self.config.is_enforcing(gate.name):
                    return result
                else:
                    # Shadow mode: print warning to stderr and continue
                    sys.stderr.write(f"[ALONG HOOK: SHADOW] Would deny execution: {result.reason}\n")
                    sys.stderr.flush()

        return GateResult(decision=GateDecision.ALLOW, exit_code=0)


def evaluate_event(
    event: HookEvent,
    repo_root: Optional[str] = None,
    config: Optional[HooksConfig] = None,
) -> GateResult:
    """Convenience helper to evaluate an event against the default pipeline."""
    engine = HookEngine(repo_root=repo_root, config=config)
    return engine.evaluate(event, repo_root=repo_root)
