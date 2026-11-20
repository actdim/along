#!/usr/bin/env python3
"""alongkit.webdev.browser - Portable CfT process launcher, DevTools port discovery, and teardown."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .. import proc
from . import cft

DEVTOOLS_ACTIVE_PORT_FILE = "DevToolsActivePort"


class BrowserProcess:
    """Manages the lifecycle of a spawned Chrome for Testing browser instance."""

    def __init__(
        self,
        popen: subprocess.Popen,
        port: int,
        ws_path: str,
        user_data_dir: str,
        is_temp_profile: bool = True,
    ):
        self.popen = popen
        self.port = port
        self.ws_path = ws_path
        self.user_data_dir = os.path.abspath(user_data_dir)
        self.is_temp_profile = is_temp_profile
        self.http_endpoint = f"http://127.0.0.1:{self.port}"
        clean_path = ws_path if ws_path.startswith("/") else f"/{ws_path}"
        self.ws_endpoint = f"ws://127.0.0.1:{self.port}{clean_path}"

    def is_alive(self) -> bool:
        """Check if browser process is still running."""
        return self.popen.poll() is None

    def close(self, grace: float = 2.0) -> None:
        """Terminate browser process tree and purge temporary user profile."""
        if self.is_alive():
            proc.kill_process_tree(self.popen, grace=grace)

        if self.is_temp_profile and os.path.isdir(self.user_data_dir):
            for _ in range(5):
                try:
                    shutil.rmtree(self.user_data_dir, ignore_errors=False)
                    break
                except OSError:
                    time.sleep(0.2)
            if os.path.isdir(self.user_data_dir):
                shutil.rmtree(self.user_data_dir, ignore_errors=True)

    def __enter__(self) -> BrowserProcess:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


def launch_cft(
    browser_path: Optional[str] = None,
    headless: bool = True,
    user_data_dir: Optional[str] = None,
    extra_args: Optional[List[str]] = None,
    remote_debugging_port: int = 0,
    timeout: float = 20.0,
    repo_root: Optional[str] = None,
    auto_download: bool = True,
) -> BrowserProcess:
    """Launch Portable Chrome for Testing and wait for DevToolsActivePort readiness."""
    executable = browser_path or cft.resolve_browser_path(
        repo_root=repo_root, auto_download=auto_download
    )
    if not os.path.isfile(executable):
        raise FileNotFoundError(f"Browser binary does not exist: {executable}")

    is_temp = False
    profile_dir = user_data_dir
    if not profile_dir:
        is_temp = True
        session_id = uuid.uuid4().hex[:12]
        profile_dir = os.path.join(tempfile.get_tempdir(), f"along-cft-session-{session_id}")

    os.makedirs(profile_dir, exist_ok=True)
    port_marker = os.path.join(profile_dir, DEVTOOLS_ACTIVE_PORT_FILE)
    if os.path.isfile(port_marker):
        try:
            os.remove(port_marker)
        except OSError:
            pass

    cmd: List[str] = [
        executable,
        f"--remote-debugging-port={remote_debugging_port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-background-timer-throttling",
        "--disable-client-side-phishing-detection",
        "--disable-default-apps",
        "--disable-hang-monitor",
        "--disable-popup-blocking",
        "--disable-prompt-on-repost",
        "--disable-sync",
        "--disable-translate",
        "--metrics-recording-only",
        "--safebrowsing-disable-auto-update",
    ]

    if headless:
        cmd.append("--headless=new")

    if extra_args:
        cmd.extend(extra_args)

    spawn_kwargs = proc.spawn_group_kwargs()
    child_env = proc.child_env()

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=child_env,
        **spawn_kwargs,
    )

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            proc.kill_process_tree(process, grace=1.0)
            if is_temp:
                shutil.rmtree(profile_dir, ignore_errors=True)
            raise RuntimeError(
                f"Chrome process exited unexpectedly with code {process.returncode} before port discovery."
            )

        if os.path.isfile(port_marker):
            try:
                with open(port_marker, "r", encoding="utf-8") as handle:
                    lines = [ln.strip() for ln in handle if ln.strip()]
                if len(lines) >= 2:
                    port = int(lines[0])
                    ws_path = lines[1]
                    return BrowserProcess(
                        popen=process,
                        port=port,
                        ws_path=ws_path,
                        user_data_dir=profile_dir,
                        is_temp_profile=is_temp,
                    )
            except (OSError, ValueError):
                pass
        time.sleep(0.1)

    proc.kill_process_tree(process, grace=1.0)
    if is_temp:
        shutil.rmtree(profile_dir, ignore_errors=True)
    raise TimeoutError(
        f"Timed out after {timeout:.1f}s waiting for {DEVTOOLS_ACTIVE_PORT_FILE} in {profile_dir}."
    )


def connect_playwright(browser_process: BrowserProcess) -> Tuple[Any, Any]:
    """Connect Playwright to the running browser process via CDP websocket.

    Returns (playwright_context, browser_instance).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed in the active environment. "
            "Run via 'along webdev' to auto-bootstrap runtime dependencies."
        ) from exc

    pw = sync_playwright().start()
    try:
        browser = pw.chromium.connect_over_cdp(browser_process.ws_endpoint)
        return pw, browser
    except Exception:
        pw.stop()
        raise
