#!/usr/bin/env python3
"""
alongkit.environment - Isolated Docker Environment Manager for Along Protocol.

Manages dedicated Docker containers for autonomous agent runs on a VPS or host:
- Provisions host folder structure under /srv/along/envs/<name>/ (or --dir)
- Manages concise env.yaml (under 20 lines) and template secrets.env
- Generates deterministic compose.yaml with dedicated isolation volumes
- Enforces egress firewall allowlist and restart: unless-stopped lifecycle
- Dispatches docker compose commands for up, down, status, logs, shell, update
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along env --help   (or: python scripts/along_exec.py env --help)"
    )

import json
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

from . import bootstrap, proc, repo, textio

DEFAULT_IMAGE = "actdim/along-autonomous:latest"
DEFAULT_RUNTIMES = ["claude-code", "opencode"]
DEFAULT_EGRESS_ALLOWLIST = [
    "api.anthropic.com",
    "api.openai.com",
    "generativelanguage.googleapis.com",
    "github.com",
    "pypi.org",
    "files.pythonhosted.org",
    "registry.npmjs.org",
    "api.telegram.org",
]
DEFAULT_VOLUMES = ["repo", "claude_auth", "opencode_auth", "cache"]

ENV_YAML_NAME = "env.yaml"
SECRETS_ENV_NAME = "secrets.env"
COMPOSE_YAML_NAME = "compose.yaml"

SECRETS_TEMPLATE = """# Model API Keys (per-VPS keys with spend limits recommended)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GEMINI_API_KEY=

# Git Repository Credentials (fine-grained repo-scoped token)
GITHUB_TOKEN=

# Telegram Alerts & Interventions
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Autonomous Execution Mode
ALONG_AUTONOMOUS=1
"""


def get_default_base_dir() -> str:
    """Return default base directory for along environments."""
    env_override = os.environ.get("ALONG_ENVS_DIR")
    if env_override:
        return os.path.abspath(env_override)
    if os.name == "nt":
        return os.path.join(os.path.expanduser("~"), ".along", "envs")
    if os.path.exists("/srv/along/envs") or (os.path.exists("/srv") and os.access("/srv", os.W_OK)):
        return "/srv/along/envs"
    return os.path.join(os.path.expanduser("~"), ".along", "envs")


def resolve_env_dir(name: str, base_dir: Optional[str] = None) -> str:
    """Resolve absolute directory for an environment by name."""
    if not name or name.strip() == "":
        raise ValueError("Environment name cannot be empty.")
    if base_dir:
        norm = os.path.normpath(os.path.abspath(base_dir))
        if os.path.basename(norm) == name:
            return norm
        return os.path.join(norm, name)
    return os.path.join(get_default_base_dir(), name)


def load_env_config(env_dir: str) -> Dict[str, Any]:
    """Load env.yaml from target environment directory, filling defaults."""
    env_file = os.path.join(env_dir, ENV_YAML_NAME)
    if not os.path.exists(env_file):
        raise FileNotFoundError(f"Missing {ENV_YAML_NAME} in {env_dir}")

    try:
        ruamel = bootstrap.require("ruamel.yaml")
        yaml = ruamel.YAML(typ="safe")
        content = textio.read_text(env_file, strict=False)
        data = yaml.load(content) or {}
    except (OSError, ValueError):
        data = {}

    name = data.get("name") or os.path.basename(os.path.normpath(env_dir))
    repo_url = data.get("repo") or ""
    branch = data.get("branch") or "main"
    runtimes = data.get("runtimes") or list(DEFAULT_RUNTIMES)
    telegram_chat_id = data.get("telegram_chat_id") or ""
    egress_allowlist = data.get("egress_allowlist") or []
    image = data.get("image") or DEFAULT_IMAGE
    gvisor = bool(data.get("gvisor", False))

    return {
        "name": name,
        "repo": repo_url,
        "branch": branch,
        "runtimes": runtimes,
        "telegram_chat_id": telegram_chat_id,
        "egress_allowlist": egress_allowlist,
        "image": image,
        "gvisor": gvisor,
    }


def save_env_config(env_dir: str, config: Dict[str, Any]) -> str:
    """Save concise env.yaml (under 20 lines) in target environment directory."""
    os.makedirs(env_dir, exist_ok=True)
    env_file = os.path.join(env_dir, ENV_YAML_NAME)

    name = config.get("name") or os.path.basename(os.path.normpath(env_dir))
    repo_url = config.get("repo") or ""
    branch = config.get("branch") or "main"
    runtimes = config.get("runtimes") or list(DEFAULT_RUNTIMES)
    telegram_chat_id = config.get("telegram_chat_id") or ""
    egress_allowlist = config.get("egress_allowlist") or []
    image = config.get("image") or DEFAULT_IMAGE
    gvisor = bool(config.get("gvisor", False))

    lines = [
        f"name: {name}",
        f"repo: \"{repo_url}\"",
        f"branch: \"{branch}\"",
        "runtimes:",
    ]
    for r in runtimes:
        lines.append(f"  - {r}")
    lines.append(f"telegram_chat_id: \"{telegram_chat_id}\"")
    if egress_allowlist:
        lines.append("egress_allowlist:")
        for host in egress_allowlist:
            lines.append(f"  - {host}")
    else:
        lines.append("egress_allowlist: []")
    lines.append(f"gvisor: {'true' if gvisor else 'false'}")
    if image != DEFAULT_IMAGE:
        lines.append(f"image: \"{image}\"")
    lines.append("")

    content = "\n".join(lines)
    textio.write_text(env_file, content)
    return env_file


def ensure_secrets_file(env_dir: str) -> str:
    """Create secrets.env template if it does not already exist."""
    os.makedirs(env_dir, exist_ok=True)
    secrets_file = os.path.join(env_dir, SECRETS_ENV_NAME)
    if not os.path.exists(secrets_file):
        textio.write_text(secrets_file, SECRETS_TEMPLATE)
        if os.name != "nt":
            try:
                os.chmod(secrets_file, 0o600)
            except OSError:
                pass
    return secrets_file


def generate_compose_yaml(config: Dict[str, Any], env_dir: Optional[str] = None) -> str:
    """Deterministically generate compose.yaml specification from configuration."""
    name = config.get("name") or "env"
    image = config.get("image") or DEFAULT_IMAGE
    repo_url = config.get("repo") or ""
    branch = config.get("branch") or "main"
    runtimes = config.get("runtimes") or list(DEFAULT_RUNTIMES)
    telegram_chat_id = config.get("telegram_chat_id") or ""
    egress_allowlist = config.get("egress_allowlist") or []
    gvisor = bool(config.get("gvisor", False))

    runtimes_csv = ",".join(runtimes)
    egress_csv = ",".join(egress_allowlist)

    lines = [
        "# Generated by Along (along env) - do not edit by hand",
        "services:",
        "  runner:",
        f"    image: {image}",
        f"    container_name: along-{name}",
        "    restart: unless-stopped",
        "    cap_add:",
        "      - NET_ADMIN",
    ]

    if gvisor:
        lines.append("    runtime: runsc")

    lines.extend([
        "    env_file:",
        "      - secrets.env",
        "    environment:",
        f"      - ALONG_ENV_NAME={name}",
        "      - ALONG_AUTONOMOUS=1",
        f"      - ALONG_REPO_URL={repo_url}",
        f"      - ALONG_REPO_BRANCH={branch}",
        f"      - ALONG_RUNTIMES={runtimes_csv}",
    ])

    if egress_csv:
        lines.append(f"      - ALONG_EXTRA_EGRESS={egress_csv}")
    if telegram_chat_id:
        lines.append(f"      - TELEGRAM_CHAT_ID={telegram_chat_id}")

    lines.extend([
        "    volumes:",
        "      - repo:/workspace",
        "      - claude_auth:/home/along/.claude",
        "      - opencode_auth:/home/along/.opencode",
        "      - cache:/home/along/.cache",
        "",
        "volumes:",
        "  repo:",
        "  claude_auth:",
        "  opencode_auth:",
        "  cache:",
        "",
    ])

    return "\n".join(lines)


def write_compose_file(env_dir: str, config: Dict[str, Any]) -> str:
    """Write compose.yaml in target environment directory."""
    os.makedirs(env_dir, exist_ok=True)
    compose_file = os.path.join(env_dir, COMPOSE_YAML_NAME)
    content = generate_compose_yaml(config, env_dir=env_dir)
    textio.write_text(compose_file, content)
    return compose_file


def get_docker_cmd() -> Optional[str]:
    """Find docker executable if present in PATH."""
    return shutil.which("docker")


def get_docker_compose_cmd() -> Optional[List[str]]:
    """Determine available docker compose invocation command."""
    docker_bin = shutil.which("docker")
    if docker_bin:
        try:
            res = subprocess.run([docker_bin, "compose", "version"],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL,
                                 check=False)
            if res.returncode == 0:
                return [docker_bin, "compose"]
        except (OSError, ValueError):
            pass

    compose_bin = shutil.which("docker-compose")
    if compose_bin:
        return [compose_bin]

    return None


def get_container_status(container_name: str) -> str:
    """Inspect running container status using docker CLI."""
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return "configured (docker not found)"

    try:
        res = subprocess.run(
            [docker_bin, "ps", "-a", "--filter", f"name=^/{container_name}$", "--format", "{{.Status}}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        out = res.stdout.strip().lower()
        if not out:
            return "not_created"
        if "up" in out:
            return "running"
        if "exited" in out or "dead" in out:
            return "stopped"
        return out
    except (OSError, ValueError):
        return "unknown"


def env_up(
    name: str,
    repo_url: Optional[str] = None,
    branch: Optional[str] = None,
    base_dir: Optional[str] = None,
    run_compose: bool = True,
) -> Dict[str, Any]:
    """Create and start isolated environment."""
    env_dir = resolve_env_dir(name, base_dir)
    os.makedirs(env_dir, exist_ok=True)

    env_yaml = os.path.join(env_dir, ENV_YAML_NAME)
    if os.path.exists(env_yaml):
        config = load_env_config(env_dir)
        if repo_url:
            config["repo"] = repo_url
        if branch:
            config["branch"] = branch
    else:
        config = {
            "name": name,
            "repo": repo_url or "",
            "branch": branch or "main",
            "runtimes": list(DEFAULT_RUNTIMES),
            "telegram_chat_id": "",
            "egress_allowlist": [],
            "image": DEFAULT_IMAGE,
            "gvisor": False,
        }

    save_env_config(env_dir, config)
    ensure_secrets_file(env_dir)
    write_compose_file(env_dir, config)

    compose_cmd = get_docker_compose_cmd()
    compose_file = os.path.join(env_dir, COMPOSE_YAML_NAME)
    container_name = f"along-{name}"

    started = False
    error_msg = None

    if run_compose:
        if compose_cmd:
            cmd = compose_cmd + ["-f", compose_file, "up", "-d"]
            try:
                res = subprocess.run(cmd, cwd=env_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if res.returncode == 0:
                    started = True
                else:
                    error_msg = res.stderr.strip()
            except (OSError, ValueError) as exc:
                error_msg = str(exc)
        else:
            error_msg = "Docker or docker compose not found in PATH."

    container_status = get_container_status(container_name) if started else ("error" if error_msg else "configured")

    return {
        "name": name,
        "path": env_dir,
        "container_name": container_name,
        "status": container_status,
        "started": started,
        "error": error_msg,
        "config": config,
    }


def env_down(
    name: str,
    base_dir: Optional[str] = None,
    run_compose: bool = True,
) -> Dict[str, Any]:
    """Stop running container while preserving persistent volumes and configuration."""
    env_dir = resolve_env_dir(name, base_dir)
    if not os.path.exists(env_dir):
        raise FileNotFoundError(f"Environment directory not found: {env_dir}")

    compose_file = os.path.join(env_dir, COMPOSE_YAML_NAME)
    container_name = f"along-{name}"
    compose_cmd = get_docker_compose_cmd()

    stopped = False
    error_msg = None

    if run_compose:
        if compose_cmd and os.path.exists(compose_file):
            cmd = compose_cmd + ["-f", compose_file, "down"]
            try:
                res = subprocess.run(cmd, cwd=env_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if res.returncode == 0:
                    stopped = True
                else:
                    error_msg = res.stderr.strip()
            except (OSError, ValueError) as exc:
                error_msg = str(exc)
        else:
            docker_bin = shutil.which("docker")
            if docker_bin:
                try:
                    subprocess.run([docker_bin, "stop", container_name],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                    stopped = True
                except (OSError, ValueError) as exc:
                    error_msg = str(exc)
            else:
                error_msg = "Docker or docker compose not found in PATH."

    return {
        "name": name,
        "path": env_dir,
        "container_name": container_name,
        "stopped": stopped,
        "status": "stopped" if stopped else "unknown",
        "error": error_msg,
    }


def env_status(
    name: Optional[str] = None,
    base_dir: Optional[str] = None,
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """Return status dictionary for a specific environment or list all environments."""
    if name:
        env_dir = resolve_env_dir(name, base_dir)
        container_name = f"along-{name}"
        if not os.path.exists(env_dir):
            return {
                "name": name,
                "path": env_dir,
                "status": "missing_directory",
                "container_name": container_name,
                "repo": "",
                "branch": "",
                "runtimes": [],
                "gvisor": False,
                "has_secrets": False,
                "has_compose": False,
            }

        has_secrets = os.path.exists(os.path.join(env_dir, SECRETS_ENV_NAME))
        has_compose = os.path.exists(os.path.join(env_dir, COMPOSE_YAML_NAME))

        try:
            config = load_env_config(env_dir)
        except (OSError, ValueError, FileNotFoundError):
            config = {"repo": "", "branch": "", "runtimes": [], "gvisor": False}

        status = get_container_status(container_name)

        return {
            "name": name,
            "path": env_dir,
            "status": status,
            "container_name": container_name,
            "repo": config.get("repo", ""),
            "branch": config.get("branch", ""),
            "runtimes": config.get("runtimes", []),
            "gvisor": config.get("gvisor", False),
            "has_secrets": has_secrets,
            "has_compose": has_compose,
        }

    # Scan base directory for all environments
    root = os.path.abspath(base_dir) if base_dir else get_default_base_dir()
    results: List[Dict[str, Any]] = []

    if not os.path.isdir(root):
        return results

    for entry in sorted(os.listdir(root)):
        sub = os.path.join(root, entry)
        if os.path.isdir(sub) and os.path.exists(os.path.join(sub, ENV_YAML_NAME)):
            env_res = env_status(name=entry, base_dir=root)
            if isinstance(env_res, dict):
                results.append(env_res)

    return results


def env_logs(
    name: str,
    follow: bool = False,
    tail: Optional[int] = None,
    base_dir: Optional[str] = None,
) -> int:
    """Stream container logs using docker compose logs."""
    env_dir = resolve_env_dir(name, base_dir)
    compose_file = os.path.join(env_dir, COMPOSE_YAML_NAME)
    compose_cmd = get_docker_compose_cmd()

    if not compose_cmd or not os.path.exists(compose_file):
        docker_bin = shutil.which("docker")
        if docker_bin:
            cmd = [docker_bin, "logs"]
            if follow:
                cmd.append("-f")
            if tail is not None:
                cmd.extend(["--tail", str(tail)])
            cmd.append(f"along-{name}")
            return proc.run_passthrough(cmd, cwd=env_dir)
        sys.stderr.write("[Error] Docker or docker compose not found in PATH.\n")
        return 1

    cmd = compose_cmd + ["-f", compose_file, "logs"]
    if follow:
        cmd.append("-f")
    if tail is not None:
        cmd.extend(["--tail", str(tail)])

    return proc.run_passthrough(cmd, cwd=env_dir)


def env_shell(
    name: str,
    base_dir: Optional[str] = None,
) -> int:
    """Open interactive shell inside running container."""
    env_dir = resolve_env_dir(name, base_dir)
    compose_file = os.path.join(env_dir, COMPOSE_YAML_NAME)
    compose_cmd = get_docker_compose_cmd()

    if not compose_cmd or not os.path.exists(compose_file):
        docker_bin = shutil.which("docker")
        if docker_bin:
            cmd = [docker_bin, "exec", "-it", f"along-{name}", "/bin/bash"]
            return proc.run_passthrough(cmd, cwd=env_dir)
        sys.stderr.write("[Error] Docker or docker compose not found in PATH.\n")
        return 1

    cmd = compose_cmd + ["-f", compose_file, "exec", "runner", "/bin/bash"]
    return proc.run_passthrough(cmd, cwd=env_dir)


def env_update(
    name: str,
    base_dir: Optional[str] = None,
    run_compose: bool = True,
) -> Dict[str, Any]:
    """Pull latest container image and refresh running environment."""
    env_dir = resolve_env_dir(name, base_dir)
    if not os.path.exists(env_dir):
        raise FileNotFoundError(f"Environment directory not found: {env_dir}")

    config = load_env_config(env_dir)
    write_compose_file(env_dir, config)

    compose_file = os.path.join(env_dir, COMPOSE_YAML_NAME)
    compose_cmd = get_docker_compose_cmd()
    updated = False
    error_msg = None

    if run_compose:
        if compose_cmd and os.path.exists(compose_file):
            pull_cmd = compose_cmd + ["-f", compose_file, "pull"]
            up_cmd = compose_cmd + ["-f", compose_file, "up", "-d", "--build"]
            try:
                subprocess.run(pull_cmd, cwd=env_dir, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False)
                res = subprocess.run(up_cmd, cwd=env_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                if res.returncode == 0:
                    updated = True
                else:
                    error_msg = res.stderr.strip()
            except (OSError, ValueError) as exc:
                error_msg = str(exc)
        else:
            error_msg = "Docker or docker compose not found in PATH."

    return {
        "name": name,
        "path": env_dir,
        "updated": updated,
        "status": "running" if updated else "unknown",
        "error": error_msg,
    }
