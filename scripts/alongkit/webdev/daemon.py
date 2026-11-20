#!/usr/bin/env python3
"""alongkit.webdev.daemon - Interactive browser session daemon and transcript recorder (REQ-10)."""

from __future__ import annotations

import http.server
import json
import os
import secrets
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import ruamel.yaml

from .. import entities, proc, repo, textio
from . import browser, capture, config, redact, services, session, steps


DEFAULT_IDLE_TIMEOUT_SECONDS = 900  # 15 minutes


def get_session_info_path(repo_root: str) -> str:
    """Return path to active session JSON file."""
    sdir = repo.state_dir(repo_root)
    return os.path.join(sdir, ".session", "webdev_session.json")


def read_session_info(repo_root: str) -> Optional[Dict[str, Any]]:
    """Read session info if active session file exists and is valid."""
    path = get_session_info_path(repo_root)
    if not os.path.isfile(path):
        return None
    try:
        raw = textio.read_text(path)
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("port") and data.get("token"):
            return data
    except (OSError, ValueError, TypeError):
        pass
    return None


class InteractiveSessionServer:
    """HTTP daemon managing an interactive browser session."""

    def __init__(
        self,
        repo_root: str,
        issue_key: str,
        service_names: Optional[List[str]] = None,
        idle_timeout_seconds: int = DEFAULT_IDLE_TIMEOUT_SECONDS,
        port: int = 0,
        headed: bool = False,
    ):
        self.repo_root = os.path.abspath(repo_root)
        self.issue_key = issue_key
        self.service_names = service_names or []
        self.idle_timeout_seconds = idle_timeout_seconds
        self.requested_port = port
        self.headed = headed

        self.token = secrets.token_hex(16)
        self.transcript: List[Dict[str, Any]] = []
        self.last_active_time = time.monotonic()
        self.is_running = False

        self.httpd: Optional[http.server.HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.watchdog_thread: Optional[threading.Thread] = None

        self.b_proc: Optional[browser.BrowserProcess] = None
        self.pw: Optional[Any] = None
        self.page: Optional[Any] = None
        self.redactor = redact.Redactor()
        self.harvester = capture.DiagnosticsHarvester(redactor=self.redactor)

    def start(self) -> Dict[str, Any]:
        """Start services, browser, and HTTP daemon."""
        if self.service_names:
            services.serve_up(self.repo_root, service_names=self.service_names)

        is_hermetic = os.environ.get("ALONG_WEBDEV_HERMETIC") == "1"
        if not is_hermetic:
            try:
                b_proc, (pw, page) = session.create_browser_session(
                    self.repo_root,
                    headed=self.headed,
                )
                self.b_proc = b_proc
                self.pw = pw
                self.page = page
            except (RuntimeError, OSError, ValueError) as exc:
                print(f"[Warning] Interactive browser creation fallback: {exc}", file=sys.stderr)

        server_instance = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, format_str: str, *args: Any) -> None:
                # Suppress normal HTTP logging
                pass

            def _authenticate(self) -> bool:
                auth = self.headers.get("Authorization", "")
                if auth == f"Bearer {server_instance.token}":
                    return True
                return False

            def _send_json(self, status_code: int, data: Dict[str, Any]) -> None:
                body = json.dumps(data, indent=2).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                server_instance.last_active_time = time.monotonic()
                if self.path in ("/status", "/health"):
                    if not self._authenticate():
                        self._send_json(401, {"ok": False, "error": "Unauthorized"})
                        return
                    self._send_json(200, {
                        "ok": True,
                        "alive": True,
                        "issue": server_instance.issue_key,
                        "steps_count": len(server_instance.transcript),
                        "services": server_instance.service_names,
                    })
                    return
                self._send_json(404, {"ok": False, "error": "Not Found"})

            def do_POST(self) -> None:
                server_instance.last_active_time = time.monotonic()
                if not self._authenticate():
                    self._send_json(401, {"ok": False, "error": "Unauthorized"})
                    return

                length = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
                try:
                    payload = json.loads(raw_body)
                except ValueError:
                    self._send_json(400, {"ok": False, "error": "Invalid JSON body"})
                    return

                if self.path == "/step":
                    step_obj = payload.get("step")
                    if not isinstance(step_obj, dict):
                        self._send_json(400, {"ok": False, "error": "Missing 'step' object"})
                        return
                    res = server_instance.execute_step(step_obj)
                    self._send_json(200, res)
                    return

                elif self.path == "/batch":
                    step_list = payload.get("steps")
                    if not isinstance(step_list, list):
                        self._send_json(400, {"ok": False, "error": "Missing 'steps' array"})
                        return
                    results_list = []
                    for stp in step_list:
                        if isinstance(stp, dict):
                            results_list.append(server_instance.execute_step(stp))
                    self._send_json(200, {
                        "ok": True,
                        "executed_count": len(results_list),
                        "transcript_count": len(server_instance.transcript),
                        "results": results_list,
                    })
                    return

                elif self.path == "/save":
                    out_path = payload.get("path") or "scenario.yaml"
                    issue_slug = payload.get("issue") or server_instance.issue_key
                    title = payload.get("title") or f"Recorded scenario for {issue_slug}"
                    saved_path = server_instance.save_transcript(out_path, issue_slug, title)
                    self._send_json(200, {
                        "ok": True,
                        "saved_to": saved_path,
                        "steps_count": len(server_instance.transcript),
                    })
                    return

                elif self.path == "/stop":
                    info_path = get_session_info_path(server_instance.repo_root)
                    if os.path.isfile(info_path):
                        try:
                            os.remove(info_path)
                        except OSError:
                            pass
                    self._send_json(200, {"ok": True, "message": "Stopping session"})
                    threading.Thread(target=server_instance.shutdown).start()
                    return

                self._send_json(404, {"ok": False, "error": "Not Found"})

        self.httpd = http.server.HTTPServer(("127.0.0.1", self.requested_port), Handler)
        bound_port = self.httpd.server_port
        self.is_running = True

        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()

        # Start idle watchdog
        self.watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self.watchdog_thread.start()

        # Write session info file
        info_path = get_session_info_path(self.repo_root)
        os.makedirs(os.path.dirname(info_path), exist_ok=True)
        session_data = {
            "port": bound_port,
            "token": self.token,
            "pid": os.getpid(),
            "issue": self.issue_key,
            "services": self.service_names,
            "created_at": time.time(),
        }
        textio.write_text(info_path, json.dumps(session_data, indent=2))

        return session_data

    def execute_step(self, step_obj: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single step against active page and record into transcript."""
        if self.page:
            try:
                steps.execute_step(self.page, step_obj, harvester=self.harvester, redactor=self.redactor)
            except (RuntimeError, AssertionError, ValueError, TypeError, KeyError, OSError, TimeoutError) as exc:
                self.transcript.append(step_obj)
                return {"ok": False, "error": str(exc), "step": step_obj}

        self.transcript.append(step_obj)
        return {"ok": True, "step": step_obj, "transcript_index": len(self.transcript) - 1}

    def save_transcript(self, output_path: str, issue_slug: str, title: str) -> str:
        """Convert transcript steps into scenario YAML file."""
        scenario_data: Dict[str, Any] = {
            "meta": {
                "issue": issue_slug,
                "title": title,
            },
            "services": self.service_names,
            "defaults": {
                "origins": ["http://localhost:5173", "http://localhost:8000"],
                "viewport": "desktop-1280x800",
                "theme": "light",
            },
            "checks": [
                {
                    "id": "C1",
                    "title": title,
                    "steps": list(self.transcript),
                }
            ],
        }

        abs_out = os.path.join(self.repo_root, output_path) if not os.path.isabs(output_path) else output_path
        os.makedirs(os.path.dirname(abs_out), exist_ok=True)

        yaml = ruamel.yaml.YAML()
        yaml.default_flow_style = False
        with open(abs_out, "w", encoding="utf-8") as f:
            yaml.dump(scenario_data, f)

        return abs_out

    def _watchdog_loop(self) -> None:
        """Monitor idle duration and auto-shutdown if idle timeout exceeded."""
        while self.is_running:
            time.sleep(5)
            if time.monotonic() - self.last_active_time > self.idle_timeout_seconds:
                self.shutdown()
                break

    def shutdown(self) -> None:
        """Shutdown browser and HTTP daemon, clean up state file."""
        self.is_running = False

        if self.page:
            try:
                self.page.close()
            except (RuntimeError, OSError, AttributeError):
                pass
            self.page = None

        if self.pw:
            try:
                self.pw.stop()
            except (RuntimeError, OSError, AttributeError):
                pass
            self.pw = None

        if self.b_proc:
            try:
                self.b_proc.close()
            except (RuntimeError, OSError, AttributeError):
                pass
            self.b_proc = None

        if self.httpd:
            try:
                self.httpd.shutdown()
            except (RuntimeError, OSError, AttributeError):
                pass
            self.httpd = None

        info_path = get_session_info_path(self.repo_root)
        if os.path.isfile(info_path):
            try:
                os.remove(info_path)
            except OSError:
                pass


def _dispatch_request(
    repo_root: str,
    endpoint: str,
    method: str = "GET",
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Helper to dispatch request to running session daemon."""
    info = read_session_info(repo_root)
    if not info:
        raise RuntimeError("No active webdev session found. Run 'along webdev session start' first.")

    port = info["port"]
    token = info["token"]
    url = f"http://127.0.0.1:{port}{endpoint}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    data_bytes = json.dumps(payload).encode("utf-8") if payload is not None else None

    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content)
    except urllib.error.HTTPError as http_err:
        err_content = http_err.read().decode("utf-8")
        try:
            return json.loads(err_content)
        except ValueError:
            return {"ok": False, "error": f"HTTP {http_err.code}: {http_err.reason}"}
    except (urllib.error.URLError, ConnectionError, OSError) as net_err:
        raise RuntimeError(f"Failed to communicate with webdev session daemon: {net_err}") from net_err


def session_start(
    repo_root: str,
    issue_key: str,
    services_list: Optional[List[str]] = None,
    headed: bool = False,
    idle_timeout: int = DEFAULT_IDLE_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Start interactive session daemon."""
    existing = read_session_info(repo_root)
    if existing:
        return {"ok": True, "already_running": True, "session": existing}

    daemon = InteractiveSessionServer(
        repo_root=repo_root,
        issue_key=issue_key,
        service_names=services_list,
        idle_timeout_seconds=idle_timeout,
        headed=headed,
    )
    session_data = daemon.start()
    return {"ok": True, "already_running": False, "session": session_data}


def session_step(repo_root: str, step_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Execute single step in active session."""
    return _dispatch_request(repo_root, "/step", method="POST", payload={"step": step_obj})


def session_batch(repo_root: str, step_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Execute batch of steps in active session."""
    return _dispatch_request(repo_root, "/batch", method="POST", payload={"steps": step_list})


def session_save(
    repo_root: str,
    output_path: str,
    issue: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """Save session transcript to scenario file."""
    payload = {"path": output_path}
    if issue:
        payload["issue"] = issue
    if title:
        payload["title"] = title
    return _dispatch_request(repo_root, "/save", method="POST", payload=payload)


def session_status(repo_root: str) -> Dict[str, Any]:
    """Check status of active session."""
    return _dispatch_request(repo_root, "/status", method="GET")


def session_stop(repo_root: str) -> Dict[str, Any]:
    """Stop active session."""
    info = read_session_info(repo_root)
    if not info:
        return {"ok": True, "already_stopped": True}
    return _dispatch_request(repo_root, "/stop", method="POST")


def handle_session_cli(args: Any) -> int:
    """CLI handler for 'along webdev session' (REQ-10)."""
    repo_root = repo.find_repo_root()
    action = args.action

    if action == "start":
        issue_key = getattr(args, "issue", None)
        if not issue_key:
            active, _ = entities.resolve_active_issue(repo_root)
            issue_key = active["slug"] if active else "scratch"
        res = session_start(repo_root, issue_key=issue_key, headed=getattr(args, "headed", False))
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2))
        else:
            print(f"Session started on port {res.get('session', {}).get('port')} (issue: {issue_key})")
        return 0

    elif action == "status":
        try:
            res = session_status(repo_root)
            if getattr(args, "json", False):
                print(json.dumps(res, indent=2))
            else:
                print(f"Session status: alive={res.get('alive')}, steps={res.get('steps_count')}")
            return 0
        except (RuntimeError, OSError) as exc:
            print(f"[Error] {exc}", file=sys.stderr)
            return 1

    elif action == "step":
        if not args.step:
            print("[Error] --step argument required for 'session step'.", file=sys.stderr)
            return 2
        try:
            step_data = json.loads(args.step)
        except ValueError:
            yaml = ruamel.yaml.YAML(typ="safe")
            step_data = yaml.load(args.step)
        try:
            res = session_step(repo_root, step_data)
            if getattr(args, "json", False):
                print(json.dumps(res, indent=2))
            else:
                print(f"Step executed: ok={res.get('ok')}")
            return 0 if res.get("ok") else 1
        except (RuntimeError, OSError) as exc:
            print(f"[Error] {exc}", file=sys.stderr)
            return 1

    elif action == "batch":
        if not args.batch:
            print("[Error] --batch argument required for 'session batch'.", file=sys.stderr)
            return 2
        try:
            batch_data = json.loads(args.batch)
        except ValueError:
            yaml = ruamel.yaml.YAML(typ="safe")
            batch_data = yaml.load(args.batch)
        try:
            res = session_batch(repo_root, batch_data)
            if getattr(args, "json", False):
                print(json.dumps(res, indent=2))
            else:
                print(f"Batch executed: count={res.get('executed_count')}")
            return 0 if res.get("ok") else 1
        except (RuntimeError, OSError) as exc:
            print(f"[Error] {exc}", file=sys.stderr)
            return 1

    elif action == "save":
        target_path = args.save_as or "scenario.yaml"
        issue_key = getattr(args, "issue", None)
        try:
            res = session_save(repo_root, target_path, issue=issue_key)
            if getattr(args, "json", False):
                print(json.dumps(res, indent=2))
            else:
                print(f"Session saved to {res.get('saved_to')} ({res.get('steps_count')} steps)")
            return 0
        except (RuntimeError, OSError) as exc:
            print(f"[Error] {exc}", file=sys.stderr)
            return 1

    elif action == "stop":
        try:
            res = session_stop(repo_root)
            if getattr(args, "json", False):
                print(json.dumps(res, indent=2))
            else:
                print("Session stopped.")
            return 0
        except (RuntimeError, OSError) as exc:
            print(f"[Error] {exc}", file=sys.stderr)
            return 1

    return 2
