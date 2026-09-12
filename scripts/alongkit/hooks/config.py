#!/usr/bin/env python3
"""
alongkit.hooks.config - Configuration and audit logging for lifecycle hooks.

Supports dual-mode governance:
- 'enforce': Blocks execution on gate violations.
- 'shadow': Evaluates gates and logs violations to .along/diagnostics/hooks_audit.jsonl
  without blocking tool execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from typing import Any, Dict, Optional

from .. import repo, textio
from .models import GateResult, HookEvent


class HookMode:
    ENFORCE = "enforce"
    SHADOW = "shadow"


DEFAULT_GATE_MODES: Dict[str, str] = {
    "typography": HookMode.ENFORCE,
    "projection_protection": HookMode.ENFORCE,
    "cli_safety": HookMode.SHADOW,
}


@dataclass
class HooksConfig:
    """Runtime configuration for hook execution."""
    mode: str = HookMode.ENFORCE
    gates: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_GATE_MODES))
    record_transcript: bool = False

    def get_gate_mode(self, gate_name: str) -> str:
        """Resolve mode for an individual gate."""
        if gate_name in self.gates:
            return self.gates[gate_name]
        return self.mode

    def is_enforcing(self, gate_name: str) -> bool:
        """True if the gate should actively block on violation."""
        return self.get_gate_mode(gate_name) == HookMode.ENFORCE


def load_config(repo_root: Optional[str] = None) -> HooksConfig:
    """Load hooks configuration from repository or environment."""
    config = HooksConfig()

    env_mode = os.environ.get("ALONG_HOOK_MODE", "").strip().lower()
    if env_mode in (HookMode.ENFORCE, HookMode.SHADOW):
        config.mode = env_mode

    if not repo_root:
        repo_root = repo.find_repo_root()

    if repo_root:
        config_path = os.path.join(repo.state_dir(repo_root), "config.json")
        if os.path.isfile(config_path):
            try:
                data = json.loads(textio.read_text(config_path, strict=False))
                hooks_data = data.get("hooks", {})
                if isinstance(hooks_data, dict):
                    if "mode" in hooks_data and hooks_data["mode"] in (HookMode.ENFORCE, HookMode.SHADOW):
                        if not env_mode:
                            config.mode = hooks_data["mode"]
                    if "gates" in hooks_data and isinstance(hooks_data["gates"], dict):
                        for gname, gmode in hooks_data["gates"].items():
                            if gmode in (HookMode.ENFORCE, HookMode.SHADOW):
                                config.gates[gname] = gmode
                    if "record_transcript" in hooks_data:
                        config.record_transcript = bool(hooks_data["record_transcript"])
            except (OSError, ValueError):
                pass

    return config


def record_audit_entry(
    repo_root: Optional[str],
    event: HookEvent,
    result: GateResult,
    mode: str,
) -> None:
    """Append a violation record to .along/diagnostics/hooks_audit.jsonl."""
    if not repo_root:
        repo_root = repo.find_repo_root()
    if not repo_root:
        return

    diagnostics_dir = os.path.join(repo.state_dir(repo_root), "diagnostics")
    try:
        os.makedirs(diagnostics_dir, exist_ok=True)
        audit_file = os.path.join(diagnostics_dir, "hooks_audit.jsonl")
        entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "gate": result.gate_name,
            "decision": result.decision.value,
            "mode": mode,
            "runtime": event.runtime,
            "tool": event.tool_name,
            "reason": result.reason,
            "conversation_id": event.conversation_id,
            "step_idx": event.step_idx,
        }
        with open(audit_file, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def get_antigravity_hook_manifest() -> Dict[str, Any]:
    """Canonical hook configuration dictionary for Google Antigravity."""
    return {
        "along-runtime-gates": {
            "PreToolUse": [
                {
                    "matcher": "write_to_file|replace_file_content|run_command",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python ../scripts/along_hook.py --runtime antigravity --event PreToolUse",
                            "timeout": 15,
                        }
                    ],
                }
            ]
        }
    }


def install_antigravity_hooks(repo_root: str, dry_run: bool = False) -> Tuple[str, str]:
    """Scaffold or update .agents/hooks.json for Antigravity in the given repository."""
    agents_dir = os.path.join(repo_root, ".agents")
    hooks_file = os.path.join(agents_dir, "hooks.json")

    existing: Dict[str, Any] = {}
    if os.path.isfile(hooks_file):
        try:
            content = textio.read_text(hooks_file, strict=False)
            if content.strip():
                existing = json.loads(content)
                if not isinstance(existing, dict):
                    return "failed", f"left {hooks_file} alone: top-level is not a JSON object"
        except (OSError, ValueError) as exc:
            return "failed", f"left {hooks_file} alone: cannot parse JSON ({exc})"

    spec = get_antigravity_hook_manifest()
    gate_key = "along-runtime-gates"
    if existing.get(gate_key) == spec[gate_key]:
        return "present", f"{hooks_file}: already up to date"

    if dry_run:
        return "dry-run", f"would update {hooks_file} with {gate_key}"

    existing[gate_key] = spec[gate_key]
    os.makedirs(agents_dir, exist_ok=True)
    textio.write_text(hooks_file, json.dumps(existing, indent=2) + "\n", newline="\n")
    return "installed", f"updated {hooks_file} with {gate_key}"

