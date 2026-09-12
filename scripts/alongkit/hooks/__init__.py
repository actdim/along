#!/usr/bin/env python3
"""
alongkit.hooks - Programmatic runtime enforcement of Along protocols and rules.
"""

from __future__ import annotations

from .adapters import get_adapter
from .config import (
    HookMode,
    HooksConfig,
    get_antigravity_hook_manifest,
    install_antigravity_hooks,
    load_config,
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
    "get_antigravity_hook_manifest",
    "install_antigravity_hooks",
    "BaseGate",
    "TypographyGate",
    "ProjectionProtectionGate",
    "CliSafetyGate",
    "HookEngine",
    "evaluate_event",
    "get_adapter",
]
