#!/usr/bin/env python3
"""alongkit.webdev.services - Service lifecycle management, probes, log harvesting, and attachment."""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from .. import proc, repo
from . import config

STATE_FILENAME = "services.json"


def get_services_state_dir(repo_root: str) -> str:
    """Directory for ephemeral webdev service state and logs."""
    state_dir = os.path.join(repo.state_dir(repo_root), ".session", "webdev")
    os.makedirs(state_dir, exist_ok=True)
    return state_dir


def get_services_state_path(repo_root: str) -> str:
    """Path to services.json."""
    return os.path.join(get_services_state_dir(repo_root), STATE_FILENAME)


def get_services_log_dir(repo_root: str) -> str:
    """Directory for service output logs."""
    log_dir = os.path.join(get_services_state_dir(repo_root), "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def load_services_state(repo_root: str) -> Dict[str, Any]:
    """Read services.json state file."""
    path = get_services_state_path(repo_root)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_services_state(repo_root: str, state: Dict[str, Any]) -> None:
    """Write services.json state file atomically."""
    path = get_services_state_path(repo_root)
    tmp = f"{path}.tmp-{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        os.replace(tmp, path)
    except OSError:
        if os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    """Check if TCP port is accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, TimeoutError):
        return False


def is_pid_alive(pid: Optional[int]) -> bool:
    """Check if process with given PID is currently alive."""
    if not pid or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        exit_code = ctypes.c_ulong()
        kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        kernel32.CloseHandle(handle)
        STILL_ACTIVE = 259
        return exit_code.value == STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def probe_http(
    url: str,
    status_spec: Any = 200,
    timeout: float = 2.0,
) -> bool:
    """Probe HTTP URL and verify response status against expected status or range."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "along-webdev-probe"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = getattr(resp, "status", 200)
            return _matches_status(code, status_spec)
    except urllib.error.HTTPError as exc:
        return _matches_status(exc.code, status_spec)
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _matches_status(code: int, spec: Any) -> bool:
    if isinstance(spec, int):
        return code == spec
    if isinstance(spec, str):
        if ".." in spec:
            try:
                low, high = spec.split("..", 1)
                return int(low) <= code <= int(high)
            except ValueError:
                return False
        try:
            return code == int(spec)
        except ValueError:
            return False
    return 200 <= code < 400


def check_probe(probe_spec: Dict[str, Any], svc: config.ServiceConfig) -> bool:
    """Execute declared probe check once."""
    if svc.kind == "static" and svc.static_port:
        return is_port_open(svc.static_port)

    if "http" in probe_spec:
        h = probe_spec["http"]
        url = h.get("url")
        status_spec = h.get("status", 200)
        timeout = float(h.get("timeout", 1.5))
        if url:
            return probe_http(url, status_spec=status_spec, timeout=timeout)

    if "port" in probe_spec:
        p_val = probe_spec["port"]
        port_num = int(p_val.get("port", p_val)) if isinstance(p_val, dict) else int(p_val)
        return is_port_open(port_num)

    return False


def poll_probe(
    probe_spec: Dict[str, Any],
    svc: config.ServiceConfig,
    log_path: str,
    process: Optional[subprocess.Popen] = None,
    default_timeout: float = 30.0,
) -> Tuple[bool, str]:
    """Poll probe until success or timeout, tracking fatal and noise regexes."""
    timeout = default_timeout
    if "http" in probe_spec and "timeout" in probe_spec["http"]:
        timeout = float(probe_spec["http"]["timeout"])
    elif "port" in probe_spec and isinstance(probe_spec["port"], dict):
        timeout = float(probe_spec["port"].get("timeout", timeout))

    fatal_res = [re.compile(pat) for pat in svc.fatal]
    log_pat_re = re.compile(probe_spec["log"]["pattern"]) if "log" in probe_spec and "pattern" in probe_spec["log"] else None

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process and process.poll() is not None:
            return False, f"Process exited prematurely with code {process.returncode}."

        # Scan log lines for fatal errors or log probe
        if os.path.isfile(log_path):
            try:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                for line in content.splitlines():
                    for fr in fatal_res:
                        if fr.search(line):
                            return False, f"Fatal error detected in logs: {line.strip()}"
                    if log_pat_re and log_pat_re.search(line):
                        return True, "Log probe matched."
            except OSError:
                pass

        if check_probe(probe_spec, svc):
            return True, "Probe succeeded."

        time.sleep(0.2)

    if process and process.poll() is not None:
        return False, f"Process exited prematurely with code {process.returncode}."

    return False, f"Probe timed out after {timeout:.1f}s."


def tail_log_lines(path: str, count: int = 40) -> List[str]:
    """Read the last N lines from a log file."""
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
            return [ln.rstrip("\r\n") for ln in lines[-count:]]
    except OSError:
        return []


def build_service_command(svc: config.ServiceConfig, repo_root: str) -> List[str]:
    """Construct command line arguments for launching a service."""
    if svc.kind == "static":
        root = os.path.abspath(os.path.join(repo_root, svc.static_root or "."))
        port = svc.static_port or 8099
        return [sys.executable, "-m", "http.server", str(port), "--directory", root]

    # Split command line preserving quotes
    import shlex
    return shlex.split(svc.command, posix=(os.name != "nt"))


def serve_up(
    repo_root: Optional[str] = None,
    service_names: Optional[List[str]] = None,
    cfg: Optional[config.WebdevConfig] = None,
) -> Dict[str, Any]:
    """Start declared application services or attach if already listening."""
    root = repo_root or repo.find_repo_root()
    webdev_cfg = cfg or config.load_config(root)
    state = load_services_state(root)
    log_dir = get_services_log_dir(root)
    env_file = config.load_env_file(root)

    targets = service_names or list(webdev_cfg.services.keys())
    if not targets:
        print("[Warning] No services declared in .along/webdev.yaml.", file=sys.stderr)
        return {"ok": True, "services": state}

    for name in targets:
        svc = webdev_cfg.services.get(name)
        if not svc:
            raise KeyError(f"Service '{name}' not declared in .along/webdev.yaml")

        existing = state.get(name)
        if existing and existing.get("state") in ("running", "attached"):
            pid = existing.get("pid")
            if pid and is_pid_alive(pid):
                continue

        # Check attach-if-running before starting duplicate
        if check_probe(svc.probe, svc):
            state[name] = {
                "name": name,
                "pid": None,
                "port": svc.static_port or svc.probe.get("port"),
                "log_path": os.path.join(log_dir, f"{name}.log"),
                "state": "attached",
                "started_by_along": False,
                "started_at": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
                "attached": True,
            }
            save_services_state(root, state)
            continue

        # Build child environment with secret resolution
        child_env = proc.child_env()
        for k, v in svc.raw_env.items():
            val, _ = config.resolve_env_val(v, env_file)
            child_env[k] = str(val)

        cmd = build_service_command(svc, root)
        cwd = os.path.abspath(os.path.join(root, svc.cwd)) if svc.cwd else root
        log_path = os.path.join(log_dir, f"{name}.log")

        log_file = open(log_path, "w", encoding="utf-8")
        spawn_kwargs = proc.spawn_group_kwargs()

        try:
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=child_env,
                **spawn_kwargs,
            )
        except OSError as exc:
            log_file.close()
            raise RuntimeError(f"Could not spawn service '{name}': {exc}")

        # Wait for readiness probe
        ok, reason = poll_probe(svc.probe, svc, log_path, process=process)
        if not ok:
            proc.kill_process_tree(process, grace=1.0)
            log_file.close()
            tail = tail_log_lines(log_path, count=40)
            tail_msg = "\n".join(tail) if tail else "(no log output)"
            state[name] = {
                "name": name,
                "pid": process.pid,
                "state": "crashed",
                "started_by_along": True,
                "log_path": log_path,
                "error": reason,
            }
            save_services_state(root, state)
            raise RuntimeError(
                f"Service '{name}' failed readiness probe: {reason}\n"
                f"--- Last 40 lines of {name}.log ---\n{tail_msg}"
            )

        state[name] = {
            "name": name,
            "pid": process.pid,
            "port": svc.static_port or svc.probe.get("port"),
            "log_path": log_path,
            "state": "running",
            "started_by_along": True,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
            "attached": False,
        }
        save_services_state(root, state)

    return {"ok": True, "services": state}


def serve_status(
    repo_root: Optional[str] = None,
    service_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Inspect status of managed services and refresh crash state."""
    root = repo_root or repo.find_repo_root()
    webdev_cfg = config.load_config(root)
    state = load_services_state(root)
    changed = False

    for name, info in list(state.items()):
        pid = info.get("pid")
        if pid and info.get("started_by_along"):
            if not is_pid_alive(pid):
                if info.get("state") == "running":
                    info["state"] = "crashed"
                    changed = True

        svc = webdev_cfg.services.get(name)
        if svc and info.get("state") == "running":
            # Check if probe still answers
            if not check_probe(svc.probe, svc):
                info["state"] = "crashed"
                changed = True

    if changed:
        save_services_state(root, state)

    if service_names:
        return {k: v for k, v in state.items() if k in service_names}
    return state


def serve_logs(
    repo_root: Optional[str] = None,
    service_name: str = "",
    tail: int = 40,
    grep: Optional[str] = None,
) -> List[str]:
    """Retrieve filtered log lines for a named service."""
    root = repo_root or repo.find_repo_root()
    log_dir = get_services_log_dir(root)
    log_path = os.path.join(log_dir, f"{service_name}.log")
    lines = tail_log_lines(log_path, count=tail * 2 if grep else tail)
    if grep:
        pat = re.compile(grep)
        lines = [ln for ln in lines if pat.search(ln)]
    return lines[-tail:]


def serve_down(
    repo_root: Optional[str] = None,
    service_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Stop Along-started services while preserving externally attached ones."""
    root = repo_root or repo.find_repo_root()
    state = load_services_state(root)
    targets = service_names or list(state.keys())
    results: Dict[str, str] = {}

    for name in targets:
        info = state.get(name)
        if not info:
            results[name] = "not_found"
            continue

        if not info.get("started_by_along"):
            results[name] = "preserved_attached"
            print(f"[Notice] Preserving attached service '{name}' (not started by Along).", file=sys.stderr)
            continue

        pid = info.get("pid")
        if pid and is_pid_alive(pid):
            proc.kill_process_tree(pid, grace=2.0)
            for _ in range(20):
                if not is_pid_alive(pid):
                    break
                time.sleep(0.1)
            results[name] = "stopped"
        else:
            results[name] = "already_stopped"

        info["state"] = "stopped"

    save_services_state(root, state)
    return results


def handle_serve_cli(args: argparse.Namespace) -> int:
    """CLI handler for along webdev serve up|status|logs|down."""
    repo_root = repo.find_repo_root()
    action = args.action

    if action == "up":
        try:
            res = serve_up(repo_root=repo_root, service_names=args.services or None)
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                for name, s_info in res.get("services", {}).items():
                    print(f"-> Service '{name}': {s_info.get('state')} (pid={s_info.get('pid')})")
            return 0
        except (RuntimeError, KeyError) as exc:
            print(f"[Error] {exc}", file=sys.stderr)
            return 1

    if action == "status":
        st = serve_status(repo_root=repo_root, service_names=args.services or None)
        if args.json:
            print(json.dumps(st, indent=2))
        else:
            print("=== WebDev Services Status ===")
            if not st:
                print("  No active or declared services.")
            for name, s_info in st.items():
                print(f"  {name:15} {s_info.get('state'):10} pid={s_info.get('pid')} attached={s_info.get('attached')}")
        return 0

    if action == "logs":
        if not args.services:
            print("[Error] Specific service name required for logs.", file=sys.stderr)
            return 2
        svc_name = args.services[0]
        lines = serve_logs(repo_root=repo_root, service_name=svc_name, tail=args.tail, grep=args.grep)
        if args.json:
            print(json.dumps(lines, indent=2))
        else:
            for ln in lines:
                print(ln)
        return 0

    if action == "down":
        res = serve_down(repo_root=repo_root, service_names=args.services or None)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            for name, outcome in res.items():
                print(f"-> Service '{name}': {outcome}")
        return 0

    return 2
