#!/usr/bin/env python3
"""alongkit.webdev.config - Configuration loading, validation, and secret masking for webdev."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .. import repo

CONFIG_FILENAME = "webdev.yaml"
ALONG_CONFIG_FILENAME = "along.yaml"

ENV_REF_RE = re.compile(r"^\$\{env:([A-Za-z0-9_]+)\}$")


def load_env_file(repo_root: str) -> Dict[str, str]:
    """Parse local .env file in repo root if present."""
    env_file = os.path.join(repo_root, ".env")
    result: Dict[str, str] = {}
    if not os.path.isfile(env_file):
        return result
    try:
        with open(env_file, "r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" in stripped:
                    key, val = stripped.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    result[key] = val
    except OSError:
        pass
    return result


def resolve_env_val(val: Any, env_dict: Dict[str, str]) -> Tuple[Any, bool]:
    """Resolve ${env:KEY} string value against env_dict or os.environ.

    Returns (resolved_value, is_secret).
    """
    if not isinstance(val, str):
        return val, False
    match = ENV_REF_RE.match(val.strip())
    if match:
        key = match.group(1)
        resolved = env_dict.get(key) or os.environ.get(key, "")
        return resolved, True
    return val, False


def mask_secret(key: str) -> str:
    """Mask reference name for safe logging and output."""
    return f"***{key}***"


def mask_env_dict(env_spec: Dict[str, Any]) -> Dict[str, str]:
    """Return dictionary with ${env:KEY} values replaced by ***KEY***."""
    masked: Dict[str, str] = {}
    for k, v in env_spec.items():
        if isinstance(v, str):
            match = ENV_REF_RE.match(v.strip())
            if match:
                masked[k] = mask_secret(match.group(1))
                continue
        masked[k] = str(v)
    return masked


class ServiceConfig:
    """Parsed and validated service configuration."""

    def __init__(
        self,
        name: str,
        command: Optional[str] = None,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, Any]] = None,
        probe: Optional[Dict[str, Any]] = None,
        noise: Optional[List[str]] = None,
        fatal: Optional[List[str]] = None,
        kind: str = "default",
        static_root: Optional[str] = None,
        static_port: Optional[int] = None,
    ):
        self.name = name
        self.command = command or ""
        self.cwd = cwd or ""
        self.raw_env = env or {}
        self.probe = probe or {}
        self.noise = noise or []
        self.fatal = fatal or []
        self.kind = kind
        self.static_root = static_root
        self.static_port = static_port


class WebdevConfig:
    """Parsed .along/webdev.yaml configuration."""

    def __init__(
        self,
        services: Dict[str, ServiceConfig],
        defaults: Dict[str, Any],
        raw: Dict[str, Any],
    ):
        self.services = services
        self.defaults = defaults
        self.raw = raw
        self.origins: List[str] = list(defaults.get("origins") or [])


def parse_webdev_config(data: Dict[str, Any], repo_root: str) -> WebdevConfig:
    """Validate and construct WebdevConfig from parsed YAML dictionary."""
    services_dict: Dict[str, ServiceConfig] = {}
    raw_services = data.get("services") or {}

    for name, s_data in raw_services.items():
        if not isinstance(s_data, dict):
            continue
        kind = str(s_data.get("kind") or "default").lower()
        cmd = s_data.get("command")
        cwd = s_data.get("cwd")
        env_map = s_data.get("env") or {}
        probe = s_data.get("probe") or {}
        noise = list(s_data.get("noise") or [])
        fatal = list(s_data.get("fatal") or [])

        static_root = s_data.get("root")
        static_port = s_data.get("port")
        if kind == "static" and static_port is not None:
            try:
                static_port = int(static_port)
            except ValueError:
                static_port = None

        svc = ServiceConfig(
            name=name,
            command=cmd,
            cwd=cwd,
            env=env_map,
            probe=probe,
            noise=noise,
            fatal=fatal,
            kind=kind,
            static_root=static_root,
            static_port=static_port,
        )
        services_dict[name] = svc

    defaults = data.get("defaults") or {}
    return WebdevConfig(services=services_dict, defaults=defaults, raw=data)


def load_config(repo_root: Optional[str] = None) -> WebdevConfig:
    """Load webdev configuration from .along/webdev.yaml or along.yaml."""
    root = repo_root or repo.find_repo_root()
    import ruamel.yaml

    yaml = ruamel.yaml.YAML(typ="safe")

    state_cfg = os.path.join(repo.state_dir(root), CONFIG_FILENAME)
    if os.path.isfile(state_cfg):
        try:
            with open(state_cfg, "r", encoding="utf-8") as handle:
                parsed = yaml.load(handle) or {}
                if isinstance(parsed, dict):
                    return parse_webdev_config(parsed, root)
        except (OSError, ruamel.yaml.YAMLError):
            pass

    along_yaml = os.path.join(root, ALONG_CONFIG_FILENAME)
    if os.path.isfile(along_yaml):
        try:
            with open(along_yaml, "r", encoding="utf-8") as handle:
                parsed = yaml.load(handle) or {}
                if isinstance(parsed, dict) and "webdev" in parsed:
                    return parse_webdev_config(parsed["webdev"], root)
        except (OSError, ruamel.yaml.YAMLError):
            pass

    return WebdevConfig(services={}, defaults={}, raw={})
