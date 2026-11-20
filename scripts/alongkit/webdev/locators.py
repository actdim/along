#!/usr/bin/env python3
"""alongkit.webdev.locators - Semantic locator resolution, ambiguity reporting, and coordinate gating."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

LocatorSpec = Union[str, Dict[str, Any]]


def describe_locator(spec: LocatorSpec) -> str:
    """Return a human-readable representation of a locator specification."""
    if isinstance(spec, str):
        return spec
    if isinstance(spec, dict):
        parts = [f"{k}={v!r}" for k, v in sorted(spec.items())]
        return f"{{{', '.join(parts)}}}"
    return str(spec)


def validate_coordinates_allowed(step_spec: Dict[str, Any]) -> None:
    """Enforce that coordinate clicks require allow_coordinates: true (REQ-2)."""
    if "at" in step_spec:
        if step_spec.get("allow_coordinates") is not True:
            raise ValueError(
                "Coordinate targeting ({at: {x, y}}) is rejected: coordinates are not layout-safe. "
                "Specify allow_coordinates: true on the step to override (REQ-2)."
            )


def resolve_playwright_locator(page: Any, spec: LocatorSpec) -> Any:
    """Resolve LocatorSpec into a Playwright Locator object."""
    if isinstance(spec, str):
        raw = spec.strip()
        if raw.startswith("text="):
            return page.get_by_text(raw[5:])
        if raw.startswith("label="):
            return page.get_by_label(raw[6:])
        if raw.startswith("placeholder="):
            return page.get_by_placeholder(raw[12:])
        if raw.startswith("test_id="):
            return page.get_by_test_id(raw[8:])
        return page.locator(raw)

    if isinstance(spec, dict):
        if "role" in spec:
            role_name = spec["role"]
            name_filter = spec.get("name")
            exact = spec.get("exact", False)
            if name_filter:
                return page.get_by_role(role_name, name=name_filter, exact=exact)
            return page.get_by_role(role_name)

        if "label" in spec:
            return page.get_by_label(spec["label"], exact=spec.get("exact", False))

        if "text" in spec:
            return page.get_by_text(spec["text"], exact=spec.get("exact", False))

        if "placeholder" in spec:
            return page.get_by_placeholder(spec["placeholder"], exact=spec.get("exact", False))

        if "test_id" in spec:
            return page.get_by_test_id(spec["test_id"])

        if "css" in spec:
            return page.locator(spec["css"])

        if "xpath" in spec:
            return page.locator(f"xpath={spec['xpath']}")

    return page.locator(str(spec))


def check_locator_uniqueness(locator: Any, spec: LocatorSpec, timeout_ms: int = 5000) -> None:
    """Assert locator matches exactly 1 element; reports candidate details on ambiguity (REQ-2)."""
    try:
        locator.first.wait_for(state="attached", timeout=timeout_ms)
    except Exception as exc:
        raise TimeoutError(f"Locator {describe_locator(spec)} timed out waiting for element.") from exc

    count = locator.count()
    if count == 0:
        raise TimeoutError(f"Locator {describe_locator(spec)} matched 0 elements.")
    if count > 1:
        candidates = []
        for i in range(min(count, 5)):
            el = locator.nth(i)
            tag = el.evaluate("e => e.tagName.toLowerCase()")
            text = el.evaluate("e => (e.innerText || e.textContent || '').trim().slice(0, 40)")
            box = el.bounding_box() or {}
            box_str = f"x={box.get('x', '?')}, y={box.get('y', '?')}, w={box.get('width', '?')}, h={box.get('height', '?')}"
            candidates.append(f"  [{i}] <{tag}> text={text!r} at ({box_str})")
        raise RuntimeError(
            f"Ambiguous locator {describe_locator(spec)} matched {count} elements:\n"
            + "\n".join(candidates)
        )
