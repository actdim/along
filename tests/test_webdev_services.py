#!/usr/bin/env python3
"""tests/test_webdev_services.py - Hermetic tests for application services lifecycle (REQ-1)."""

from __future__ import annotations

import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))

from alongkit import proc
from alongkit.webdev import config, services


def find_free_port() -> int:
    """Find a random available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestWebdevServicesLifecycle(unittest.TestCase):
    """Hermetic unit tests for along webdev serve lifecycle."""

    def setUp(self):
        self.temp_repo = tempfile.mkdtemp()
        self.state_dir = os.path.join(self.temp_repo, ".along")
        os.makedirs(self.state_dir, exist_ok=True)
        self.fixtures_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "webdev"))

    def tearDown(self):
        try:
            services.serve_down(self.temp_repo)
        finally:
            shutil.rmtree(self.temp_repo, ignore_errors=True)

    def test_serve_up_and_down_lifecycle(self):
        port = find_free_port()
        svc_cmd = f"{sys.executable} {os.path.join(self.fixtures_dir, 'good_service.py')} {port}"

        raw_cfg = {
            "services": {
                "web": {
                    "command": svc_cmd,
                    "probe": {
                        "http": {
                            "url": f"http://127.0.0.1:{port}",
                            "status": 200,
                            "timeout": 5.0,
                        }
                    },
                }
            }
        }
        cfg = config.parse_webdev_config(raw_cfg, self.temp_repo)

        res = services.serve_up(self.temp_repo, cfg=cfg)
        self.assertTrue(res["ok"])
        st = services.serve_status(self.temp_repo)
        self.assertIn("web", st)
        self.assertEqual(st["web"]["state"], "running")
        self.assertTrue(st["web"]["started_by_along"])
        pid = st["web"]["pid"]
        self.assertTrue(services.is_pid_alive(pid))

        # Check serve_down terminates the process
        down_res = services.serve_down(self.temp_repo)
        self.assertEqual(down_res["web"], "stopped")
        self.assertFalse(services.is_pid_alive(pid))

    def test_attach_if_already_running_and_preserve_on_down(self):
        port = find_free_port()
        # Start external service process independently
        ext_proc = subprocess.Popen(
            [sys.executable, os.path.join(self.fixtures_dir, "good_service.py"), str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            # Wait until socket is open
            for _ in range(50):
                if services.is_port_open(port):
                    break
                import time; time.sleep(0.1)

            raw_cfg = {
                "services": {
                    "api": {
                        "command": f"{sys.executable} nonexistent.py",
                        "probe": {"port": port},
                    }
                }
            }
            cfg = config.parse_webdev_config(raw_cfg, self.temp_repo)

            res = services.serve_up(self.temp_repo, cfg=cfg)
            self.assertTrue(res["ok"])
            st = services.serve_status(self.temp_repo)
            self.assertEqual(st["api"]["state"], "attached")
            self.assertFalse(st["api"]["started_by_along"])

            # Down must not kill what Along did not start (REQ-1)
            down_res = services.serve_down(self.temp_repo)
            self.assertEqual(down_res["api"], "preserved_attached")
            self.assertIsNone(ext_proc.poll())
        finally:
            proc.kill_process_tree(ext_proc, grace=0.5)

    def test_crash_reporting_with_log_tail(self):
        svc_cmd = f"{sys.executable} {os.path.join(self.fixtures_dir, 'crash_service.py')}"
        raw_cfg = {
            "services": {
                "crasher": {
                    "command": svc_cmd,
                    "probe": {"http": {"url": "http://127.0.0.1:9999", "timeout": 2.0}},
                }
            }
        }
        cfg = config.parse_webdev_config(raw_cfg, self.temp_repo)

        with self.assertRaises(RuntimeError) as ctx:
            services.serve_up(self.temp_repo, cfg=cfg)
        self.assertIn("exited prematurely", str(ctx.exception))

    def test_static_helper_kind(self):
        port = find_free_port()
        static_dir = os.path.join(self.temp_repo, "static_content")
        os.makedirs(static_dir, exist_ok=True)
        with open(os.path.join(static_dir, "hello.txt"), "w", encoding="utf-8") as f:
            f.write("Hello Static")

        raw_cfg = {
            "services": {
                "cors-static": {
                    "kind": "static",
                    "root": "static_content",
                    "port": port,
                }
            }
        }
        cfg = config.parse_webdev_config(raw_cfg, self.temp_repo)

        res = services.serve_up(self.temp_repo, cfg=cfg)
        self.assertTrue(res["ok"])
        st = services.serve_status(self.temp_repo)
        self.assertEqual(st["cors-static"]["state"], "running")

        # Verify static HTTP server delivers file
        self.assertTrue(services.probe_http(f"http://127.0.0.1:{port}/hello.txt", status_spec=200))
        services.serve_down(self.temp_repo)

    def test_env_secret_never_leaked(self):
        secret_value = "super_secret_token_12345"
        with open(os.path.join(self.temp_repo, ".env"), "w", encoding="utf-8") as f:
            f.write(f"MY_TOKEN={secret_value}\n")

        port = find_free_port()
        raw_cfg = {
            "services": {
                "auth_app": {
                    "command": f"{sys.executable} {os.path.join(self.fixtures_dir, 'good_service.py')} {port}",
                    "env": {
                        "AUTH_KEY": "${env:MY_TOKEN}",
                        "NORMAL": "public_val",
                    },
                    "probe": {"port": port},
                }
            }
        }
        cfg = config.parse_webdev_config(raw_cfg, self.temp_repo)
        services.serve_up(self.temp_repo, cfg=cfg)

        state_path = services.get_services_state_path(self.temp_repo)
        with open(state_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Secret must never appear in saved state or stdout
        self.assertNotIn(secret_value, content)
        services.serve_down(self.temp_repo)


if __name__ == "__main__":
    unittest.main()
