#!/usr/bin/env python3
"""alongkit.webdev.cft - Portable Chrome for Testing (CfT) bootstrap, resolution, and caching."""

from __future__ import annotations

import json
import os
import platform
import shutil
import stat
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from typing import Any, Dict, Optional

DEFAULT_CFT_VERSION = "131.0.6778.85"
CFT_API_URL = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"
CFT_DOWNLOAD_URL_TEMPLATE = (
    "https://storage.googleapis.com/chrome-for-testing-public/{version}/{platform}/chrome-{platform}.zip"
)


def detect_platform() -> str:
    """Detect CfT platform identifier matching Google release naming."""
    system = sys.platform
    if system == "win32":
        return "win64"
    if system == "darwin":
        machine = platform.machine().lower()
        if machine in ("arm64", "aarch64"):
            return "mac-arm64"
        return "mac-x64"
    if system.startswith("linux"):
        return "linux64"
    return system


def binary_relative_path(platform_name: Optional[str] = None) -> str:
    """Relative path from unpacked CfT root to the browser executable."""
    plat = platform_name or detect_platform()
    if plat == "win64":
        return os.path.join("chrome-win64", "chrome.exe")
    if plat == "linux64":
        return os.path.join("chrome-linux64", "chrome")
    if plat in ("mac-arm64", "mac-x64"):
        return os.path.join(
            f"chrome-{plat}",
            "Google Chrome for Testing.app",
            "Contents",
            "MacOS",
            "Google Chrome for Testing",
        )
    return os.path.join(f"chrome-{plat}", "chrome")


def cft_cache_dir(version: str = DEFAULT_CFT_VERSION) -> str:
    """Location of cached CfT binaries for the given version."""
    override = os.environ.get("ALONG_CFT_CACHE_DIR")
    if override:
        return os.path.abspath(override)
    home = os.path.expanduser("~")
    return os.path.join(home, ".along", "runtimes", "cft", version)


def find_installed_cft(
    version: str = DEFAULT_CFT_VERSION,
    platform_name: Optional[str] = None,
) -> Optional[str]:
    """Return path to cached CfT binary if present on disk, otherwise None."""
    cache = cft_cache_dir(version)
    rel = binary_relative_path(platform_name)
    candidate = os.path.join(cache, rel)
    if os.path.isfile(candidate):
        return os.path.abspath(candidate)
    return None


def fetch_latest_cft_version(timeout: float = 5.0) -> Optional[str]:
    """Query CfT API for latest stable version; returns None if offline or timed out."""
    try:
        with urllib.request.urlopen(CFT_API_URL, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            channels = payload.get("channels", {})
            stable = channels.get("Stable", {})
            ver = stable.get("version")
            if isinstance(ver, str) and ver.strip():
                return ver.strip()
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None
    return None


def download_cft(
    version: str = DEFAULT_CFT_VERSION,
    platform_name: Optional[str] = None,
    destination_dir: Optional[str] = None,
    quiet: bool = False,
    url_override: Optional[str] = None,
    timeout: float = 120.0,
) -> str:
    """Download and unpack CfT archive into cache directory, returning binary path."""
    plat = platform_name or detect_platform()
    target_dir = destination_dir or cft_cache_dir(version)
    rel_binary = binary_relative_path(plat)
    final_binary = os.path.join(target_dir, rel_binary)

    if os.path.isfile(final_binary):
        return os.path.abspath(final_binary)

    url = url_override or CFT_DOWNLOAD_URL_TEMPLATE.format(version=version, platform=plat)
    if not quiet:
        print(f"-> [Along CfT] Downloading Chrome for Testing {version} ({plat}) from {url}...", file=sys.stderr)

    os.makedirs(os.path.dirname(target_dir), exist_ok=True)
    tmp_extract = f"{target_dir}.tmp-{os.getpid()}"
    shutil.rmtree(tmp_extract, ignore_errors=True)
    os.makedirs(tmp_extract, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_file:
        tmp_zip_path = tmp_file.name

    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp, open(tmp_zip_path, "wb") as out_file:
            shutil.copyfileobj(resp, out_file)

        with zipfile.ZipFile(tmp_zip_path, "r") as archive:
            archive.extractall(tmp_extract)

        candidate_binary = os.path.join(tmp_extract, rel_binary)
        if not os.path.isfile(candidate_binary):
            raise FileNotFoundError(
                f"CfT binary not found at expected extracted path: {candidate_binary}"
            )

        # Ensure executable bit on POSIX
        if sys.platform != "win32":
            st = os.stat(candidate_binary)
            os.chmod(candidate_binary, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

        if os.path.isdir(target_dir):
            shutil.rmtree(target_dir, ignore_errors=True)

        os.replace(tmp_extract, target_dir)
        if not quiet:
            print(f"-> [Along CfT] Installed to {final_binary}", file=sys.stderr)
        return os.path.abspath(final_binary)

    finally:
        if os.path.isfile(tmp_zip_path):
            try:
                os.remove(tmp_zip_path)
            except OSError:
                pass
        shutil.rmtree(tmp_extract, ignore_errors=True)


def status(
    repo_root: Optional[str] = None,
    version: str = DEFAULT_CFT_VERSION,
    platform_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Inspect CfT runtime status and resolution."""
    plat = platform_name or detect_platform()
    cache = cft_cache_dir(version)
    cached_path = find_installed_cft(version, plat)
    custom_path = os.environ.get("ALONG_BROWSER_PATH")

    resolved_path: Optional[str] = None
    if custom_path and os.path.isfile(custom_path):
        resolved_path = os.path.abspath(custom_path)
    elif cached_path:
        resolved_path = cached_path

    return {
        "available": bool(resolved_path and os.path.isfile(resolved_path)),
        "version": version,
        "platform": plat,
        "path": resolved_path,
        "cached": bool(cached_path and os.path.isfile(cached_path)),
        "cache_dir": cache,
        "custom_path": custom_path,
    }


def resolve_browser_path(
    repo_root: Optional[str] = None,
    custom_path: Optional[str] = None,
    auto_download: bool = True,
    version: str = DEFAULT_CFT_VERSION,
    platform_name: Optional[str] = None,
    quiet: bool = False,
) -> str:
    """Resolve browser executable path or download if auto_download is True."""
    plat = platform_name or detect_platform()
    override = custom_path or os.environ.get("ALONG_BROWSER_PATH")
    if override:
        if os.path.isfile(override):
            return os.path.abspath(override)
        raise FileNotFoundError(f"Custom browser binary not found: {override}")

    installed = find_installed_cft(version, plat)
    if installed:
        return installed

    if not auto_download:
        raise RuntimeError(
            f"Chrome for Testing {version} is not cached. Run 'along webdev bootstrap' to install."
        )

    return download_cft(version=version, platform_name=plat, quiet=quiet)
