#!/usr/bin/env python3
"""alongkit.webdev.steps - Step execution engine, password safety gate, and synthetic uploads."""

from __future__ import annotations

import json
import os
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

from . import locators, probes, redact


def generate_synthetic_fixture(kind: str = "png", size_kb: int = 1, name: Optional[str] = None) -> str:
    """Generate a temporary synthetic fixture file of specified kind and approximate size."""
    filename = name or f"synthetic_{int(time.time())}.{kind}"
    tmp_path = os.path.join(tempfile.gettempdir(), filename)
    target_bytes = max(1, size_kb) * 1024

    if kind.lower() in ("png", "jpg", "jpeg"):
        # 1x1 transparent PNG header + padding
        header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        padding = b"\x00" * max(0, target_bytes - len(header))
        payload = header + padding
    elif kind.lower() == "txt":
        payload = (b"Generated test fixture line.\n" * (target_bytes // 30 + 1))[:target_bytes]
    else:
        payload = b"\x00" * target_bytes

    with open(tmp_path, "wb") as f:
        f.write(payload)
    return tmp_path


def execute_step(
    page: Any,
    step: Dict[str, Any],
    harvester: Optional[Any] = None,
    redactor: Optional[redact.Redactor] = None,
    test_credentials: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Execute a single declarative step against Playwright Page."""
    action = step.get("action")
    if not action:
        for k in ("goto", "click", "fill", "type", "press", "eval", "upload", "wait_for", "route", "assert_visible", "assert_text", "screenshot"):
            if k in step:
                action = k
                break

    locators.validate_coordinates_allowed(step)

    # REQ-3 Password safety check
    if action in ("fill", "type"):
        target_spec = step.get("selector") or step.get("locator") or step.get("fill") or step.get("type")
        val = step.get("value", "")
        if target_spec:
            loc = locators.resolve_playwright_locator(page, target_spec)
            try:
                el_type = loc.evaluate("e => (e.getAttribute('type') || '').toLowerCase()")
                if el_type == "password":
                    # Check if value came from test_credentials
                    allowed_values = set((test_credentials or {}).values())
                    if val not in allowed_values and not str(val).startswith("***"):
                        raise ValueError(
                            "Refusing to fill password field with literal password value. "
                            "Test credentials must come from declared test_credentials / .env (REQ-3)."
                        )
            except Exception as exc:
                if "Refusing to fill" in str(exc):
                    raise

    if action in ("goto", "navigate"):
        url = step.get("url") or step.get("goto") or step.get("navigate")
        page.goto(url)
        return {"action": "goto", "url": url, "ok": True}

    if action == "click":
        target = step.get("selector") or step.get("locator") or step.get("click")
        loc = locators.resolve_playwright_locator(page, target)
        if "at" in step:
            at = step["at"]
            loc.click(position={"x": at["x"], "y": at["y"]})
        else:
            loc.click()
        return {"action": "click", "ok": True}

    if action == "dblclick":
        target = step.get("selector") or step.get("locator") or step.get("dblclick")
        loc = locators.resolve_playwright_locator(page, target)
        loc.dblclick()
        return {"action": "dblclick", "ok": True}

    if action == "hover":
        target = step.get("selector") or step.get("locator") or step.get("hover")
        loc = locators.resolve_playwright_locator(page, target)
        loc.hover()
        return {"action": "hover", "ok": True}

    if action == "fill":
        target = step.get("selector") or step.get("locator") or step.get("fill")
        val = step.get("value", "")
        loc = locators.resolve_playwright_locator(page, target)
        loc.fill(str(val))
        return {"action": "fill", "ok": True}

    if action == "type":
        target = step.get("selector") or step.get("locator") or step.get("type")
        val = step.get("value", "")
        delay = float(step.get("delay", 20))
        loc = locators.resolve_playwright_locator(page, target)
        loc.type(str(val), delay=delay)
        return {"action": "type", "ok": True}

    if action == "press":
        key = step.get("key") or step.get("press")
        repeat = int(step.get("repeat", 1))
        target = step.get("selector") or step.get("locator")
        for _ in range(repeat):
            if target:
                loc = locators.resolve_playwright_locator(page, target)
                loc.press(key)
            else:
                page.keyboard.press(key)
        return {"action": "press", "key": key, "repeat": repeat, "ok": True}

    if action in ("back", "forward", "reload"):
        if action == "back":
            page.go_back()
        elif action == "forward":
            page.go_forward()
        else:
            page.reload()
        return {"action": action, "ok": True}

    if action == "upload":
        target = step.get("selector") or step.get("locator") or step.get("upload")
        loc = locators.resolve_playwright_locator(page, target)
        if "generate" in step:
            g = step["generate"]
            file_path = generate_synthetic_fixture(
                kind=g.get("kind", "png"),
                size_kb=g.get("size_kb", 1),
                name=g.get("name"),
            )
        else:
            file_path = step.get("file") or step.get("path")
        loc.set_input_files(file_path)
        return {"action": "upload", "file": file_path, "ok": True}

    if action == "eval":
        expr = step.get("expr") or step.get("eval")
        res = page.evaluate(expr)
        if "expect" in step:
            exp = step["expect"]
            if isinstance(exp, dict) and "$" in exp:
                expected_val = exp["$"]
                if res != expected_val:
                    raise AssertionError(f"Eval assertion failed: expected {expected_val!r}, got {res!r}")
            elif isinstance(exp, dict) and "$.self" in exp:
                if not isinstance(res, dict) or res.get("self") != exp["$.self"]:
                    raise AssertionError(f"Eval covered_by assertion failed: expected {exp['$.self']}, got {res}")
            elif isinstance(exp, dict) and "$.overflow" in exp:
                if not isinstance(res, dict) or res.get("overflow") != exp["$.overflow"]:
                    raise AssertionError(f"Eval overflow assertion failed: expected {exp['$.overflow']}, got {res}")
        return {"action": "eval", "result": res, "ok": True}

    if action == "assert_visible":
        target = step.get("selector") or step.get("locator") or step.get("assert_visible")
        loc = locators.resolve_playwright_locator(page, target)
        if not loc.is_visible():
            raise AssertionError(f"Element not visible: {locators.describe_locator(target)}")
        return {"action": "assert_visible", "ok": True}

    if action == "assert_hidden":
        target = step.get("selector") or step.get("locator") or step.get("assert_hidden")
        loc = locators.resolve_playwright_locator(page, target)
        if loc.is_visible():
            raise AssertionError(f"Element is unexpectedly visible: {locators.describe_locator(target)}")
        return {"action": "assert_hidden", "ok": True}

    if action == "assert_text":
        target = step.get("selector") or step.get("locator") or step.get("assert_text")
        contains = step.get("contains")
        exact = step.get("exact")
        loc = locators.resolve_playwright_locator(page, target)
        text = loc.inner_text()
        if contains and contains not in text:
            raise AssertionError(f"Text mismatch: expected {contains!r} to be in {text!r}")
        if exact and exact != text:
            raise AssertionError(f"Text mismatch: expected {exact!r}, got {text!r}")
        return {"action": "assert_text", "ok": True}

    if action == "route":
        route_spec = step.get("route") or step
        url_pat = route_spec.get("url", "**/*")
        fulfill = route_spec.get("fulfill")
        abort = route_spec.get("abort")

        def _handler(route: Any) -> None:
            if abort:
                route.abort(abort if isinstance(abort, str) else "failed")
            elif fulfill:
                status = fulfill.get("status", 200)
                body = fulfill.get("body", "OK")
                headers = fulfill.get("headers", {})
                route.fulfill(status=status, body=str(body), headers=headers)
            else:
                route.continue_()

        page.route(url_pat, _handler)
        return {"action": "route", "url": url_pat, "ok": True}

    if action == "assert_no_console_errors":
        if harvester:
            errors = harvester.filtered_console_errors()
            if errors:
                err_text = "; ".join(f"[{e.level}] {e.text}" for e in errors)
                raise AssertionError(f"Console errors detected: {err_text}")
        return {"action": "assert_no_console_errors", "ok": True}

    if action == "assert_no_failed_requests":
        if harvester:
            failures = harvester.filtered_failed_requests()
            if failures:
                fail_text = "; ".join(f"{f.method} {f.url} ({f.status or f.failure_text})" for f in failures)
                raise AssertionError(f"Failed network requests detected: {fail_text}")
        return {"action": "assert_no_failed_requests", "ok": True}

    return {"action": action or "unknown", "ok": True}
