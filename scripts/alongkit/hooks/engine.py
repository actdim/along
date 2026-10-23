#!/usr/bin/env python3
"""
alongkit.hooks.engine - Core execution pipeline for lifecycle gates.

Coordinates gate evaluation, respects shadow vs enforce modes, and logs telemetry.
"""

from __future__ import annotations

import sys
from typing import List, Optional

from .. import profiles
from .config import HooksConfig, load_config, record_audit_entry
from .containment import is_autonomous as check_is_autonomous
from .declarative import get_all_declarative_gates
from .escalation import classify_escalation, route_escalation
from .gates import BaseGate, ProjectionProtectionGate
from .adapters import normalize
from .models import GateDecision, GateResult, HookEvent, HookEventType
from .predicates import record_gate_denial, record_tool_activity


#: Runtimes whose hook protocol can hand an ASK decision to the user
#: (Claude Code: `permissionDecision: "ask"`). See [bug--claude-stop-loop-ask-mapping].
ASK_CAPABLE_RUNTIMES = ("antigravity", "claude")

#: Used only when the declarative catalogue cannot be loaded.
FALLBACK_GATES: List[BaseGate] = [
    ProjectionProtectionGate(),
]


def _is_procedural(gate: BaseGate) -> bool:
    """A catalogue entry with `denial: procedural`: its denials are the normal way to the
    plan and settle on a later approval. [feat--anti-silent-fallback-gate]"""
    options = getattr(getattr(gate, "defn", None), "options", None) or {}
    return str(options.get("denial") or "").strip().lower() == "procedural"


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
        is_auto = (self.config.profile == profiles.PROFILE_AUTONOMOUS
                   or check_is_autonomous(event, repo_root=effective_root))

        # Fail closed on tool names no adapter maps: infer writes, audit the rest.
        # See [bug--claude-adapter-unmapped-tools].
        event = normalize.fail_closed(event)
        unmapped = event.tool_args.get(normalize.UNMAPPED_MARKER)
        if unmapped and event.event_type == HookEventType.PRE_TOOL_USE:
            record_audit_entry(
                effective_root,
                event,
                GateResult(
                    decision=GateDecision.ALLOW,
                    reason=f"unmapped_tool: '{unmapped}' is not mapped by the {event.runtime} adapter",
                    gate_name="unmapped_tool",
                ),
                "audit",
            )

        for gate in self.gates:
            if not self.config.is_enabled(gate.name):
                continue
            # Propagate effective repo_root to declarative gates if needed
            if hasattr(gate, "repo_root") and getattr(gate, "repo_root") is None:
                setattr(gate, "repo_root", effective_root)

            result = gate.evaluate(event)
            if not result.is_allowed:
                # Escalation list operations under autonomous profile can route to handler
                esc = classify_escalation(event, effective_root)
                if esc:
                    op_type, detail = esc
                    if is_auto:
                        esc_res = route_escalation(
                            event, op_type, detail, effective_root, original_reason=result.reason
                        )
                        gate_mode = self.config.get_gate_mode(gate.name)
                        record_audit_entry(effective_root, event, esc_res, gate_mode)
                        if not esc_res.is_allowed and self.config.is_enforcing(gate.name):
                            record_gate_denial(event, effective_root, esc_res.gate_name or gate.name, esc_res.reason,
                                               procedural=_is_procedural(gate))
                            return esc_res
                        elif esc_res.is_allowed:
                            continue

                gate_mode = self.config.get_gate_mode(gate.name)
                record_audit_entry(effective_root, event, result, gate_mode)

                if self.config.is_enforcing(gate.name):
                    record_gate_denial(event, effective_root, result.gate_name or gate.name, result.reason,
                                       procedural=_is_procedural(gate))
                    if result.decision in (GateDecision.ASK, GateDecision.FORCE_ASK):
                        if is_auto:
                            # Autonomous profile: no gate returns interactive ask.
                            # General ask decisions become deny with a clear actionable reason.
                            return GateResult(
                                decision=GateDecision.DENY,
                                reason=result.reason or "Operation rejected: interactive confirmation is disabled under autonomous profile.",
                                gate_name=result.gate_name or gate.name,
                                exit_code=2,
                            )
                        # Runtimes with a native ask keep it; the rest cannot prompt.
                        if event.runtime not in ASK_CAPABLE_RUNTIMES:
                            return GateResult(
                                decision=GateDecision.DENY,
                                reason=result.reason or "Operation rejected: plan approval required before code mutations.",
                                gate_name=result.gate_name or gate.name,
                                exit_code=2,
                            )
                    return result
                else:
                    # Shadow mode: print warning to stderr and continue
                    sys.stderr.write(f"[ALONG HOOK: SHADOW] Would block execution ({result.decision.value}): {result.reason}\n")
                    sys.stderr.flush()

        # Under autonomous profile, check escalation list for operations not guarded by previous gates
        if is_auto:
            esc = classify_escalation(event, effective_root)
            if esc:
                op_type, detail = esc
                esc_res = route_escalation(event, op_type, detail, effective_root)
                if not esc_res.is_allowed:
                    record_audit_entry(effective_root, event, esc_res, "enforce")
                    record_gate_denial(event, effective_root, esc_res.gate_name or "escalation", esc_res.reason)
                    return esc_res

        # Track session activity (edits and test runs) only for what the gates let through:
        # a rejected write or test run is not the session's. [bug--hook-activation-and-gate-deadlock]
        if effective_root:
            record_tool_activity(event, effective_root)

        return GateResult(decision=GateDecision.ALLOW, exit_code=0)


def evaluate_event(
    event: HookEvent,
    repo_root: Optional[str] = None,
    config: Optional[HooksConfig] = None,
) -> GateResult:
    """Convenience helper to evaluate an event against the default pipeline."""
    engine = HookEngine(repo_root=repo_root, config=config)
    return engine.evaluate(event, repo_root=repo_root)
