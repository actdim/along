#!/usr/bin/env python3
"""
alongkit.hooks - Programmatic runtime enforcement of Along protocols and rules.
"""

from __future__ import annotations

from .adapters import get_adapter
from .config import (
    HookMode,
    HooksConfig,
    audit_installed_hook_manifests,
    audit_manifest_coverage,
    get_antigravity_hook_manifest,
    get_claude_hook_manifest,
    get_codex_hook_manifest,
    get_cursor_hook_manifest,
    get_dsh_hook_manifest,
    get_runtime_hook_narrowing,
    install_antigravity_hooks,
    install_claude_hooks,
    install_codex_hooks,
    install_cursor_hooks,
    install_dsh_hooks,
    load_config,
    purge_local_along_hooks,
    runtime_gate_tool_union,
)
from .engine import HookEngine, evaluate_event
from .gates import BaseGate, CliSafetyGate, ProjectionProtectionGate, TypographyGate
from .models import GateDecision, GateResult, HookEvent, HookEventType

__all__ = [
    "HookEventType",
    "GateDecision",
    "HookEvent",
    "GateResult",
    "HookMode",
    "HooksConfig",
    "load_config",
    "runtime_gate_tool_union",
    "audit_manifest_coverage",
    "audit_installed_hook_manifests",
    "get_runtime_hook_narrowing",
    "get_antigravity_hook_manifest",
    "install_antigravity_hooks",
    "get_claude_hook_manifest",
    "install_claude_hooks",
    "get_codex_hook_manifest",
    "install_codex_hooks",
    "get_cursor_hook_manifest",
    "install_cursor_hooks",
    "get_dsh_hook_manifest",
    "install_dsh_hooks",
    "purge_local_along_hooks",
    "BaseGate",
    "TypographyGate",
    "ProjectionProtectionGate",
    "CliSafetyGate",
    "HookEngine",
    "evaluate_event",
    "get_adapter",
]

