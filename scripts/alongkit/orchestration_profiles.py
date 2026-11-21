#!/usr/bin/env python3
"""
alongkit.orchestration_profiles - Declarative orchestration profile loader and schema validator.

Loads and validates named orchestration profiles from .along/orchestration/<name>.yaml
supporting direct, team-native, and cross-runtime execution modes across heterogeneous
agent harnesses (Claude Code, Codex, OpenCode, Antigravity).
"""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

import copy
import json
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

MODE_DIRECT: str = "direct"
MODE_TEAM_NATIVE: str = "team-native"
MODE_CROSS_RUNTIME: str = "cross-runtime"
VALID_MODES: Tuple[str, ...] = (MODE_DIRECT, MODE_TEAM_NATIVE, MODE_CROSS_RUNTIME)

WORKSPACE_INHERIT: str = "inherit"
WORKSPACE_WORKTREE: str = "worktree"
VALID_WORKSPACES: Tuple[str, ...] = (WORKSPACE_INHERIT, WORKSPACE_WORKTREE)

SUPPORTED_ROLES: Tuple[str, ...] = ("scout", "architect", "implementer", "reviewer")
VALID_RUNTIMES: Tuple[str, ...] = (
    "claude",
    "claude-code",
    "codex",
    "deepseek",
    "deepseek-harness",
    "dsh",
    "opencode",
    "generic",
)

PROFILES_DIR_NAME: str = "orchestration"
DEFAULT_TIMEOUT: int = 1800

BUILTIN_PROFILES: Dict[str, Dict[str, Any]] = {
    "direct": {
        "name": "direct",
        "description": "Default single-agent fast path",
        "mode": MODE_DIRECT,
        "workspace": WORKSPACE_INHERIT,
        "timeout": DEFAULT_TIMEOUT,
        "roles": {
            "scout": {"runtime": "claude-code"},
            "architect": {"runtime": "claude-code"},
            "implementer": {"runtime": "claude-code"},
            "reviewer": {"runtime": "claude-code"},
        },
    },
    "team-native": {
        "name": "team-native",
        "description": "Role-based state machine executing inside a single harness",
        "mode": MODE_TEAM_NATIVE,
        "workspace": WORKSPACE_INHERIT,
        "timeout": DEFAULT_TIMEOUT,
        "roles": {
            "scout": {"runtime": "claude-code"},
            "architect": {"runtime": "claude-code"},
            "implementer": {"runtime": "claude-code"},
            "reviewer": {"runtime": "claude-code"},
        },
    },
    "cross-tiered": {
        "name": "cross-tiered",
        "description": "Heterogeneous cross-runtime orchestration across multiple CLIs",
        "mode": MODE_CROSS_RUNTIME,
        "workspace": WORKSPACE_INHERIT,
        "timeout": DEFAULT_TIMEOUT,
        "roles": {
            "scout": {"runtime": "claude-code", "timeout": 600},
            "architect": {"runtime": "claude-code", "timeout": 900},
            "implementer": {"runtime": "opencode", "timeout": 1800},
            "reviewer": {"runtime": "claude-code", "timeout": 600},
        },
    },
}


def get_profiles_dir(repo_root: str) -> str:
    """Return the filesystem directory path for repository orchestration profiles."""
    return os.path.join(os.path.abspath(repo_root), ".along", PROFILES_DIR_NAME)


def list_profile_names(repo_root: Optional[str] = None) -> List[str]:
    """List available profile names, combining repository directory profiles and builtins."""
    names: Set[str] = set(BUILTIN_PROFILES.keys())
    if repo_root and os.path.isdir(repo_root):
        pdir = get_profiles_dir(repo_root)
        if os.path.isdir(pdir):
            for entry in os.listdir(pdir):
                if entry.endswith((".yaml", ".yml", ".json")):
                    base = os.path.splitext(entry)[0]
                    if base:
                        names.add(base)
    return sorted(names)


def validate_profile_dict(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a parsed profile dictionary against Along schema rules."""
    errors: List[str] = []
    if not isinstance(data, dict):
        return False, ["Profile must be a dictionary/mapping object"]

    name = data.get("name")
    if not name or not isinstance(name, str):
        errors.append("Profile missing required non-empty string 'name'")

    mode = data.get("mode", MODE_DIRECT)
    if mode not in VALID_MODES:
        errors.append(f"Invalid mode '{mode}'. Expected one of: {list(VALID_MODES)}")

    workspace = data.get("workspace", WORKSPACE_INHERIT)
    if workspace not in VALID_WORKSPACES:
        errors.append(f"Invalid workspace '{workspace}'. Expected one of: {list(VALID_WORKSPACES)}")

    roles = data.get("roles")
    runner = data.get("runner")

    if not roles and runner and isinstance(runner, dict):
        # Allow shorthand runner config for direct mode
        rt = runner.get("runtime", "claude-code")
        roles = {r: dict(runner) for r in SUPPORTED_ROLES}
        data["roles"] = roles

    if not isinstance(roles, dict):
        errors.append("Profile must specify a 'roles' mapping (or 'runner' mapping)")
    else:
        for r_name in SUPPORTED_ROLES:
            r_cfg = roles.get(r_name)
            if not r_cfg or not isinstance(r_cfg, dict):
                # Fallback to default runtime if missing in direct mode
                if mode == MODE_DIRECT:
                    roles[r_name] = {"runtime": "claude-code"}
                    continue
                errors.append(f"Missing configuration for required role '{r_name}'")
                continue
            rt = str(r_cfg.get("runtime", "")).strip().lower()
            if not rt:
                errors.append(f"Role '{r_name}' missing required 'runtime'")
            elif rt not in VALID_RUNTIMES:
                errors.append(f"Role '{r_name}' specifies invalid runtime '{rt}'. Expected one of: {list(VALID_RUNTIMES)}")

    return len(errors) == 0, errors


def load_profile_from_file(file_path: str) -> Dict[str, Any]:
    """Parse a profile from a YAML or JSON file."""
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Profile file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        raw = f.read()

    data: Optional[Dict[str, Any]] = None
    if file_path.endswith((".yaml", ".yml")):
        try:
            from . import bootstrap
            ruamel = bootstrap.require("ruamel.yaml")
            yaml = ruamel.YAML(typ="safe")
            data = yaml.load(raw)
        except Exception:
            # Fallback if json formatted
            try:
                data = json.loads(raw)
            except Exception as e:
                raise ValueError(f"Failed to parse YAML profile '{file_path}': {e}")
    else:
        data = json.loads(raw)

    if not isinstance(data, dict):
        raise ValueError(f"Profile content in '{file_path}' must be a YAML/JSON mapping")

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    if "name" not in data:
        data["name"] = base_name

    valid, errors = validate_profile_dict(data)
    if not valid:
        raise ValueError(f"Invalid profile in '{file_path}': {'; '.join(errors)}")

    return data


def resolve_orchestration_profile(
    name: Optional[str] = None,
    repo_root: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Resolve an orchestration profile by name from repository files, builtins, or defaults.
    Applies any CLI or execution overrides.
    """
    profile_data: Optional[Dict[str, Any]] = None
    clean_name = str(name).strip() if name else ""

    # Check repository default in along.yaml / config.yaml if name is not explicitly passed
    if not clean_name and repo_root and os.path.isdir(repo_root):
        candidates = [
            os.path.join(repo_root, ".along", "config.yaml"),
            os.path.join(repo_root, ".along", "config.json"),
            os.path.join(repo_root, "along.yaml"),
            os.path.join(repo_root, "along.json"),
        ]
        for cpath in candidates:
            if not os.path.isfile(cpath):
                continue
            try:
                with open(cpath, "r", encoding="utf-8") as f:
                    content = f.read()
                data: Optional[Dict[str, Any]] = None
                if cpath.endswith((".yaml", ".yml")):
                    from . import bootstrap
                    ruamel = bootstrap.require("ruamel.yaml")
                    yaml = ruamel.YAML(typ="safe")
                    data = yaml.load(content)
                else:
                    data = json.loads(content)
                if isinstance(data, dict):
                    orch = data.get("orchestration") or data.get("orchestrator")
                    if isinstance(orch, str) and orch.strip():
                        clean_name = orch.strip()
                        break
                    elif isinstance(orch, dict):
                        norm_roles: Dict[str, Dict[str, Any]] = {}
                        for r_name in SUPPORTED_ROLES:
                            val = orch.get(r_name)
                            if isinstance(val, str):
                                norm_roles[r_name] = {"runtime": val.strip(), "args": []}
                            elif isinstance(val, dict):
                                r_cfg = dict(val)
                                if "runtime" in r_cfg:
                                    r_cfg["runtime"] = str(r_cfg["runtime"]).strip()
                                if "args" in r_cfg and not isinstance(r_cfg["args"], list):
                                    r_cfg["args"] = [str(r_cfg["args"])]
                                norm_roles[r_name] = r_cfg
                        profile_data = {
                            "name": "config-custom",
                            "mode": MODE_CROSS_RUNTIME,
                            "workspace": WORKSPACE_INHERIT,
                            "roles": norm_roles,
                        }
                        break
            except (ValueError, OSError, KeyError, TypeError):
                continue

    if profile_data is None:
        if not clean_name:
            clean_name = "direct"

        # Search in .along/orchestration/
        if repo_root and os.path.isdir(repo_root):
            pdir = get_profiles_dir(repo_root)
            for ext in (".yaml", ".yml", ".json"):
                candidate = os.path.join(pdir, f"{clean_name}{ext}")
                if os.path.isfile(candidate):
                    profile_data = load_profile_from_file(candidate)
                    break

        # Search in built-ins
        if profile_data is None:
            if clean_name in BUILTIN_PROFILES:
                profile_data = copy.deepcopy(BUILTIN_PROFILES[clean_name])
            else:
                profile_data = copy.deepcopy(BUILTIN_PROFILES["direct"])
                profile_data["name"] = clean_name

    # Apply overrides
    if overrides:
        for r_name in SUPPORTED_ROLES:
            val = overrides.get(r_name)
            if val:
                if isinstance(val, str):
                    profile_data.setdefault("roles", {}).setdefault(r_name, {})["runtime"] = val.strip()
                elif isinstance(val, dict):
                    profile_data.setdefault("roles", {}).setdefault(r_name, {}).update(val)
        if overrides.get("model"):
            model_val = str(overrides["model"]).strip()
            for r_name in SUPPORTED_ROLES:
                profile_data.setdefault("roles", {}).setdefault(r_name, {})["model"] = model_val
        if overrides.get("timeout"):
            try:
                t_val = int(overrides["timeout"])
                profile_data["timeout"] = t_val
                for r_name in SUPPORTED_ROLES:
                    profile_data.setdefault("roles", {}).setdefault(r_name, {})["timeout"] = t_val
            except (ValueError, TypeError):
                pass
        if overrides.get("workspace"):
            ws_val = str(overrides["workspace"]).strip().lower()
            if ws_val in VALID_WORKSPACES:
                profile_data["workspace"] = ws_val
        if overrides.get("mode"):
            mode_val = str(overrides["mode"]).strip().lower()
            if mode_val in VALID_MODES:
                profile_data["mode"] = mode_val
        role_overrides = overrides.get("roles")
        if isinstance(role_overrides, dict):
            for r_name, r_cfg in role_overrides.items():
                if r_name in SUPPORTED_ROLES and isinstance(r_cfg, dict):
                    profile_data.setdefault("roles", {}).setdefault(r_name, {}).update(r_cfg)

    return profile_data
