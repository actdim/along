#!/usr/bin/env python3
"""alongkit.webdev.session - Browser session context, origin guard, emulation, and storage seeding."""

from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

VIEWPORT_PRESETS: Dict[str, Dict[str, Any]] = {
    "mobile-375x812": {
        "viewport": {"width": 375, "height": 812},
        "is_mobile": True,
        "has_touch": True,
        "device_scale_factor": 3.0,
    },
    "mobile-390x844": {
        "viewport": {"width": 390, "height": 844},
        "is_mobile": True,
        "has_touch": True,
        "device_scale_factor": 3.0,
    },
    "tablet-900x800": {
        "viewport": {"width": 900, "height": 800},
        "is_mobile": False,
        "has_touch": True,
        "device_scale_factor": 2.0,
    },
    "desktop-1440x900": {
        "viewport": {"width": 1440, "height": 900},
        "is_mobile": False,
        "has_touch": False,
        "device_scale_factor": 1.0,
    },
}


def parse_viewport_spec(spec: Any) -> Dict[str, Any]:
    """Parse viewport preset name, WxH string, or dictionary into context options."""
    if not spec:
        return VIEWPORT_PRESETS["desktop-1440x900"]

    if isinstance(spec, str):
        cleaned = spec.strip().lower()
        if cleaned in VIEWPORT_PRESETS:
            return VIEWPORT_PRESETS[cleaned]
        if "x" in cleaned:
            try:
                w, h = cleaned.split("x", 1)
                return {
                    "viewport": {"width": int(w), "height": int(h)},
                    "is_mobile": False,
                    "has_touch": False,
                    "device_scale_factor": 1.0,
                }
            except ValueError:
                pass

    if isinstance(spec, dict):
        w = spec.get("width", 1440)
        h = spec.get("height", 900)
        return {
            "viewport": {"width": int(w), "height": int(h)},
            "is_mobile": bool(spec.get("is_mobile", False)),
            "has_touch": bool(spec.get("has_touch", False)),
            "device_scale_factor": float(spec.get("device_scale_factor", 1.0)),
        }

    return VIEWPORT_PRESETS["desktop-1440x900"]


def get_origin(url: str) -> str:
    """Extract scheme + netloc origin from URL."""
    if not url:
        return ""
    if url.startswith("about:"):
        return "about:blank"
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}".lower()


def is_origin_allowed(url: str, allowed_origins: List[str]) -> bool:
    """Return True if url origin matches allowlist or about:blank."""
    target_origin = get_origin(url)
    if not target_origin or target_origin == "about:blank":
        return True
    for allowed in allowed_origins:
        if get_origin(allowed) == target_origin:
            return True
    return False


def setup_origin_guard(page: Any, allowed_origins: List[str]) -> None:
    """Attach navigation guard to abort unallowed origin requests (REQ-2)."""
    norm_allowed = [get_origin(o) for o in allowed_origins if o] + ["about:blank"]

    def _route_handler(route: Any, request: Any) -> None:
        if request.is_navigation_request():
            dest = request.url
            if not is_origin_allowed(dest, norm_allowed):
                route.abort("blockedbyclient")
                return
        route.continue_()

    try:
        page.route("**/*", _route_handler)
    except (AttributeError, RuntimeError, TypeError):
        pass


def setup_storage_seeding(context_or_page: Any, storage_spec: Dict[str, Any]) -> None:
    """Inject storage seeds (localStorage, sessionStorage) before page scripts run (REQ-4)."""
    local_items = storage_spec.get("localStorage") or {}
    session_items = storage_spec.get("sessionStorage") or {}

    init_js = []
    if local_items:
        init_js.append(
            "(function() {\n"
            + "".join(f"  try {{ window.localStorage.setItem({json.dumps(k)}, {json.dumps(str(v))}); }} catch(e) {{}}\n"
                      for k, v in local_items.items())
            + "})();"
        )
    if session_items:
        init_js.append(
            "(function() {\n"
            + "".join(f"  try {{ window.sessionStorage.setItem({json.dumps(k)}, {json.dumps(str(v))}); }} catch(e) {{}}\n"
                      for k, v in session_items.items())
            + "})();"
        )

    if init_js:
        full_code = "\n".join(init_js)
        context_or_page.add_init_script(full_code)
