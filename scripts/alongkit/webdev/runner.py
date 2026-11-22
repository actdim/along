#!/usr/bin/env python3
"""alongkit.webdev.runner - Execution runner for declarative scenarios, matrix expansion, and evidence capture."""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from .. import repo
from . import browser, capture, config, evidence, failures, locators, redact, results, schema, session, steps


class SimulatedLocator:
    """Lightweight Playwright Locator mock for hermetic scenario testing."""
    def __init__(self, spec: Any) -> None:
        self.spec = spec

    def click(self, **kw) -> None:
        pass

    def dblclick(self, **kw) -> None:
        pass

    def hover(self, **kw) -> None:
        pass

    def fill(self, val: str, **kw) -> None:
        pass

    def type(self, val: str, **kw) -> None:
        pass

    def press(self, key: str, **kw) -> None:
        pass

    def set_input_files(self, file_path: str, **kw) -> None:
        pass

    def is_visible(self) -> bool:
        return True

    def inner_text(self) -> str:
        return "sample text"

    def evaluate(self, expr: str, **kw) -> Any:
        return "text"


class SimulatedPage:
    """Lightweight Playwright Page mock that validates real step execution in hermetic mode."""
    def __init__(self) -> None:
        self.keyboard = self
        self._url = "about:blank"

    def goto(self, url: str, **kw) -> None:
        self._url = url

    def evaluate(self, expr: str, **kw) -> Any:
        try:
            return eval(expr, {"__builtins__": {}}, {})
        except (ArithmeticError, SyntaxError, ValueError, TypeError, NameError):
            return None

    def locator(self, spec: Any, **kw) -> SimulatedLocator:
        return SimulatedLocator(spec)

    def get_by_text(self, text: str, **kw) -> SimulatedLocator:
        return SimulatedLocator(f"text={text}")

    def get_by_label(self, label: str, **kw) -> SimulatedLocator:
        return SimulatedLocator(f"label={label}")

    def get_by_placeholder(self, ph: str, **kw) -> SimulatedLocator:
        return SimulatedLocator(f"placeholder={ph}")

    def get_by_test_id(self, tid: str, **kw) -> SimulatedLocator:
        return SimulatedLocator(f"test_id={tid}")

    def route(self, pat: str, handler: Any, **kw) -> None:
        pass

    def screenshot(self, path: Optional[str] = None, **kw) -> bytes:
        if path:
            with open(path, "wb") as f:
                f.write(b"simulated-screenshot")
        return b""

    def press(self, key: str, **kw) -> None:
        pass


def expand_check_matrix(chk: Dict[str, Any], defaults: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Return list of (viewport, theme) cells for a check."""
    matrix = chk.get("matrix") or {}
    viewports = matrix.get("viewport") or [defaults.get("viewport") or "desktop-1440x900"]
    themes = matrix.get("theme") or [defaults.get("theme") or "light"]
    return list(itertools.product(viewports, themes))


def run_scenario(
    repo_root: str,
    scenario_spec: Any,
    issue_override: Optional[str] = None,
    check_filter: Optional[List[str]] = None,
    matrix_filter: Optional[Dict[str, str]] = None,
    headed: bool = False,
    file_failures_flag: bool = False,
    keep_evidence_dir: Optional[str] = None,
) -> Tuple[int, Dict[str, Any]]:
    """Execute scenario against real CfT browser or simulated runner."""
    try:
        scenario = schema.load_scenario(scenario_spec)
    except (ValueError, OSError) as exc:
        print(f"[Error] Invalid scenario: {exc}", file=sys.stderr)
        return 2, {"error": str(exc)}

    meta = scenario.get("meta", {})
    issue_key = issue_override or meta.get("issue", "unbound")
    defaults = scenario.get("defaults", {})
    run_id = evidence.generate_run_id()
    run_dir = evidence.get_run_artifacts_dir(repo_root, issue_key, run_id)

    # Bring up declared services if requested
    req_services = scenario.get("services") or []
    if req_services:
        try:
            from . import services
            services.serve_up(repo_root, service_names=req_services)
        except (RuntimeError, OSError, ValueError) as exc:
            print(f"[Warning] Services serve_up encountered: {exc}", file=sys.stderr)

    redactor = redact.Redactor()
    harvester = capture.DiagnosticsHarvester(
        redactor=redactor,
        console_noise=defaults.get("noise", {}).get("console"),
        network_noise=defaults.get("noise", {}).get("network"),
    )

    check_results: List[Dict[str, Any]] = []
    checks = scenario.get("checks", [])
    if check_filter:
        checks = [c for c in checks if c.get("id") in check_filter]

    # Evaluate checks
    for chk in checks:
        cid = chk.get("id", "")
        title = chk.get("title", "")
        ac = chk.get("ac", "")
        not_run_reason = chk.get("not_run")
        cells = expand_check_matrix(chk, defaults)

        for vp, theme in cells:
            if matrix_filter:
                if matrix_filter.get("viewport") and matrix_filter["viewport"] != vp:
                    continue
                if matrix_filter.get("theme") and matrix_filter["theme"] != theme:
                    continue

            start_t = time.monotonic()
            if not_run_reason:
                check_results.append({
                    "check_id": cid,
                    "title": title,
                    "ac": ac,
                    "viewport": vp,
                    "theme": theme,
                    "status": "NOT RUN",
                    "reason": not_run_reason,
                    "evidence": [],
                    "duration_ms": 0.0,
                })
                continue

            # Execute steps
            step_list = chk.get("steps") or []
            if not step_list:
                check_results.append({
                    "check_id": cid,
                    "title": title,
                    "ac": ac,
                    "viewport": vp,
                    "theme": theme,
                    "status": "NOT RUN",
                    "reason": "not-compiled",
                    "evidence": [],
                    "duration_ms": 0.0,
                })
                continue

            status = "PASS"
            failure_reason = ""
            cell_evidence: List[str] = []

            # In hermetic test mode without real browser, execute steps against SimulatedPage
            is_hermetic = os.environ.get("ALONG_WEBDEV_HERMETIC") == "1"
            if is_hermetic:
                page = SimulatedPage()
                try:
                    for s_idx, step_obj in enumerate(step_list):
                        steps.execute_step(page, step_obj, harvester=harvester, redactor=redactor)
                        if "screenshot" in step_obj:
                            ev_name = evidence.evidence_filename(cid, vp, theme, f"step_{s_idx}")
                            ev_path = os.path.join(run_dir, ev_name)
                            evidence.capture_screenshot(page, ev_path)
                            cell_evidence.append(ev_path)
                except (RuntimeError, AssertionError, ValueError, TypeError, KeyError, OSError, TimeoutError) as exc:
                    status = "FAIL"
                    failure_reason = str(exc)

                duration_ms = (time.monotonic() - start_t) * 1000
                check_results.append({
                    "check_id": cid,
                    "title": title,
                    "ac": ac,
                    "viewport": vp,
                    "theme": theme,
                    "status": status,
                    "reason": failure_reason,
                    "evidence": cell_evidence,
                    "duration_ms": round(duration_ms, 1),
                    "steps": step_list,
                })
                continue

            # Real browser execution tier
            try:
                with browser.launch_cft(headless=not headed, repo_root=repo_root) as bp:
                    pw, b_inst = browser.connect_playwright(bp)
                    try:
                        vp_opts = session.parse_viewport_spec(vp)
                        color_scheme = "dark" if theme == "dark" else "light"
                        ctx = b_inst.new_context(
                            viewport=vp_opts.get("viewport"),
                            is_mobile=vp_opts.get("is_mobile", False),
                            has_touch=vp_opts.get("has_touch", False),
                            device_scale_factor=vp_opts.get("device_scale_factor", 1.0),
                            color_scheme=color_scheme,
                        )
                        page = ctx.new_page()
                        harvester.attach(page)
                        session.setup_origin_guard(page, defaults.get("origins") or [])
                        session.setup_storage_seeding(page, defaults.get("storage") or {})

                        for s_idx, step_obj in enumerate(step_list):
                            steps.execute_step(page, step_obj, harvester=harvester, redactor=redactor)
                            if "screenshot" in step_obj:
                                ev_name = evidence.evidence_filename(cid, vp, theme, f"step_{s_idx}")
                                ev_path = os.path.join(run_dir, ev_name)
                                evidence.capture_screenshot(page, ev_path)
                                cell_evidence.append(ev_path)
                    finally:
                        b_inst.close()
                        pw.stop()
            except (RuntimeError, AssertionError, ValueError, TypeError, KeyError, OSError, TimeoutError) as exc:
                status = "FAIL"
                failure_reason = str(exc)

            duration_ms = (time.monotonic() - start_t) * 1000
            check_results.append({
                "check_id": cid,
                "title": title,
                "ac": ac,
                "viewport": vp,
                "theme": theme,
                "status": status,
                "reason": failure_reason,
                "evidence": cell_evidence,
                "duration_ms": round(duration_ms, 1),
                "steps": step_list,
            })

    # Build and persist report payload
    report_data = results.build_report_payload(issue_key, run_id, check_results)
    results_json_path = os.path.join(run_dir, "results.json")
    with open(results_json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    results_md = results.format_results_markdown(run_id, check_results)
    results_md_path = os.path.join(run_dir, "results.md")
    with open(results_md_path, "w", encoding="utf-8") as f:
        f.write(results_md)

    if issue_override:
        results.update_issue_results(repo_root, issue_override, results_md)

    failed_checks = [r for r in check_results if r.get("status") == "FAIL"]
    if file_failures_flag and failed_checks:
        failures.file_failures(repo_root, issue_key, failed_checks)

    if keep_evidence_dir:
        evidence.export_evidence(run_dir, keep_evidence_dir)

    exit_code = 1 if failed_checks else 0
    return exit_code, report_data


def handle_run_cli(args: argparse.Namespace) -> int:
    """CLI handler for along webdev run."""
    repo_root = repo.find_repo_root()
    m_filter: Dict[str, str] = {}
    for m in args.matrix or []:
        if "=" in m:
            k, v = m.split("=", 1)
            m_filter[k.strip()] = v.strip()

    code, rep = run_scenario(
        repo_root=repo_root,
        scenario_spec=args.scenario,
        issue_override=args.issue,
        check_filter=args.check or None,
        matrix_filter=m_filter or None,
        headed=args.headed,
        file_failures_flag=args.file_failures,
        keep_evidence_dir=args.keep_evidence,
    )
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        summary = rep.get("summary", {})
        print(
            f"-> Scenario run completed: {summary.get('passed', 0)} PASS, "
            f"{summary.get('failed', 0)} FAIL, {summary.get('not_run', 0)} NOT RUN"
        )
    return code


def handle_shot_cli(args: argparse.Namespace) -> int:
    """CLI handler for along webdev shot."""
    repo_root = repo.find_repo_root()
    scenario_dict = {
        "meta": {"issue": args.issue or "shot", "title": f"Quick shot of {args.url}"},
        "checks": [
            {
                "id": "shot",
                "title": f"Shot of {args.url}",
                "matrix": {"viewport": [args.viewport], "theme": [args.theme]},
                "steps": [
                    {"action": "goto", "url": args.url},
                    {"action": "screenshot"},
                ],
            }
        ],
    }
    code, _ = run_scenario(repo_root, scenario_dict, keep_evidence_dir=os.path.dirname(args.out))
    return code
