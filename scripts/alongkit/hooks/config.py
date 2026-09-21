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
        for k in config.gates:
            config.gates[k] = env_mode

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


def get_hook_command(runtime: str, event: str, is_global: bool = False) -> str:
    """Generate command string for a runtime lifecycle hook."""
    if not is_global:
        return f"python scripts/along_hook.py --runtime {runtime} --event {event}"
    script_path = os.path.expanduser("~/.along/bin/along_hook.py")
    return f'python "{script_path}" --runtime {runtime} --event {event}'


def get_antigravity_hook_manifest(is_global: bool = False) -> Dict[str, Any]:
    """Canonical hook configuration dictionary for Google Antigravity."""
    return {
        "along-runtime-gates": {
            "PreToolUse": [
                {
                    "matcher": "write_to_file|replace_file_content|run_command",
                    "hooks": [
                        {
                            "type": "command",
                            "command": get_hook_command("antigravity", "PreToolUse", is_global=is_global),
                            "timeout": 15,
                        }
                    ],
                }
            ]
        }
    }


def install_antigravity_hooks(
    repo_root: Optional[str] = None,
    dry_run: bool = False,
    is_global: bool = False,
    target_home: Optional[str] = None,
) -> Tuple[str, str]:
    """Scaffold or update hooks.json for Antigravity globally or in repo_root."""
    if is_global:
        agents_dir = target_home or os.path.expanduser("~/.gemini/config")
    else:
        if not repo_root:
            return "failed", "repo_root is required for local hook install"
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

    spec = get_antigravity_hook_manifest(is_global=is_global)
    gate_key = "along-runtime-gates"
    if existing.get(gate_key) == spec[gate_key]:
        return "present", f"{hooks_file}: already up to date"

    if dry_run:
        return "dry-run", f"would update {hooks_file} with {gate_key}"

    existing[gate_key] = spec[gate_key]
    os.makedirs(agents_dir, exist_ok=True)
    textio.write_text(hooks_file, json.dumps(existing, indent=2) + "\n", newline="\n")
    return "installed", f"updated {hooks_file} with {gate_key}"


def get_claude_hook_manifest(is_global: bool = False) -> Dict[str, Any]:
    """Canonical hook configuration dictionary for Anthropic Claude Code (.claude/settings.json)."""
    return {
        "PreToolUse": [
            {
                "matcher": "Write|WriteFile|Edit|EditFile|Bash|PowerShell",
                "command": get_hook_command("claude", "PreToolUse", is_global=is_global),
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Write|WriteFile|Edit|EditFile",
                "command": get_hook_command("claude", "PostToolUse", is_global=is_global),
            }
        ],
        "Stop": [
            {
                "command": get_hook_command("claude", "Stop", is_global=is_global),
            }
        ],
    }


def install_claude_hooks(
    repo_root: Optional[str] = None,
    dry_run: bool = False,
    is_global: bool = False,
    target_home: Optional[str] = None,
) -> Tuple[str, str]:
    """Scaffold or update settings.json for Claude Code globally or in repo_root."""
    if is_global:
        claude_dir = target_home or os.path.expanduser("~/.claude")
    else:
        if not repo_root:
            return "failed", "repo_root is required for local hook install"
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

    spec = get_claude_hook_manifest(is_global=is_global)
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



def get_codex_hook_manifest(is_global: bool = False) -> Dict[str, Any]:
    """Canonical hook configuration dictionary for OpenAI Codex (.codex/hooks.json)."""
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "write_file|WriteFile|Write|create_file|edit_file|EditFile|Edit|patch|patch_file|shell|exec|execute|bash|Bash|run_command",
                    "command": get_hook_command("codex", "PreToolUse", is_global=is_global),
                }
            ],
            "PostToolUse": [
                {
                    "matcher": "write_file|WriteFile|Write|create_file|edit_file|EditFile|Edit|patch|patch_file",
                    "command": get_hook_command("codex", "PostToolUse", is_global=is_global),
                }
            ],
            "Stop": [
                {
                    "command": get_hook_command("codex", "Stop", is_global=is_global),
                }
            ],
        }
    }


def install_codex_hooks(
    repo_root: Optional[str] = None,
    dry_run: bool = False,
    is_global: bool = False,
    target_home: Optional[str] = None,
) -> Tuple[str, str]:
    """Scaffold or update hooks.json for OpenAI Codex globally or in repo_root."""
    if is_global:
        codex_dir = target_home or os.path.expanduser("~/.codex")
    else:
        if not repo_root:
            return "failed", "repo_root is required for local hook install"
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

    spec = get_codex_hook_manifest(is_global=is_global)
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


def get_cursor_hook_manifest(is_global: bool = False) -> Dict[str, Any]:
    """Canonical hook configuration dictionary for Cursor (.cursor/hooks.json)."""
    return {
        "version": 1,
        "hooks": {
            "preToolUse": [
                {
                    "command": get_hook_command("cursor", "PreToolUse", is_global=is_global),
                }
            ],
            "postToolUse": [
                {
                    "command": get_hook_command("cursor", "PostToolUse", is_global=is_global),
                }
            ],
            "stop": [
                {
                    "command": get_hook_command("cursor", "Stop", is_global=is_global),
                }
            ],
        },
    }


def install_cursor_hooks(
    repo_root: Optional[str] = None,
    dry_run: bool = False,
    is_global: bool = False,
    target_home: Optional[str] = None,
) -> Tuple[str, str]:
    """Scaffold or update hooks.json for Cursor globally or in repo_root."""
    if is_global:
        cursor_dir = target_home or os.path.expanduser("~/.cursor")
    else:
        if not repo_root:
            return "failed", "repo_root is required for local hook install"
        cursor_dir = os.path.join(repo_root, ".cursor")
    hooks_file = os.path.join(cursor_dir, "hooks.json")

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

    spec = get_cursor_hook_manifest(is_global=is_global)
    spec_hooks = spec.get("hooks", {})

    if "version" not in existing:
        existing["version"] = 1

    hooks_container = existing.get("hooks")
    if not isinstance(hooks_container, dict):
        hooks_container = {}
        existing["hooks"] = hooks_container

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
                    and f"--event {event_name}".lower() in str(item.get("command", "")).lower()
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

    os.makedirs(cursor_dir, exist_ok=True)
    textio.write_text(hooks_file, json.dumps(existing, indent=2) + "\n", newline="\n")
    return "installed", f"updated {hooks_file} with Along hooks"


def purge_local_along_hooks(repo_root: str, recursive: bool = True, dry_run: bool = False) -> List[str]:
    """Purge spurious local Along hooks and workaround scripts from a consumer repository and its subprojects."""
    actions: List[str] = []
    if not repo_root or not os.path.isdir(repo_root):
        return actions

    contexts = [os.path.abspath(repo_root)]
    if recursive:
        try:
            for c in repo.find_agent_contexts(repo_root):
                abs_c = os.path.abspath(c)
                if abs_c not in contexts:
                    contexts.append(abs_c)
        except (OSError, ValueError):
            pass

    for ctx in contexts:
        # 1. Purge .agents/hooks.json
        agents_hooks = os.path.join(ctx, ".agents", "hooks.json")
        if os.path.isfile(agents_hooks):
            try:
                content = textio.read_text(agents_hooks, strict=False)
                data = json.loads(content) if content.strip() else {}
                if isinstance(data, dict) and "along-runtime-gates" in data:
                    del data["along-runtime-gates"]
                    if not data:
                        if not dry_run:
                            os.remove(agents_hooks)
                        actions.append(f"removed {agents_hooks}")
                        # Note: We do not remove agents_dir (.agents) even if empty, because active
                        # agent processes (e.g. Antigravity) may hold in-memory hook registrations
                        # with cwd set to this directory; deleting it causes OS-level chdir failures.
                    else:
                        if not dry_run:
                            textio.write_text(agents_hooks, json.dumps(data, indent=2) + "\n", newline="\n")
                        actions.append(f"cleaned along-runtime-gates from {agents_hooks}")
            except (OSError, ValueError):
                pass

        # 2. Purge .claude/settings.json
        claude_settings = os.path.join(ctx, ".claude", "settings.json")
        if os.path.isfile(claude_settings):
            try:
                content = textio.read_text(claude_settings, strict=False)
                data = json.loads(content) if content.strip() else {}
                if isinstance(data, dict) and "hooks" in data and isinstance(data["hooks"], dict):
                    modified = False
                    for ev in list(data["hooks"].keys()):
                        ev_list = data["hooks"][ev]
                        if isinstance(ev_list, list):
                            new_list = [h for h in ev_list if isinstance(h, dict) and "along_hook.py" not in str(h.get("command", ""))]
                            if len(new_list) != len(ev_list):
                                modified = True
                                if new_list:
                                    data["hooks"][ev] = new_list
                                else:
                                    del data["hooks"][ev]
                    if modified:
                        if not data["hooks"]:
                            del data["hooks"]
                        if not data:
                            if not dry_run:
                                os.remove(claude_settings)
                            actions.append(f"removed {claude_settings}")
                            # Note: preserve .claude directory to protect active Claude processes
                        else:
                            if not dry_run:
                                textio.write_text(claude_settings, json.dumps(data, indent=2) + "\n", newline="\n")
                            actions.append(f"cleaned Along hooks from {claude_settings}")
            except (OSError, ValueError):
                pass

        # 3. Purge .codex/hooks.json
        codex_hooks = os.path.join(ctx, ".codex", "hooks.json")
        if os.path.isfile(codex_hooks):
            try:
                content = textio.read_text(codex_hooks, strict=False)
                data = json.loads(content) if content.strip() else {}
                if isinstance(data, dict):
                    hooks_dict = data.get("hooks", data)
                    modified = False
                    for ev in list(hooks_dict.keys()):
                        ev_list = hooks_dict[ev]
                        if isinstance(ev_list, list):
                            new_list = [h for h in ev_list if isinstance(h, dict) and "along_hook.py" not in str(h.get("command", ""))]
                            if len(new_list) != len(ev_list):
                                modified = True
                                if new_list:
                                    hooks_dict[ev] = new_list
                                else:
                                    del hooks_dict[ev]
                    if modified:
                        if "hooks" in data and not data["hooks"]:
                            del data["hooks"]
                        if not data or (len(data) == 1 and "hooks" in data and not data["hooks"]):
                            if not dry_run:
                                os.remove(codex_hooks)
                            actions.append(f"removed {codex_hooks}")
                            # Note: preserve .codex directory to protect active Codex processes
                        else:
                            if not dry_run:
                                textio.write_text(codex_hooks, json.dumps(data, indent=2) + "\n", newline="\n")
                            actions.append(f"cleaned Along hooks from {codex_hooks}")
            except (OSError, ValueError):
                pass

        # 4. Purge .cursor/hooks.json
        cursor_hooks = os.path.join(ctx, ".cursor", "hooks.json")
        if os.path.isfile(cursor_hooks):
            try:
                content = textio.read_text(cursor_hooks, strict=False)
                data = json.loads(content) if content.strip() else {}
                if isinstance(data, dict) and "hooks" in data and isinstance(data["hooks"], dict):
                    modified = False
                    for ev in list(data["hooks"].keys()):
                        ev_list = data["hooks"][ev]
                        if isinstance(ev_list, list):
                            new_list = [h for h in ev_list if isinstance(h, dict) and "along_hook.py" not in str(h.get("command", ""))]
                            if len(new_list) != len(ev_list):
                                modified = True
                                if new_list:
                                    data["hooks"][ev] = new_list
                                else:
                                    del data["hooks"][ev]
                    if modified:
                        if not data["hooks"]:
                            del data["hooks"]
                        keys_left = [k for k in data.keys() if k != "version"]
                        if not keys_left:
                            if not dry_run:
                                os.remove(cursor_hooks)
                            actions.append(f"removed {cursor_hooks}")
                            # Note: preserve .cursor directory to protect active Cursor processes
                        else:
                            if not dry_run:
                                textio.write_text(cursor_hooks, json.dumps(data, indent=2) + "\n", newline="\n")
                            actions.append(f"cleaned Along hooks from {cursor_hooks}")
            except (OSError, ValueError):
                pass

        # 5. Purge workaround scripts/along_hook.py or .along/scripts/along_hook.py in consumer repos
        if not repo.is_dev_repo(ctx):
            for candidate_script in [
                os.path.join(ctx, "scripts", "along_hook.py"),
                os.path.join(ctx, ".along", "scripts", "along_hook.py"),
            ]:
                if os.path.isfile(candidate_script):
                    try:
                        if not dry_run:
                            os.remove(candidate_script)
                        actions.append(f"removed workaround {candidate_script}")
                        s_dir = os.path.dirname(candidate_script)
                        if not dry_run and os.path.isdir(s_dir) and not os.listdir(s_dir):
                            os.rmdir(s_dir)
                            actions.append(f"removed empty directory {s_dir}")
                    except OSError:
                        pass

    return actions





