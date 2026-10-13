#!/usr/bin/env python3
"""
alongkit.profiles - Gate strictness profiles per model tier.

Covers [feat--gate-strictness-profiles] REQ-1..REQ-6:
- Named profiles: 'strict', 'standard', 'light'.
- 'standard' is the behavior-preserving default.
- Active profile resolution priority:
  1. Active session binding/state (along start --profile <p> or active session)
  2. Environment variable: ALONG_PROFILE
  3. Tracked repository configuration (.along/config.json "profile" or "hooks.profile", or .along/config.yaml)
  4. Default: "standard"
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along doctor   (or: python scripts/along_exec.py doctor)"
    )

import json
import os
from typing import Any, Dict, Optional, Tuple

from . import repo, textio

PROFILE_STRICT = "strict"
PROFILE_STANDARD = "standard"
PROFILE_LIGHT = "light"

VALID_PROFILES: Tuple[str, ...] = (
    PROFILE_STRICT,
    PROFILE_STANDARD,
    PROFILE_LIGHT,
)

DEFAULT_PROFILE = PROFILE_STANDARD

SOURCE_SESSION = "session"
SOURCE_ENV = "env"
SOURCE_CONFIG = "config"
SOURCE_DEFAULT = "default"

VALID_SOURCES: Tuple[str, ...] = (
    SOURCE_SESSION,
    SOURCE_ENV,
    SOURCE_CONFIG,
    SOURCE_DEFAULT,
)


def validate_profile(profile: Optional[str]) -> str:
    """Validate and normalize profile name, raising ValueError on unknown profile."""
    if not profile:
        return DEFAULT_PROFILE
    norm = str(profile).strip().lower()
    if norm in VALID_PROFILES:
        return norm
    raise ValueError(f"Invalid profile '{profile}'. Valid profiles: {', '.join(VALID_PROFILES)}")


def normalize_profile(profile: Optional[str], default: str = DEFAULT_PROFILE) -> str:
    """Safe normalization returning fallback default instead of raising ValueError."""
    if not profile:
        return default
    norm = str(profile).strip().lower()
    return norm if norm in VALID_PROFILES else default


def load_config_profile(repo_root: Optional[str] = None) -> Optional[str]:
    """Read profile from .along/config.json or .along/config.yaml."""
    if not repo_root:
        repo_root = repo.find_repo_root()
    if not repo_root:
        return None

    state_dir = repo.state_dir(repo_root)

    # 1. Try .along/config.json
    json_path = os.path.join(state_dir, "config.json")
    if os.path.isfile(json_path):
        try:
            content = textio.read_text(json_path, strict=False)
            data = json.loads(content)
            if isinstance(data, dict):
                # Top-level "profile"
                prof = data.get("profile")
                if prof and str(prof).strip().lower() in VALID_PROFILES:
                    return str(prof).strip().lower()
                # Under "hooks": {"profile": ...}
                hooks_data = data.get("hooks", {})
                if isinstance(hooks_data, dict):
                    h_prof = hooks_data.get("profile")
                    if h_prof and str(h_prof).strip().lower() in VALID_PROFILES:
                        return str(h_prof).strip().lower()
        except (OSError, ValueError):
            pass

    # 2. Try .along/config.yaml
    yaml_path = os.path.join(state_dir, "config.yaml")
    if os.path.isfile(yaml_path):
        try:
            from . import bootstrap
            ruamel = bootstrap.require("ruamel.yaml")
            yaml = ruamel.YAML(typ="safe")
            content = textio.read_text(yaml_path, strict=False)
            data = yaml.load(content)
            if isinstance(data, dict):
                prof = data.get("profile")
                if prof and str(prof).strip().lower() in VALID_PROFILES:
                    return str(prof).strip().lower()
                hooks_data = data.get("hooks", {})
                if isinstance(hooks_data, dict):
                    h_prof = hooks_data.get("profile")
                    if h_prof and str(h_prof).strip().lower() in VALID_PROFILES:
                        return str(h_prof).strip().lower()
        except (OSError, ValueError):
            pass

    return None


def resolve_active_profile_with_source(
    repo_root: Optional[str] = None,
    session_key: Optional[str] = None,
) -> Tuple[str, str]:
    """Resolve active profile and its provenance source.

    Returns:
        (profile_name, source) where source is one of 'session', 'env', 'config', 'default'.
    """
    effective_root = repo_root or repo.find_repo_root()

    # 1. Active session binding / state
    if effective_root:
        from . import session
        key = session_key or session.current_session_key()
        session_prof = session.get_session_profile(effective_root, key=key)
        if session_prof and session_prof in VALID_PROFILES:
            return session_prof, SOURCE_SESSION

    # 2. Environment variable
    env_prof = os.environ.get("ALONG_PROFILE", "").strip().lower()
    if env_prof in VALID_PROFILES:
        return env_prof, SOURCE_ENV

    # 3. Tracked repository configuration
    cfg_prof = load_config_profile(effective_root)
    if cfg_prof in VALID_PROFILES:
        return cfg_prof, SOURCE_CONFIG

    # 4. Fallback default
    return DEFAULT_PROFILE, SOURCE_DEFAULT


def resolve_active_profile(
    repo_root: Optional[str] = None,
    session_key: Optional[str] = None,
) -> str:
    """Resolve active profile name."""
    prof, _source = resolve_active_profile_with_source(repo_root=repo_root, session_key=session_key)
    return prof
