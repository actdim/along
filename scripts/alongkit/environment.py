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

import io
import os
import re
import shutil
import sys
from typing import Any, Dict, List, Optional, Union

from . import bootstrap, proc, textio

DEFAULT_IMAGE = "actdim/along-autonomous:latest"
DEFAULT_RUNTIMES = ["claude-code", "opencode"]

ENV_YAML_NAME = "env.yaml"
SECRETS_ENV_NAME = "secrets.env"
COMPOSE_YAML_NAME = "compose.yaml"

ENV_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")
HOST_RE = re.compile(r"^[A-Za-z0-9.-]+$")
CIDR_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+(/[0-9]+)?$")
RUNTIME_RE = re.compile(r"^[a-z0-9-]+$")

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


class EnvConfigError(ValueError):
    """Raised when an env.yaml configuration file is malformed or invalid."""


def validate_env_name(name: str) -> str:
    """Validate environment name for compose project, directory, and container safety."""
    if not name or not isinstance(name, str):
        raise ValueError("Environment name cannot be empty.")
    if not ENV_NAME_RE.match(name):
        raise ValueError(
            f"Invalid environment name '{name}'. Must match ^[a-z0-9][a-z0-9_-]{{0,62}}$ "
            "(lowercase alphanumeric, hyphens, underscores; max 63 chars)."
        )
    return name


def validate_egress_host(host: str) -> str:
    """Validate host name or IPv4 CIDR for firewall allowlist."""
    if not host or not isinstance(host, str):
        raise ValueError("Egress host cannot be empty.")
    h = host.strip()
    if not (HOST_RE.match(h) or CIDR_RE.match(h)):
        raise ValueError(f"Invalid egress host or CIDR: '{host}'")
    return h


def _dump_yaml(data: Any) -> str:
    """Dump data structure to clean YAML using ruamel.yaml round-trip mode."""
    ruamel = bootstrap.require("ruamel.yaml")
    yaml = ruamel.YAML(typ="rt")
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    stream = io.StringIO()
    yaml.dump(data, stream)
    return stream.getvalue()


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
    validate_env_name(name)
    if base_dir:
        norm = os.path.normpath(os.path.abspath(base_dir))
        if os.path.basename(norm) == name:
            return norm
        return os.path.join(norm, name)
    return os.path.join(get_default_base_dir(), name)


def load_env_config(env_dir: str) -> Dict[str, Any]:
    """Load env.yaml from target environment directory, strictly validating schema."""
    env_file = os.path.join(env_dir, ENV_YAML_NAME)
    if not os.path.exists(env_file):
        raise FileNotFoundError(f"Missing {ENV_YAML_NAME} in {env_dir}")

    ruamel = bootstrap.require("ruamel.yaml")
    try:
        yaml = ruamel.YAML(typ="safe")
        content = textio.read_text(env_file, strict=False)
        data = yaml.load(content)
    except ruamel.error.YAMLError as exc:
        raise EnvConfigError(f"Malformed {ENV_YAML_NAME} in {env_file}: {exc}") from exc
    except (OSError, ValueError) as exc:
        raise EnvConfigError(f"Error reading {ENV_YAML_NAME} in {env_file}: {exc}") from exc

    if not isinstance(data, dict):
        raise EnvConfigError(f"Invalid {ENV_YAML_NAME} in {env_file}: document must be a mapping")

    name = data.get("name") or os.path.basename(os.path.normpath(env_dir))
    try:
        name = validate_env_name(str(name))
    except ValueError as exc:
        raise EnvConfigError(f"Invalid 'name' in {env_file}: {exc}") from exc

    repo_url = data.get("repo")
    if repo_url is None:
        repo_url = ""
    elif not isinstance(repo_url, str):
        raise EnvConfigError(f"Invalid 'repo' in {env_file}: must be a string")

    branch = data.get("branch")
    if branch is None:
        branch = "main"
    elif not isinstance(branch, str):
        raise EnvConfigError(f"Invalid 'branch' in {env_file}: must be a string")

    runtimes = data.get("runtimes")
    if runtimes is None:
        runtimes = list(DEFAULT_RUNTIMES)
    elif not isinstance(runtimes, list) or not all(isinstance(r, str) for r in runtimes):
        raise EnvConfigError(f"Invalid 'runtimes' in {env_file}: must be a list of strings")

    telegram_chat_id = data.get("telegram_chat_id")
    if telegram_chat_id is None:
        telegram_chat_id = ""
    elif not isinstance(telegram_chat_id, (str, int)):
        raise EnvConfigError(f"Invalid 'telegram_chat_id' in {env_file}: must be a string or integer")
    telegram_chat_id = str(telegram_chat_id)

    raw_egress = data.get("egress_allowlist")
    if raw_egress is None:
        egress_allowlist = []
    elif not isinstance(raw_egress, list) or not all(isinstance(h, str) for h in raw_egress):
        raise EnvConfigError(f"Invalid 'egress_allowlist' in {env_file}: must be a list of strings")
    else:
        egress_allowlist = []
        for h in raw_egress:
            try:
                egress_allowlist.append(validate_egress_host(h))
            except ValueError as exc:
                raise EnvConfigError(f"Invalid egress host in {env_file}: {exc}") from exc

    image = data.get("image")
    if image is None:
        image = DEFAULT_IMAGE
    elif not isinstance(image, str):
        raise EnvConfigError(f"Invalid 'image' in {env_file}: must be a string")

    gvisor = data.get("gvisor")
    if gvisor is None:
        gvisor = False
    elif not isinstance(gvisor, bool):
        raise EnvConfigError(f"Invalid 'gvisor' in {env_file}: must be a boolean")

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

    name = validate_env_name(config.get("name") or os.path.basename(os.path.normpath(env_dir)))
    repo_url = str(config.get("repo") or "")
    branch = str(config.get("branch") or "main")

    runtimes = config.get("runtimes")
    if runtimes is None:
        runtimes = list(DEFAULT_RUNTIMES)
    elif not isinstance(runtimes, list):
        raise ValueError("runtimes must be a list")

    telegram_chat_id = str(config.get("telegram_chat_id") or "")

    raw_egress = config.get("egress_allowlist")
    if raw_egress is None:
        egress_allowlist = []
    elif not isinstance(raw_egress, list):
        raise ValueError("egress_allowlist must be a list")
    else:
        egress_allowlist = [validate_egress_host(h) for h in raw_egress]

    image = str(config.get("image") or DEFAULT_IMAGE)
    gvisor = bool(config.get("gvisor", False))

    data: Dict[str, Any] = {
        "name": name,
        "repo": repo_url,
        "branch": branch,
        "runtimes": runtimes,
        "telegram_chat_id": telegram_chat_id,
        "egress_allowlist": egress_allowlist,
        "gvisor": gvisor,
    }
    if image != DEFAULT_IMAGE:
        data["image"] = image

    content = _dump_yaml(data)
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


def generate_compose_yaml(config: Dict[str, Any]) -> str:
    """Deterministically generate compose.yaml specification from configuration."""
    name = validate_env_name(config.get("name") or "env")
    image = str(config.get("image") or DEFAULT_IMAGE)
    repo_url = str(config.get("repo") or "")
    branch = str(config.get("branch") or "main")
    runtimes = config.get("runtimes") or list(DEFAULT_RUNTIMES)
    telegram_chat_id = str(config.get("telegram_chat_id") or "")
    raw_egress = config.get("egress_allowlist") or []
    egress_allowlist = [validate_egress_host(h) for h in raw_egress]
    gvisor = bool(config.get("gvisor", False))

    runtimes_csv = ",".join(runtimes)
    egress_csv = ",".join(egress_allowlist)

    env_mapping: Dict[str, str] = {
        "ALONG_ENV_NAME": name,
        "ALONG_AUTONOMOUS": "1",
        "ALONG_REPO_URL": repo_url,
        "ALONG_REPO_BRANCH": branch,
        "ALONG_RUNTIMES": runtimes_csv,
    }
    if egress_csv:
        env_mapping["ALONG_EXTRA_EGRESS"] = egress_csv
    if telegram_chat_id:
        env_mapping["TELEGRAM_CHAT_ID"] = telegram_chat_id

    runner_service: Dict[str, Any] = {
        "image": image,
        "container_name": f"along-{name}",
        "init": True,
        "restart": "unless-stopped",
        "security_opt": ["no-new-privileges:true"],
        "sysctls": {
            "net.ipv6.conf.all.disable_ipv6": 1,
        },
        "cap_add": ["NET_ADMIN"],
    }
    if gvisor:
        runner_service["runtime"] = "runsc"

    runner_service["env_file"] = ["secrets.env"]
    runner_service["environment"] = env_mapping
    runner_service["volumes"] = [
        "repo:/workspace",
        "claude_auth:/home/along/.claude",
        "opencode_auth:/home/along/.opencode",
        "cache:/home/along/.cache",
    ]

    compose_dict: Dict[str, Any] = {
        "services": {
            "runner": runner_service,
        },
        "volumes": {
            "repo": None,
            "claude_auth": None,
            "opencode_auth": None,
            "cache": None,
        },
    }

    yaml_str = _dump_yaml(compose_dict)
    header = "# Generated by Along (along env) - do not edit by hand\n"
    return header + yaml_str


def write_compose_file(env_dir: str, config: Dict[str, Any]) -> str:
    """Write compose.yaml in target environment directory."""
    os.makedirs(env_dir, exist_ok=True)
    compose_file = os.path.join(env_dir, COMPOSE_YAML_NAME)
    content = generate_compose_yaml(config)
    textio.write_text(compose_file, content)
    return compose_file


def get_docker_cmd() -> Optional[str]:
    """Find docker executable if present in PATH."""
    return shutil.which("docker")


def get_docker_compose_cmd() -> Optional[List[str]]:
    """Determine available docker compose invocation command."""
    docker_bin = shutil.which("docker")
    if docker_bin:
        res = proc.run_capture([docker_bin, "compose", "version"])
        if res.returncode == 0:
            return [docker_bin, "compose"]

    compose_bin = shutil.which("docker-compose")
    if compose_bin:
        return [compose_bin]

    return None


def get_container_status(container_name: str) -> str:
    """Inspect running container status using docker CLI."""
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return "configured (docker not found)"

    res = proc.run_capture(
        [docker_bin, "ps", "-a", "--filter", f"name=^/{container_name}$", "--format", "{{.State}}"]
    )
    if res.returncode != 0:
        return "unknown"
    out = res.stdout.strip().lower()
    if not out:
        return "not_created"
    if out in ("exited", "dead"):
        return "stopped"
    return out


def env_up(
    name: str,
    repo_url: Optional[str] = None,
    branch: Optional[str] = None,
    base_dir: Optional[str] = None,
    run_compose: bool = True,
) -> Dict[str, Any]:
    """Create and start isolated environment."""
    validate_env_name(name)
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
            res = proc.run_capture(cmd, cwd=env_dir)
            if res.returncode == 0:
                started = True
            else:
                error_msg = res.stderr.strip() or f"docker compose up failed with code {res.returncode}"
        else:
            error_msg = "Docker or docker compose not found in PATH."

    container_status = get_container_status(container_name) if started else ("error" if error_msg else "configured")

    return {
        "name": name,
        "path": env_dir,
        "container_name": container_name,
        "started": started,
        "status": container_status,
        "error": error_msg,
    }


def env_down(
    name: str,
    base_dir: Optional[str] = None,
    run_compose: bool = True,
) -> Dict[str, Any]:
    """Stop isolated environment container while preserving persistent files and volumes."""
    validate_env_name(name)
    env_dir = resolve_env_dir(name, base_dir)
    if not os.path.exists(env_dir):
        raise FileNotFoundError(f"Environment directory not found: {env_dir}")

    container_name = f"along-{name}"
    compose_file = os.path.join(env_dir, COMPOSE_YAML_NAME)
    compose_cmd = get_docker_compose_cmd()
    stopped = False
    error_msg = None

    if run_compose:
        if compose_cmd and os.path.exists(compose_file):
            cmd = compose_cmd + ["-f", compose_file, "down"]
            res = proc.run_capture(cmd, cwd=env_dir)
            if res.returncode == 0:
                stopped = True
            else:
                error_msg = res.stderr.strip() or f"docker compose down failed with exit code {res.returncode}"
        else:
            docker_bin = shutil.which("docker")
            if docker_bin:
                res = proc.run_capture([docker_bin, "stop", container_name])
                if res.returncode == 0:
                    stopped = True
                else:
                    error_msg = res.stderr.strip() or f"docker stop failed with exit code {res.returncode}"
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
        validate_env_name(name)
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
            try:
                env_res = env_status(name=entry, base_dir=root)
                if isinstance(env_res, dict):
                    results.append(env_res)
            except ValueError:
                continue

    return results


def env_logs(
    name: str,
    follow: bool = False,
    tail: Optional[int] = None,
    base_dir: Optional[str] = None,
) -> int:
    """Stream container logs using docker compose logs."""
    validate_env_name(name)
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
    validate_env_name(name)
    env_dir = resolve_env_dir(name, base_dir)
    compose_file = os.path.join(env_dir, COMPOSE_YAML_NAME)
    compose_cmd = get_docker_compose_cmd()

    if not compose_cmd or not os.path.exists(compose_file):
        docker_bin = shutil.which("docker")
        if docker_bin:
            cmd = [docker_bin, "exec", "-it", "-u", "along", f"along-{name}", "/bin/bash"]
            return proc.run_passthrough(cmd, cwd=env_dir)
        sys.stderr.write("[Error] Docker or docker compose not found in PATH.\n")
        return 1

    cmd = compose_cmd + ["-f", compose_file, "exec", "-u", "along", "runner", "/bin/bash"]
    return proc.run_passthrough(cmd, cwd=env_dir)


def env_update(
    name: str,
    base_dir: Optional[str] = None,
    run_compose: bool = True,
) -> Dict[str, Any]:
    """Pull latest container image and refresh running environment."""
    validate_env_name(name)
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
            up_cmd = compose_cmd + ["-f", compose_file, "up", "-d"]
            res_pull = proc.run_capture(pull_cmd, cwd=env_dir)
            if res_pull.returncode != 0:
                error_msg = res_pull.stderr.strip() or f"docker compose pull failed with exit code {res_pull.returncode}"
            else:
                res = proc.run_capture(up_cmd, cwd=env_dir)
                if res.returncode == 0:
                    updated = True
                else:
                    error_msg = res.stderr.strip() or f"docker compose up failed with exit code {res.returncode}"
        else:
            error_msg = "Docker or docker compose not found in PATH."

    return {
        "name": name,
        "path": env_dir,
        "updated": updated,
        "status": "running" if updated else "unknown",
        "error": error_msg,
    }
