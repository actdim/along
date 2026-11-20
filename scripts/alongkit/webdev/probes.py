#!/usr/bin/env python3
"""alongkit.webdev.probes - Python helper interface for injecting and invoking in-page probes."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

_PROBES_JS_PATH = os.path.join(os.path.dirname(__file__), "probes.js")


def get_probes_script() -> str:
    """Read the in-page JavaScript bundle for geometry and spy probes."""
    try:
        with open(_PROBES_JS_PATH, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""


def inject_probes(page: Any) -> None:
    """Inject geometry probes and spy runtime into Playwright Page."""
    script = get_probes_script()
    if script:
        page.add_init_script(script)
        page.evaluate(script)


def box(page: Any, target: Any) -> Optional[Dict[str, float]]:
    """Query bounding box of target element via in-page probe."""
    inject_probes(page)
    return page.evaluate("t => window.__along_probes__.box(t)", target)


def above(page: Any, target_a: Any, target_b: Any) -> bool:
    """Assert element A is positioned vertically above element B."""
    inject_probes(page)
    return bool(page.evaluate("([a, b]) => window.__along_probes__.above(a, b)", [target_a, target_b]))


def covered_by(page: Any, target: Any) -> Dict[str, Any]:
    """Check if target element is covered by another element at its center/corners."""
    inject_probes(page)
    return page.evaluate("t => window.__along_probes__.covered_by(t)", target)


def overflow_x(page: Any) -> Dict[str, Any]:
    """Check if horizontal overflow exists in the document layout."""
    inject_probes(page)
    return page.evaluate("() => window.__along_probes__.overflow_x()")


def in_viewport(page: Any, target: Any) -> bool:
    """Check if target element is within the viewport bounding box."""
    inject_probes(page)
    return bool(page.evaluate("t => window.__along_probes__.in_viewport(t)", target))


def install_spy(page: Any, target_path: str) -> None:
    """Install call recording spy on target function path (e.g. navigator.mediaSession.setPositionState)."""
    inject_probes(page)
    page.evaluate("p => window.__along_probes__.install_spy(p)", target_path)


def get_spy_calls(page: Any, target_path: str) -> List[Dict[str, Any]]:
    """Retrieve recorded calls for target function."""
    inject_probes(page)
    return page.evaluate("p => window.__along_probes__.get_spy_calls(p)", target_path) or []
