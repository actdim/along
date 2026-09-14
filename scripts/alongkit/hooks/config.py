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
from typing import Any, Dict, Optional, Tuple

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


def get_claude_hook_manifest() -> Dict[str, Any]:
    """Canonical hook configuration dictionary for Anthropic Claude Code (.claude/settings.json)."""
    return {
        "PreToolUse": [
            {
                "matcher": "Write|WriteFile|Edit|EditFile|Bash|PowerShell",
                "command": "python scripts/along_hook.py --runtime claude --event PreToolUse",
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Write|WriteFile|Edit|EditFile",
                "command": "python scripts/along_hook.py --runtime claude --event PostToolUse",
            }
        ],
        "Stop": [
            {
                "command": "python scripts/along_hook.py --runtime claude --event Stop",
            }
        ],
    }


def install_claude_hooks(repo_root: str, dry_run: bool = False) -> Tuple[str, str]:
    """Scaffold or update .claude/settings.json for Claude Code in the given repository."""
    claude_dir = os.path.join(repo_root, ".claude")
    settings_file = os.path.join(claude_dir, "settings.json")

    existing: Dict[str, Any] = {}
    if os.path.isfile(settings_file):
        try:
            content = textio.read_text(settings_file, strict=False)
            if content.strip():
                existing = json.loads(content)
                if not isinstance(existing, dict):
                    return "failed", f"left {settings_file} alone: top-level is not a JSON object"
        except (OSError, ValueError) as exc:
            return "failed", f"left {settings_file} alone: cannot parse JSON ({exc})"

    spec = get_claude_hook_manifest()
    existing_hooks = existing.get("hooks")
    if not isinstance(existing_hooks, dict):
        existing_hooks = {}
        existing["hooks"] = existing_hooks

    changed = False
    for event_name, hook_list in spec.items():
        cur_list = existing_hooks.get(event_name)
        if not isinstance(cur_list, list):
            cur_list = []
            existing_hooks[event_name] = cur_list
            changed = True

        for expected_hook in hook_list:
            matched_idx = -1
            for idx, item in enumerate(cur_list):
                if (
                    isinstance(item, dict)
                    and "along_hook.py" in str(item.get("command", ""))
                    and f"--event {event_name}" in str(item.get("command", ""))
                ):
                    matched_idx = idx
                    break

            if matched_idx >= 0:
                if cur_list[matched_idx] != expected_hook:
                    cur_list[matched_idx] = expected_hook
                    changed = True
            else:
                cur_list.append(expected_hook)
                changed = True

    if not changed:
        return "present", f"{settings_file}: already up to date"

    if dry_run:
        return "dry-run", f"would update {settings_file} with Along hooks"

    os.makedirs(claude_dir, exist_ok=True)
    textio.write_text(settings_file, json.dumps(existing, indent=2) + "\n", newline="\n")
    return "installed", f"updated {settings_file} with Along hooks"


def get_codex_hook_manifest() -> Dict[str, Any]:
    """Canonical hook configuration dictionary for OpenAI Codex (.codex/hooks.json)."""
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "write_file|WriteFile|Write|create_file|edit_file|EditFile|Edit|patch|patch_file|shell|exec|execute|bash|Bash|run_command",
                    "command": "python scripts/along_hook.py --runtime codex --event PreToolUse",
                }
            ],
            "PostToolUse": [
                {
                    "matcher": "write_file|WriteFile|Write|create_file|edit_file|EditFile|Edit|patch|patch_file",
                    "command": "python scripts/along_hook.py --runtime codex --event PostToolUse",
                }
            ],
            "Stop": [
                {
                    "command": "python scripts/along_hook.py --runtime codex --event Stop",
                }
            ],
        }
    }


def install_codex_hooks(repo_root: str, dry_run: bool = False) -> Tuple[str, str]:
    """Scaffold or update .codex/hooks.json for OpenAI Codex in the given repository."""
    codex_dir = os.path.join(repo_root, ".codex")
    hooks_file = os.path.join(codex_dir, "hooks.json")

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

    spec = get_codex_hook_manifest()
    spec_hooks = spec.get("hooks", {})

    hooks_container: Dict[str, Any]
    if "hooks" in existing and isinstance(existing["hooks"], dict):
        hooks_container = existing["hooks"]
    elif any(k in existing for k in ("PreToolUse", "PostToolUse", "Stop")):
        hooks_container = existing
    else:
        if not isinstance(existing.get("hooks"), dict):
            existing["hooks"] = {}
        hooks_container = existing["hooks"]

    changed = False
    for event_name, hook_list in spec_hooks.items():
        cur_list = hooks_container.get(event_name)
        if not isinstance(cur_list, list):
            cur_list = []
            hooks_container[event_name] = cur_list
            changed = True

        for expected_hook in hook_list:
            matched_idx = -1
            for idx, item in enumerate(cur_list):
                if (
                    isinstance(item, dict)
                    and "along_hook.py" in str(item.get("command", ""))
                    and f"--event {event_name}" in str(item.get("command", ""))
                ):
                    matched_idx = idx
                    break

            if matched_idx >= 0:
                if cur_list[matched_idx] != expected_hook:
                    cur_list[matched_idx] = expected_hook
                    changed = True
            else:
                cur_list.append(expected_hook)
                changed = True

    if not changed:
        return "present", f"{hooks_file}: already up to date"

    if dry_run:
        return "dry-run", f"would update {hooks_file} with Along hooks"

    os.makedirs(codex_dir, exist_ok=True)
    textio.write_text(hooks_file, json.dumps(existing, indent=2) + "\n", newline="\n")
    return "installed", f"updated {hooks_file} with Along hooks"



